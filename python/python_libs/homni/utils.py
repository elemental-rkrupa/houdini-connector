# SPDX-FileCopyrightText: Copyright (c) 2022-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.
import asyncio
import fnmatch
import os
import pathlib
import shutil
import time
import traceback
from contextlib import contextmanager

import hou
import omni.client
from homni import client as hclient
from homni import logging

LOGGER = logging.get_homni_logger()

NVIDIA_COLOR = hou.Color(0.46, 0.72, 0)


def is_omniverse_path_parm(parm):
    """Determines if given parm is a string parm and contains an omniverse asset path.
    Note this returns Ture even if the path does not exist.
    Args:
        parm (hou.Parm): hou.Parm object to determine if it is an omniverse parm.

    Returns:
        bool: True if the given parm is an omniverse parm.
    """
    parm_template = parm.parmTemplate()
    # Not a string field...
    if not parm_template.type() == hou.parmTemplateType.String:
        return False

    # Not a file reference
    if not parm_template.stringType() == hou.stringParmType.FileReference:
        return False

    # Not a Omni server
    if omni.client.break_url(parm.evalAsString()).host is None:
        return False

    return True


async def is_checkpoint_path_ready_parm_async(parm):
    """Determines if given parm is a string parm and contains an omniverse asset path that its checkpoint is enabled.

    Args:
        parm (hou.Parm): hou.Parm object to determine if it is an omniverse parm with
                         omniverse asset path that its checkpoint is enabled.

    Returns:
        bool: True if the given parm is an omniverse parm with checkpoints enabled path asset path.
    """
    # Not a string parm contains omniverse path.
    if not is_omniverse_path_parm(parm):
        return False

    parm_string_value = parm.evalAsString()
    # Queried to get info about it...
    result, server_info = await omni.client.get_server_info_async(parm_string_value)
    if result != omni.client.Result.OK:
        return False

    # checkpoints disabled
    if not server_info.checkpoints_enabled:
        return False

    # A file that has no checkpoint
    result, checkpoints = await omni.client.list_checkpoints_async(parm_string_value)
    if result != omni.client.Result.OK:
        return False
    if not checkpoints:
        return False

    return True


def is_checkpoint_path_ready_parm(parm):
    """Determines if given parm is a string parm and contains an omniverse asset path that its checkpoint is enabled.

    Args:
        parm (hou.Parm): hou.Parm object to determine if it is an omniverse parm with
                         omniverse asset path that its checkpoint is enabled.

    Returns:
        bool: True if the given parm is an omniverse parm with checkpoints enabled path asset path.
    """
    # Not a string parm contains omniverse path.
    if not is_omniverse_path_parm(parm):
        return False

    parm_string_value = parm.evalAsString()
    # Queried to get info about it...
    result, server_info = omni.client.get_server_info(parm_string_value)
    if result != omni.client.Result.OK:
        return False

    # checkpoints disabled
    if not server_info.checkpoints_enabled:
        return False

    # A file that has no checkpoint
    result, checkpoints = omni.client.list_checkpoints(parm_string_value)
    if result != omni.client.Result.OK:
        return False
    if not checkpoints:
        return False

    return True


def _menu_filter_deco(func):
    """Decorator to help catching errors while Houdini running menu expression."""

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (Exception, hou.Error):
            LOGGER.warning(traceback.format_exc())
            LOGGER.warning(rf"Error running menu filter - {func.__name__}")
            return False

    return wrapper


@_menu_filter_deco
def show_rmb_checkpoint_filter(kwargs):
    """Determines if the right click menu option to insert checkpoint syntax onto file paths should be shown

    Args:
        kwargs (dict): Houdini dict containing information about the parameter

    Returns:
        bool: True/False weather menu option should be shown
    """
    try:
        loop = asyncio.new_event_loop()
        task = asyncio.ensure_future(show_rmb_checkpoint_async(kwargs), loop=loop)
        loop.run_until_complete(task)
        return task.result()
    except (Exception, hou.Error):
        return show_rmb_checkpoint(kwargs)


