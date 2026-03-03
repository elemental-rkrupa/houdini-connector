# SPDX-FileCopyrightText: Copyright (c) 2022-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.
""" This script:
• Override the default Omniverse login authentication message box
• Adds omni.client into the expression globals
• Adds homni.utils into the expression globals
"""

import atexit
import importlib
import os
import sys
import threading
import tkinter as tk
import traceback
from functools import partial

import hou
import omni.client
from PySide6 import QtCore

LOGGER = None


# In case PYTHONPATH fail to load binding modules, instead, use importlib
def _import_module(name, path):
    """Load module from given path.
    Import omni and homni python bindings. We don't use PYTHONPATH to load pybindling modules
    because we might running into an issue that some HDK libraries aren't loaded yet while
    loading the python binding .so
    Args:
        name (str): Name of the module.
        path (str): File path of the module.

    Return:
        (module) Loaded module
    """
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        importlib.import_module(name)
    except Exception:
        error_msg = f"{traceback.format_exc()}\nFailed import {name} from {path}"
        if LOGGER:
            LOGGER.error(error_msg)
        else:
            print(error_msg)
        return

    return module


try:
    import homni.client
except ImportError:
    _import_module(
        "homni",
        hou.text.normpath(os.path.join(hou.text.expandString("$HOMNI"), "omni", "python", "homni", "__init__.py")),
    )
    import homni.client


homni.client.initialize()

import omni.log

# homni python modules
from homni import logging, utils


# Initialize LOGGER
def init_logger():
    """Initialize script logger"""
    global LOGGER
    # Remove existing log files, so every new Houdini session creates a new log file. Avoid
    # large log files.
    LOGGER = logging.get_homni_logger()

    # Log client versions
    LOGGER.info(f"omni.client version - {omni.client.get_version()}")
    LOGGER.info(f"homni.client version - {homni.client.getVersionString()}")


init_logger()


AUTH_DIALOG = None


def omni_auth_cb(show, server, handle):
    """Omniverse login authentication message box callback function. Calling the actual dialog pop
    function in a tread to prevert the dialog blocked by Houdini.

    Args:
        show (bool): A bool indicating if the dialog should be shown (true) or hidden (false)
        server (str): A string indicating the host name that the authentication is for
        handle (int): An integer handle that should be passed to "Cancel"
    """
    t = threading.Thread(target=partial(_omni_auth_cb, show, server, handle))
    t.start()


def _omni_auth_cb(show, server, handle):
    """Omniverse login authentication message box callback function.

    Args:
        show (bool): A bool indicating if the dialog should be shown (true) or hidden (false)
        server (str): A string indicating the host name that the authentication is for
        handle (int): An integer handle that should be passed to "Cancel"
    """
    global AUTH_DIALOG

    def cancel(handle, server):
        """Callback function while authentication dialog closed or cancel button pressed.
        Args:
            server (str): A string indicating the host name that the authentication is for
            handle (int): An integer handle that should be passed to "Cancel"
        """
        global AUTH_DIALOG
        try:
            AUTH_DIALOG.destroy()
        except Exception:
            # The dialog might have been destroyed already.
            pass
        AUTH_DIALOG = None
        omni.client.authentication_cancel(handle)
        LOGGER.warning(rf"Sign in to {server} canceled.")

    def get_dialog_pop_pos():
        """Get screen x,y coordinate where the dialog should popup.
        It should pop up near the main Houdini app Window.
        """
        main_window = hou.qt.mainWindow()
        pos = (main_window.pos() + QtCore.QPoint(main_window.width(), main_window.height())) / 2
        return pos.x(), pos.y()

    if show:
        LOGGER.info(rf"Please sign in to {server} using your browser.")
        try:
            AUTH_DIALOG = tk.Tk()
        except Exception:
            LOGGER.warning("Unable to open Omniverse sign in cancellation dialog. tkinter not installed properly?")
            return

        # Hide root window
        AUTH_DIALOG.withdraw()

        top = tk.Toplevel(AUTH_DIALOG)
        top.title(rf"Connecting to {server}")
        pos_x, pos_y = get_dialog_pop_pos()
        top.geometry(f"320x100+{pos_x}+{pos_y}")
        # Close the dialog
        top.protocol("WM_DELETE_WINDOW", partial(cancel, handle, server))
        # Use omni icon
        icon_path = os.path.join(os.environ.get("HOMNI", "."), "houdini", "config", "Icons", "nvidia-omniverse.ico")
        if os.path.exists(icon_path):
            top.iconbitmap(icon_path)

        # Disable resize
        top.resizable(False, False)

        # Text
        label = tk.Label(top, text=f"Connecting to {server}\nPlease sign in using your browser")
        label.pack()
        label.place(relx=0.23, rely=0.1)

        # Cancel button
        cancel_button = tk.Button(top, text="Cancel")
        cancel_button["command"] = partial(cancel, handle, server)
        cancel_button.pack()
        cancel_button.place(relx=0.43, rely=0.6)
        AUTH_DIALOG.mainloop()

    if AUTH_DIALOG:
        try:
            AUTH_DIALOG.destroy()
        except Exception:
            # The dialog might have been destroyed already.
            pass
        AUTH_DIALOG = None


def setup_expression_globals():
    """Set Houdini expression globals"""
    hou.expressionGlobals()["omni.client"] = omni.client
    hou.expressionGlobals()["homni.utils"] = utils


def hide_experimental_nodes():
    """Hide Experimental nodes"""
    if str(os.environ.get("HOMNI_ENABLE_EXPERIMENTAL")) != "1":
        hou.hscript("ophide Lop omni_liveeditbreak")
        hou.hscript("ophide Lop omni_live_sync")


def safe_execute(func):
    """Helper function to call given arg - func, and handle errors without stopping continue the rest of pythonrc.py

    Args:
        func (callable): Callable to execute.
    """
    try:
        func()
    except (Exception, hou.Error):
        LOGGER.error(f"{traceback.format_exc()}\nError executing Omniverse pythonrc.py. Function - {func.__name__}")


if hou.isUIAvailable():
    # Override the default cancel login dialog to prevent a houdini lock
    safe_execute(partial(omni.client.set_authentication_message_box_callback, omni_auth_cb))

# Setup Houdini expression globals
safe_execute(setup_expression_globals)

# Hide Experimental nodes
safe_execute(hide_experimental_nodes)