def show_rmb_checkpoint(kwargs):
    """Determines if the right click menu option to insert checkpoint syntax onto file paths should be shown

    Args:
        kwargs (dict): Houdini dict containing information about the parameter

    Returns:
        bool: True/False weather menu option should be shown
    """
    # Parameter clicked on - should contain one
    if len(kwargs["parms"]) != 1:
        return False
    parm = kwargs["parms"][0]

    # If the parm already has checkpoint syntax set.
    # Note that we put `omni.client.break_url(parm.evalAsString()).query` before `is_checkpoint_path_ready_parm()`
    # because this is a cheaper check. (only string processing)
    if omni.client.break_url(parm.evalAsString()).query is not None:
        return False

    # The parm is not an omniverse path parm or the omniverse asset path has no checkpoints
    if not is_checkpoint_path_ready_parm(parm):
        return False

    return True


async def show_rmb_checkpoint_async(kwargs):
    """Determines if the right click menu option to insert checkpoint syntax onto file paths should be shown

    Args:
        kwargs (dict): Houdini dict containing information about the parameter

    Returns:
        bool: True/False weather menu option should be shown
    """
    # Parameter clicked on - should contain one
    if len(kwargs["parms"]) != 1:
        return False
    parm = kwargs["parms"][0]

    # If the parm already has checkpoint syntax set.
    # Note that we put `omni.client.break_url(parm.evalAsString()).query` before `is_checkpoint_path_ready_parm_async()`
    # because this is a cheaper check. (only string processing)
    if omni.client.break_url(parm.evalAsString()).query is not None:
        return False

    # The parm is not an omniverse path parm or the omniverse asset path has no checkpoints
    if not await is_checkpoint_path_ready_parm_async(parm):
        return False

    return True


def _run_async(async_func, *args, **kwargs):
    """Helper function executing async function in Houdini 19.0, 19.5 and 20.0

    Args:
        async_func (async callable): async function to execute.
    """
    try:
        # H20 has its own implementation of event loop on UI mode - HoudiniEventLoop.
        # We cannot call loop.run_until_complete in H20 UI mode.
        loop = asyncio.get_running_loop()
        asyncio.ensure_future(async_func(*args, **kwargs), loop=loop)
    except (Exception, hou.Error):
        loop = asyncio.new_event_loop()
        task = asyncio.ensure_future(async_func(*args, **kwargs), loop=loop)
        loop.run_until_complete(task)


def enable_checkpoint_syntax(kwargs):
    """Add checkpoint syntax "?&{version_digits}" in the calling parameter.

    Args:
        kwargs (dict): Houdini dict containing information about the parameter
    """
    _run_async(enable_checkpoint_syntax_async, kwargs)


async def enable_checkpoint_syntax_async(kwargs):
    """Add checkpoint syntax "?&{version_digits}" in the calling parameter.

    This function is run when the above context expression filter has been passed, that is why there is only
    a very simple check on the incoming kwargs

    Args:
        kwargs (dict): Houdini dict containing information about the parameter
    """
    parms = kwargs["parms"]
    if not parms:
        return
    parm = parms[0]
    file_path = parm.evalAsString()
    result, checkpoints = await omni.client.list_checkpoints_async(file_path)
    if result != omni.client.Result.OK:
        return

    last_checkpoint = len(checkpoints)
    checkpointed_filepath = f"{file_path}?&{last_checkpoint}"
    parm.set(checkpointed_filepath)

    await enable_checkpoint_info_async(kwargs)


def has_checkpoint_parm_changed_callback(node):
    """Determines if the given node has checkpoint_parm_changed_callback event callback registerd.

    Args:
        node (hou.Node): hou.Node object to determine if it has checkpoint_parm_changed_callback
        event callback registerd.

    Returns:
        bool: True if the given node has checkpoint_parm_changed_callback event callback registerd.
    """
    # Check for already existing callback, return True if it already exists
    for callback in node.eventCallbacks():
        if hou.nodeEventType.ParmTupleChanged in callback[0]:
            callback_function = callback[1]
            if callback_function.__name__ == "checkpoint_parm_changed_callback":
                return True
    return False


@_menu_filter_deco
def show_rmb_checkpoint_info_filter(kwargs):
    """Determines if the right click menu option to display checkpoint info on viewport should be shown

    Args:
        kwargs (dict): Houdini dict containing information about the parameter

    Returns:
        bool: True/False weather menu option should be shown
    """
    try:
        loop = asyncio.new_event_loop()
        task = asyncio.ensure_future(show_rmb_checkpoint_info_async(kwargs), loop=loop)
        loop.run_until_complete(task)
        return task.result()
    except (Exception, hou.Error):
        return show_rmb_checkpoint_info(kwargs)


def show_rmb_checkpoint_info(kwargs):
    """Determines if the right click menu option to display checkpoint info on viewport should be shown

    Args:
        kwargs (dict): Houdini dict containing information about the parameter

    Returns:
        bool: True/False weather menu option should be shown
    """
    # Parameter clicked on - should contain one
    if len(kwargs["parms"]) != 1:
        return False
    parm = kwargs["parms"][0]

    # Parm has no checkpoint syntax
    # Note that we put `omni.client.break_url(parm.evalAsString()).query` before `is_checkpoint_path_ready_parm()`
    # because this is a cheaper check. (only string processing)
    if omni.client.break_url(parm.evalAsString()).query is None:
        return False

    # Check if Callback exists already.
    if has_checkpoint_parm_changed_callback(parm.node()):
        return False

    # The parm is not an omniverse path parm or the omniverse asset path has no checkpoints
    if not is_checkpoint_path_ready_parm(parm):
        return False

    return True


async def show_rmb_checkpoint_info_async(kwargs):
    """Determines if the right click menu option to display checkpoint info on viewport should be shown

    Args:
        kwargs (dict): Houdini dict containing information about the parameter

    Returns:
        bool: True/False weather menu option should be shown
    """
    # Parameter clicked on - should contain one
    if len(kwargs["parms"]) != 1:
        return False
    parm = kwargs["parms"][0]

    # Parm has no checkpoint syntax
    # Note that we put `omni.client.break_url(parm.evalAsString()).query` before `is_checkpoint_path_ready_parm_async()`
    # because this is a cheaper check. (only string processing)
    if omni.client.break_url(parm.evalAsString()).query is None:
        return False

    # Check if Callback exists already.
    if has_checkpoint_parm_changed_callback(parm.node()):
        return False

    # The parm is not an omniverse path parm or the omniverse asset path has no checkpoints
    if not await is_checkpoint_path_ready_parm_async(parm):
        return False

    return True


def enable_checkpoint_info(kwargs):
    """Display checkpoint info, version, creator, and comments on the viewport.

    Args:
        kwargs (dict): Houdini dict containing information about the parameter
    """
    _run_async(enable_checkpoint_info_async, kwargs)


async def enable_checkpoint_info_async(kwargs):
    """Display checkpoint info, version, creator, and comments on the viewport.

    This function is run when the above context expression filter has been passed,
    that is why there is only a very simple check on the incoming kwargs

    Args:
        kwargs (dict): Houdini dict containing information about the parameter
    """
    parms = kwargs["parms"]
    if not parms:
        return
    parm = parms[0]

    # Create UI info callback if the UI is available
    if not hou.isUIAvailable:
        return

    node = parm.node()
    # Check for already existing callback, return if it already exists
    if has_checkpoint_parm_changed_callback(node):
        return

    def checkpoint_parm_changed_callback(*args, **kwargs):
        """Callback function to run checkpoint_parm_changed async."""
        try:
            _run_async(checkpoint_parm_changed, *args, **kwargs)
        except Exception:
            LOGGER.warning(r"Failed getting checkpoint info.")

    node.addParmCallback(checkpoint_parm_changed_callback, [parm.name()])
    # For the first time, fire the callback manually to see the initial checkpoint data in the viewport
    await checkpoint_parm_changed(
        event_type=hou.nodeEventType.ParmTupleChanged, node=node, parm_tuple=node.parmTuple(parm.path())
    )


async def checkpoint_parm_changed(event_type, **kwargs):
    """Callback when changing the checkpoint path, handles displaying checkpoint info in the Houdini viewport

    Args:
        event_type (hou.nodeEventType): Expecting and only acting on `hou.nodeEventType.ParmTupleChanged`
        kwargs (dict): callback contains dict with node instance and parmTuple that changed
    """
    if not event_type == hou.nodeEventType.ParmTupleChanged:
        return
    if not hou.isUIAvailable:
        return
    parm = kwargs["parm_tuple"]
    file_paths = parm.evalAsStrings()
    if not file_paths:
        return
    file_path = file_paths[0]
    result, checkpoints = await omni.client.list_checkpoints_async(file_path)
    if result != omni.client.Result.OK or not checkpoints:
        return

    url_parts = omni.client.break_url(file_path)
    current_checkpoint = None
    for checkpoint in checkpoints:
        if checkpoint.relative_path == url_parts.query:
            current_checkpoint = checkpoint
    if current_checkpoint is None:
        return
    scene_viewer = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
    if scene_viewer is None:
        return

    # Bottom of the viewport message
    prompt_message = f"Checkpoint Comment: {current_checkpoint.comment}"
    scene_viewer.clearPromptMessage()
    scene_viewer.setPromptMessage(prompt_message, hou.promptMessageType.Prompt)

    # Top left viewport message
    flash_message = f'Checkpoint #{current_checkpoint.relative_path.replace("&", "")}    Created by: {current_checkpoint.created_by}'
    scene_viewer.flashMessage(image="LOP_omni_live_sync.png", msg=flash_message, duration=3.0)


def create_node_with_presets(kwargs, op_type, op_name, preset_name):
    """Place down a node with a preset applied

    Args:
        kwargs (dict): Houdini info dictionary
        op_type (str): Type name of the node to create
        op_name (str): Name of the node to create
        preset_name (str): The preset to apply
    """

    if not hou.isUIAvailable():
        LOGGER.warning(f"{op_name} node creation shelf tool is only available in Houdini graphic mode.")
        return

    lop_pane = get_lop_network_panetab()
    if lop_pane is None:
        hou.ui.displayMessage(
            text=f"Failed to find the active LOP network editor pane", severity=hou.severityType.Error
        )
        return

    node = lop_pane.pwd()
    # Input
    inputs = kwargs.get("inputs")
    input_item, output_index = inputs[0] if inputs and isinstance(inputs, list) else (None, -1)
    # make sure input item is an item exists in the context.
    input_item = node.item(input_item) if input_item else None

    # Output
    outputs = kwargs.get("outputs")
    output_item, input_index = outputs[0] if outputs and isinstance(outputs, list) else (None, -1)
    # make sure output item is an item exists in the context.
    output_item = node.item(output_item) if output_item else None

    # Autoplace
    autoplace = kwargs.get("autoplace", not hou.isUIAvailable())

    # Append to the current node while shift-clicked
    # This should always return false while doing tab menu.
    if kwargs.get("shiftclick") and input_item is None and lop_pane.currentNode().outputConnectors():
        input_item = lop_pane.currentNode()
        output_index = 0

    # Pos
    if autoplace or lop_pane.listMode():
        pos = lop_pane.cursorPosition()
        adjust_pos = True
    else:
        adjust_pos = False
        pos = lop_pane.selectPosition(input_item, output_index, output_item, input_index)

    if adjust_pos:
        pos -= node.size() / 2

    # Create LOP node
    new_node = None
    if isinstance(node, (hou.LopNetwork, hou.LopNode)):
        new_node = node.createNode(op_type, node_name=op_name)
    else:
        msg = f"Unable to create node. Unknown current context - {node.path()} ({node.type()})"
        hou.ui.displayMessage(text=msg, severity=hou.severityType.Error)
        return

    new_node.setSelected(True, clear_all_selected=True)

    # Apply preset
    out, err = hou.hscript(f'oppresetload {new_node.path()} "{preset_name}"')
    if err:
        msg = f'Unable to load preset "{preset_name}" for node "{new_node.path()}"'
        hou.ui.displayMessage(text=msg, severity=hou.severityType.Error)
        new_node.destroy()
        return

    # Set Nvidia color
    new_node.setColor(NVIDIA_COLOR)

    # Move to good position
    new_node.move(pos)

    # Find if we need to auto connect based on the dropped pos. This is tricky since it's based on the screen bbox
    if not input_item:
        wires = [
            i
            for i in lop_pane.networkItemsInBox(
                lop_pane.posToScreen(pos + (node.size() * 0.4)), lop_pane.posToScreen(pos + (node.size() * 0.5))
            )
            if i[1] == "wire"
        ]
        if wires:
            input_item = wires[0][0].inputItem()
            output_index = wires[0][0].inputItemOutputIndex()
            output_item = wires[0][0].outputItem()
            out_connection_index = wires[0][0].inputIndex()

    # Connect input
    if input_item:
        new_node.setInput(output_index, input_item)

    # Connect output
    if output_item:
        output_item.setInput(out_connection_index, new_node)


def legacy_light_properties(kwargs):
    """Place down a copy property node and apply a "set_legacy_light_props" preset

    Args:
        kwargs (dict): Houdini info dictionary
    """
    create_node_with_presets(kwargs, "copyproperty", "set_legacy_light_properties", "set_legacy_light_props")


def scale_light_intensities(kwargs):
    """Place down an edit properties node and apply a "Scale Light Intensities" preset

    Args:
        kwargs (dict): Houdini info dictionary
    """
    create_node_with_presets(kwargs, "editproperties", "scale_light_intensities", "Scale Light Intensities")


def get_lop_network_panetab():
    """Get the LOP pane either stage, Lop node or Lop network

    Returns:
        paneTabType.NetworkEditor: The network editor pane
    """
    for panetab in hou.ui.paneTabs():
        if not panetab.isCurrentTab():
            continue
        if isinstance(panetab, hou.NetworkEditor) and isinstance(panetab.pwd(), (hou.LopNetwork, hou.LopNode)):
            return panetab


def get_parent_directory(path):
    """
    Return parent directory for path
    Args:
        path (str):

    Returns:
        str: path to the parent directory
    """

    url = omni.client.break_url(path)
    omni_path = True if url.host else False
    return (
        f"{url.scheme}://{url.host}{pathlib.Path(url.path).parent.as_posix()}"
        if omni_path
        else f"{pathlib.Path(path).parent.as_posix()}"
    )


def copy_file(source, target):
    """
    Utility for file copy that handles both nucleus and regular system paths
    Args:
        source (str): Source file to copy from
        target (str): Target file to copy to
        is_nucleus (bool): Is this a Nucleus copy.

    Returns:

    """
    source_url = omni.client.break_url(source)
    target_url = omni.client.break_url(target)
    is_nucleus = True if source_url.host or target_url.host else False
    if is_nucleus:
        omni.client.copy(source, target, omni.client.CopyBehavior.OVERWRITE)
    else:
        shutil.copyfile(source, target)


def ensure_directory_exists(directory_path: str) -> bool:
    """
    Makes sure that directory path exists both for nucleus paths and system paths
    Args:
        directory_path (str): directory path that needs to exist
        is_nucleus (bool) : True or False weather given path is a nucleus path

    Returns:
        bool: True/False if directory now exists

    """
    url = omni.client.break_url(directory_path)
    if url.host:
        result, list_entry = omni.client.stat(directory_path)
        if result != omni.client.Result.OK:
            result = omni.client.create_folder(directory_path)
            if result != omni.client.Result.OK:
                hou.ui.displayMessage(
                    text=f"Could not create nucleus directory - {directory_path}", severity=hou.severityType.Error
                )
                return False

    else:
        if not os.path.exists(directory_path):
            os.makedirs(directory_path)
            if not os.path.exists(directory_path):
                hou.ui.displayMessage(
                    text=f"Could not create directory - {directory_path}", severity=hou.severityType.Error
                )
                return False

    return True


def log_and_set_status_bar(message):
    """Helper function to log and set hou.ui.setStatusMessage()

    Args:
        message (str): message to log.
    """
    # Consider handling log level and hou.severityType
    LOGGER.info(message)
    if hou.isUIAvailable():
        hou.ui.setStatusMessage(message)


@contextmanager
def set_checkpoint_message(message="Houdini file update", ui=True, title="Omniverse Checkpoint"):
    """Context manager function to help setting Omniverse Nucleus file checkpoint message.
    Kwargs:
        message (str): Checkpoint comment.
        ui (bool): Open a Houdini dialog for users to type in checkpoint comment if this argument
                   is True and Houdini Ui is available.
        title (str): Dialog title if ui is True.
    yield:
        (tuple): bool, str - (True if checkpoint commnet is set properly,  comment message string.)
    """
    if ui and hou.isUIAvailable():
        # Checkpoint - Message input.
        btn_idx, message = hou.ui.readInput(
            message="Checkpoint Comment:",
            buttons=("OK", "Cancel"),
            severity=hou.severityType.Message,
            default_choice=0,
            close_choice=1,
            help="Enter/OK to accept, Escape/Cancel to cancel",
            title=title,
            initial_contents=message,
        )

        if btn_idx != 0:
            log_and_set_status_bar("Checkpoint comment not set.")
            yield False, message
            return

    message = message.strip()
    try:
        hclient.setCheckpointMessage(message)
        yield True, message
    finally:
        hclient.clearCheckpointMessage()


def get_backup_file_name(backup_directory, file_name):
    """
    Look into the Omniverse Nucleus backup directory and get the file name for the next backup
    Args:
        backup_directory (str): Location of backup directory
        file_name (str): The file name that is about to get backed up

    Returns:

    """
    extension = pathlib.Path(file_name).suffix
    name_only = pathlib.Path(file_name).stem
    bak_iter = 1
    result, files = omni.client.list(backup_directory)
    if result != omni.client.Result.OK:
        LOGGER.error(f"Backup directory can not be found - {backup_directory}")
        return
    pattern = f"{name_only}_bak*{extension}"
    for file in files:
        if not fnmatch.fnmatch(file.relative_path, pattern):
            continue
        bak_iter = pathlib.Path(file.relative_path).stem.replace(f"{name_only}_bak", "")
    bak_iter = int(bak_iter) + 1
    return f"{name_only}_bak{bak_iter}{extension}"


def omni_make_backup():
    """Manages backup file creation on the nucleus server"""
    url = omni.client.break_url(hou.hipFile.path())
    # Ensure we are on a nucleus server
    if not url.host:
        return

    # Nucleus backup directory creation
    parent_dir = f"{pathlib.Path(url.path).parent.as_posix()}"
    backup_directory_path = f"{url.scheme}://{url.host}{parent_dir}/backup"
    if not ensure_directory_exists(directory_path=backup_directory_path):
        LOGGER.warning("Backup directory could not be created")
        return
    source_file = hou.hipFile.path()
    backup_file_name = get_backup_file_name(backup_directory=backup_directory_path, file_name=hou.hipFile.basename())
    if backup_file_name is None:
        LOGGER.error(
            "Backup file name can not be found likely due to issue with backup folder - {backup_directory_path}"
        )
        return
    target_file = f"{backup_directory_path}/{backup_file_name}"
    omni.client.copy(source_file, target_file, omni.client.CopyBehavior.OVERWRITE)


def omni_save(omni_path: bool):
    """
    Logic to save the hip file with the currently set preferences

    Args:
        omni_path (bool): On a nucleus server

    Return:
        (tuple): Tuple of (bool, str). True if hip saved successfully, and message string if it was specified by user.
    """
    message = ""
    # 0 = Overwrite File
    # 1 = Increment Filename
    # 2 = Make Numbered Backup (does not work on Omniverse Nucleus paths)
    if hou.getPreference("autoIncrement") == "0":
        hou.hipFile.save()
    elif hou.getPreference("autoIncrement") == "1":
        hou.hipFile.saveAndIncrementFileName()
    elif hou.getPreference("autoIncrement") == "2":
        if omni_path:
            with set_checkpoint_message() as (confirmed, message):
                if confirmed:
                    hou.hipFile.save()
                    omni_make_backup()
                else:
                    log_and_set_status_bar("Save cancelled.")
                    return False, message

        else:
            hou.hipFile.saveAndBackup()
    return True, message


def save_helper():
    """Utility function to help avoid nucleus error with Make Numbered Backups. Emulate the functionality on Nucleus."""
    file_path = hou.hipFile.path()
    saved = False

    if hou.hipFile.isNewFile():
        file_path = hou.ui.selectFile(title="Save File", file_type=hou.fileType.Hip)
        if not file_path:
            return

        # We can't deduce file extension - make sure it is included
        hip_path = pathlib.Path(file_path)
        if hip_path.suffix == "":
            parent_folder = str(hip_path.parent)
            file_name = str(hip_path.name)
            file_path = hou.ui.selectFile(
                start_directory=parent_folder,
                title="Save File - Please include the file extension",
                default_value=file_name,
                file_type=hou.fileType.Hip,
            )
            if not file_path:
                return
            hip_path = pathlib.Path(file_path)
            if hip_path.suffix == "":
                hou.ui.displayMessage(
                    text=f"Please include the desired file extension in the path - {file_path}",
                    severity=hou.severityType.Error,
                )
                return
        with set_checkpoint_message() as (confirmed, message):
            if confirmed:
                hou.hipFile.save(file_path)
                saved = True
            else:
                log_and_set_status_bar("Save cancelled.")
                return

    else:
        url = omni.client.break_url(file_path)
        omni_path = True if url.host else False
        saved, message = omni_save(omni_path=omni_path)

    if saved:
        log_and_set_status_bar(f"Successfully save {file_path} ({time.ctime()}) - {message}")


def file_copy_helper():
    """UI session tool that supports copy files from one location to another. Omniverse paths supported. If you want to achieve the same thing in a headless session, you can use the utility method copy_file"""
    files_to_copy = hou.ui.selectFile(
        title="Files to copy", file_type=hou.fileType.Any, multiple_select=True, chooser_mode=hou.fileChooserMode.Read
    )
    if not files_to_copy:
        hou.ui.displayMessage(text="Please select one or more files to copy.", severity=hou.severityType.Message)
        return

    asset_list = [hou.text.expandString(file.strip()) for file in files_to_copy.split(";")]
    directory = hou.ui.selectFile(title="Output Root Folder", file_type=hou.fileType.Directory)
    if not directory:
        hou.ui.displayMessage(
            text="Please select a directory to copy the selected files to.", severity=hou.severityType.Message
        )
        return

    if directory.endswith("/"):
        directory = directory[:-1]

    for asset_path in asset_list:
        parent_directory = get_parent_directory(asset_path)
        target = asset_path.replace(parent_directory, directory)
        LOGGER.debug(f"Copying from {asset_path} to {target}")
        copy_file(asset_path, target)

    asset_list_string = "\n".join(asset_list)
    display_message = (
        f"Files copied to target directory - {directory}:\n{asset_list_string}"
        if len(asset_list) < 100
        else f"Files copied to target directory - {directory}:\n{asset_list_string[0:4000]}..."
    )
    hou.ui.displayMessage(text=f"{display_message}", severity=hou.severityType.Message)
