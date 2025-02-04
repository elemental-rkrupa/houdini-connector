# SPDX-FileCopyrightText: Copyright (c) 2020-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


import logging
import os
import re

import hou
import husd.outputprocessor as base
from homni import client as hclient
from homni import logging as hlogging
from omni import client
from pxr import Sdf

LOGGER = hlogging.get_homni_logger()


class OmniMDLPropertiesOutputProcessor(base.OutputProcessor):
    """
    Converted the relative or flattened MDL paths to Search Path format.
    If path exists, it copies the mdl from source location to a './mdls' directory which is a
    sibling of the referencing USD file and update the MDL property to a relative path,
    otherwise it updates it to following -
    For example:
        @./OmniPBR.mdl@ -> @OmniPBR.mdl@
        @/some/where/OmniPBR.mdl@ -> @OmniPBR.mdl@

    """

    theParameters = None
    theOverwriteToggleParmName = "OmniMDLProperties_overwrite"
    theCopyAllMDLsToggleParmName = "OmniMDLProperties_copyallmdls"
    theVerboseToggleParmName = "OmniMDLProperties_verbose"
    theExcludePathsParmName = "OmniMDLProperties_excludepaths"
    theExcludePathParmName = "OmniMDLProperties_excludepath"

    # List of mdl extensions.
    theMDLExtensions = (".mdl",)

    def __init__(self):
        """There is only one object of each output processor class that is
        ever created in a Houdini session. Therefore be very careful
        about what data gets put in this object.
        """
        super().__init__()
        self.initProperties()

    @staticmethod
    def name():
        return "omnimdlproperties"

    @staticmethod
    def displayName():
        return "Omniverse Handle MDL Properties"

    def initProperties(self):
        self.exclude_paths = []
        self.verbose = False
        self.saved_files = set()
        self.saved_dirs = set()
        self.overwrite = False
        self.copyallmdls = True

    @staticmethod
    def parameters():
        """
        Returns a string containing Houdini dialog script describing the
        parameters this processor shows to the user for configuration. You can
        generate the dialog script by building up a `hou.ParmTemplateGroup`
        with `hou.ParmTemplate` objects inside, and then returning the value
        from `hou.ParmTemplateGroup.asDialogScript()`::

            group = hou.ParmTemplateGroup()
            group.append(hou.StringParmTemplate(
                "texturedir",
                "Texture Directory",
                string_type=hou.stringParmType.FileReference
            ))
            return group.asDialogScript()

        The default implementation returns the script for an empty parameter
        group, so if your processor doesn't need any parameters, you don't need
        to override this method.

        The internal names of any parameters you create here must be unique
        among all other parameters on the render node, so you probably want to
        use a naming scheme like `<modulename>_<parmname>`.
        """
        if not OmniMDLPropertiesOutputProcessor.theParameters:
            parameters = hou.ParmTemplateGroup()
            # Help Card
            helpcardlabelparm = hou.LabelParmTemplate(
                "OmniMDLProperties_help",
                "Message",
                column_labels=(
                    [
                        "Copy and converted the MDL path to the target output path.\n"
                        "If the source mdl path exists, it copies the mdl from the source location to\n"
                        "a './mdls' directory which is a sibling of the referencing USD file and update\n"
                        "the MDL property to a relative path, otherwise it updates the MDL property\n"
                        "For example:\n"
                        "    @./OmniPBR.mdl@ -> @OmniPBR.mdl@\n"
                        "    @/some/where/OmniPBR.mdl@ -> @OmniPBR.mdl@\n"
                    ]
                ),
            )
            helpcardlabelparm.setTags({"sidefx::look": "block"})
            parameters.append(helpcardlabelparm)

            # Verbose
            verbosetoggleparm = hou.ToggleParmTemplate(
                OmniMDLPropertiesOutputProcessor.theVerboseToggleParmName, "Verbose Output", False
            )
            parameters.append(verbosetoggleparm)

            # Overwrite
            overwritetoggleparm = hou.ToggleParmTemplate(
                OmniMDLPropertiesOutputProcessor.theOverwriteToggleParmName, "Overwrite Existing MDLs", False
            )
            overwritetoggleparm.setHelp("Overwrite the existing mdl files at the target location.")
            parameters.append(overwritetoggleparm)

            # Copy All MDLs
            copyallmdlstoggleparm = hou.ToggleParmTemplate(
                OmniMDLPropertiesOutputProcessor.theCopyAllMDLsToggleParmName,
                "Copy All MDLs from Discovered Directories",
                True,
            )
            copyallmdlstoggleparm.setHelp(
                "Copy all *.mdl files from the referenced mdl directories. Enable this option if you have mdls that "
                "are not used directly in the USD scene. For example, A mdl references/imports other mdls."
            )

            parameters.append(copyallmdlstoggleparm)

            # Exclude paths
            excludepathsparm = hou.FolderParmTemplate(
                OmniMDLPropertiesOutputProcessor.theExcludePathsParmName,
                "Skip Paths",
                folder_type=hou.folderType.MultiparmBlock,
            )
            excludepathsparm.setTags({"multistartoffset": "0"})
            excludepathsparm.setHelp(
                "Output processor will skip processing the mdl property value if the value "
                "matches this parm. This can be a regex syntax"
            )
            # Code for exclude path parameter template
            excludepathparm = hou.StringParmTemplate(
                f"{OmniMDLPropertiesOutputProcessor.theExcludePathParmName}#", "Exclude Path", 1
            )
            excludepathparm.setHelp(
                "Output processor will skip processing the mdl property value if the value "
                "matches this parm. This can be a regex syntax"
            )
            excludepathsparm.addParmTemplate(excludepathparm)
            parameters.append(excludepathsparm)

            OmniMDLPropertiesOutputProcessor.theParameters = parameters.asDialogScript()
        return OmniMDLPropertiesOutputProcessor.theParameters

    def processReferencePath(self, asset_path, referencing_layer_path, asset_is_layer):
        """
        Called when the render node needs to write a file path pointing to an
        asset (to sublayer or reference in the file).

        For example, if the render node is writing out `A.usd` and `B.usd`,
        where `A` references in `B`:

        1. It will first call `processSavePath()` to compute where to save
           `B.usd`. Say it calls `processSavePath("B.usd", True)`, and that
           method returns "/Users/aisha/project/usd/B.usd".

        2. As it writes out `A.usd`, when it gets to the part where it refers
           to `B.usd`, it will call this method to compute the file path
           string to use to refer to the asset in the file being written.
           `processReferencePath("/Users/aisha/project/usd/B.usd",
           "/Users/aisha/project/usd/A.usd", True)`. To make the file path
           relative, you could return the result of
           `hou.text.relpath(asset_path, referencing_layer_path)`

        :param asset_path: The path to the asset, as specified in Houdini.
            If this asset is being written to disk, this will be the final
            output of the `processSavePath()` calls on all output
            processors.
        :param referencing_layer_path: The absolute file path of the file
            containing the reference to the asset. You can use this to make
            the path pointer relative.
        :param asset_is_layer: A boolean value indicating whether this asset is
            a USD layer file. If this is `False`, the asset is something else
            (for example, a texture or volume file).
        """
        asset_path = super().processReferencePath(asset_path, referencing_layer_path, asset_is_layer)
        return self.processAsset(asset_path, "", referencing_layer_path, asset_is_layer, for_save=False)

    def processSavePath(self, asset_path, referencing_layer_path, asset_is_layer):
        """
        Called when the render node needs to determine where on disk to save
        an asset. The `asset_path` is the file path as Houdini knows it
        (for example, from USD metadata or a Houdini parameter).

        If you return a value from this method, it should be an absolute path
        to the location on disk where the asset should be saved.

        (If you return a relative path from this method, it will be relative to
        the current directory (`os.getcwd()`) which is probably not what you
        want.)

        :param asset_path: The path to the asset, as specified in Houdini.
            This string comes with expressions and environment variables (such
            as `$HIP`) expanded already, so if you want to compare to another
            path, you should also expand that path (for example, with
            `os.path.expandvars()` or `hou.text.expandString()`).
        :param referencing_layer_path: The absolute file path of the file
            containing the reference to the asset, if the asset_path refers
            to a non-layer asset such as a volume file. You can use this to
            create a save path that is in a particular location relative to
            the referencing file.
        :param asset_is_layer: A boolean value indicating whether this asset is
            a USD layer file. If this is `False`, the asset is something else
            (for example, a texture or volume file).
        """
        asset_path = super().processSavePath(asset_path, referencing_layer_path, asset_is_layer)
        return self.processAsset("", asset_path, referencing_layer_path, asset_is_layer, for_save=True)

    def copyMdl(self, src_path, dst_path):
        # source not exist
        if client.stat(src_path)[0] != client.Result.OK:
            return False

        if dst_path in (saved_dest for _, saved_dest in self.saved_files):
            if self.verbose:
                LOGGER.info(rf"{dst_path} has already been saved, skip.")
            return True

        if src_path == dst_path:
            if self.verbose:
                LOGGER.info(rf"Source mdl - {src_path} and destination paths are equal, skipping export.")
            # Source and destination are the same, do nothing.
            return True

        if not self.overwrite and client.stat(dst_path)[0] == client.Result.OK:
            # We are not allowed to overwrite and the file already exists, do nothing.
            if self.verbose:
                LOGGER.warning(rf"{dst_path} already exists, skipping export.")
            return True

        if self.verbose:
            # On Windows normalized paths will contain backslashes. This can cause errors when
            # logging.  For example, '\Users' will be interpreted as an invalid unicode escape
            # starting with '\U', generating a 'unicodeescape' error when attempting to log.
            # For this reason, we use raw string for logging.
            LOGGER.info(rf"Saving mdl {src_path} to {dst_path}.")

        behavior = client.CopyBehavior.OVERWRITE if self.overwrite else client.CopyBehavior.ERROR_IF_EXISTS
        result = client.copy(src_path, dst_path, behavior)

        if result == client.Result.OK:
            self.saved_files.add((src_path, dst_path))
            return True
        else:
            LOGGER.error(rf"Failed saving mdl {src_path} to {dst_path} - {result}")
            return False

    def copyMdlsInDir(self, src_dir, dst_dir):
        if src_dir in self.saved_dirs:
            return
        for entry in client.list(src_dir)[1]:
            mdl_basename = entry.relative_path
            if not mdl_basename.endswith(".mdl"):
                continue
            src_path = client.normalize_url(hou.text.normpath(os.path.join(src_dir, mdl_basename)))
            dst_path = client.normalize_url(hou.text.normpath(os.path.join(dst_dir, mdl_basename)))
            self.copyMdl(src_path, dst_path)
        self.saved_dirs.add(src_dir)

    def handleMdl(self, mdl_src_path, referencing_layer_path):
        src_path = client.normalize_url(hou.text.normpath(mdl_src_path))
        dst_path = client.normalize_url(
            hou.text.normpath(
                os.path.join(os.path.dirname(referencing_layer_path), "materials", "mdls", os.path.basename(src_path))
            )
        )
        relative_dst_path = client.make_relative_url(referencing_layer_path, dst_path)

        if dst_path in (saved_dest for _, saved_dest in self.saved_files):
            if self.verbose:
                LOGGER.info(rf"{dst_path} has already been saved, skip.")
            return relative_dst_path

        # src exists
        if client.stat(src_path)[0] == client.Result.OK:
            if self.copyallmdls:
                self.copyMdlsInDir(os.path.dirname(src_path), os.path.dirname(dst_path))

            return relative_dst_path if self.copyMdl(src_path, dst_path) else None

    def processAsset(self, asset_path, asset_path_for_save, referencing_layer_path, asset_is_layer, for_save):
        """This is for H19.0 backward compatible."""
        dest_path = None
        if not asset_is_layer and not for_save and os.path.dirname(asset_path) and referencing_layer_path:
            abs_asset_path = hou.text.abspath(
                hou.text.normpath(asset_path), hou.text.normpath(os.path.dirname(referencing_layer_path))
            )
            # Get the asset extension.
            ext_split = os.path.splitext(abs_asset_path)
            if not ext_split[1].lower() in self.theMDLExtensions:
                # This isn't a mdl value in our list so return path unchanged.
                return asset_path

            # Check if asset_path in exclude paths
            for path in self.exclude_paths:
                if not re.search(path, abs_asset_path):
                    continue
                if self.verbose:
                    LOGGER.info(f"Skip converting mdl property value - {abs_asset_path}. " f"Exclude path rule {path}")
                return asset_path

            referencing_layer_path = Sdf.Layer.SplitIdentifier(referencing_layer_path)[0]
            dest_path = self.handleMdl(abs_asset_path, referencing_layer_path)

        return dest_path if dest_path else asset_path

    def beginSave(self, config_node, config_overrides, *args, **kwargs):
        """
        Called when a node using this processor starts to write out files.
        This gives you the chance to read parameter values (either the
        configuration parameters added by `parameters()`, or the node's own
        parameters, depending on what information you need).

        :param config_node: A `hou.Node` object representing the node.
        :param config_overrides: A `dict` of values that should be used to
            override whatever may be set on the node. See `evalConfig()`.
        :param t: A floating point value representing the time (in seconds)
            along the timeline which the node is rendering. If you read
            parameter values from the node, you should use `Parm.evalAtTime(t)`
            in case the parameter is animated.

        Note that the *args are different between Houdini 19.0 and 19.5
        19.0:
            (t, )
        19.5:
            (lop_node, t,)
        """
        super().beginSave(config_node, config_overrides, *args, **kwargs)
        self.initProperties()

        # Check for the overwrite toggle parameters.
        overwritetoggleparm = config_node.parm(self.theOverwriteToggleParmName)
        if overwritetoggleparm:
            self.overwrite = overwritetoggleparm.evalAsInt()

        # Check for the overwrite toggle parameters.
        copyallmdlstoggleparm = config_node.parm(self.theCopyAllMDLsToggleParmName)
        if copyallmdlstoggleparm:
            self.copyallmdls = copyallmdlstoggleparm.evalAsInt()

        # Check for the verbose parm
        verbosetoggleparm = config_node.parm(self.theVerboseToggleParmName)
        if verbosetoggleparm:
            self.verbose = verbosetoggleparm.evalAsInt()
            # verbose is on - turn LOGGER level to debug.
            if self.verbose:
                hlogging.set_level(LOGGER, logging.DEBUG, handler_types=(logging.StreamHandler,))

        if self.verbose:
            LOGGER.info("Omniverse MDL Properties Handler BEGIN")

        # Get all exclude path strings
        excludepathsparm = config_node.parm(self.theExcludePathsParmName)
        if excludepathsparm:
            for idx in range(excludepathsparm.evalAsInt()):
                excludepathparm = config_node.parm(f"{self.theExcludePathParmName}{idx}")
                if not excludepathparm:
                    continue
                exclude_str = excludepathparm.evalAsString()
                if not exclude_str:
                    continue
                self.exclude_paths.append(hou.text.normpath(exclude_str))

    def endSave(self):
        try:
            super().endSave()
        except AttributeError:
            pass

        if self.verbose:
            if self.saved_files:
                values = ""
                for source_path, result_path in self.saved_files:
                    values += f"\t{source_path} -> {result_path}\n"
                LOGGER.info(f"Exported mdl files:\n{values}")
            LOGGER.info("Omniverse MDL Properties Handler END")

            # Set back LOGGER level
            hlogging.set_level(LOGGER, int(hclient.getLogLevel()) * 10, handler_types=(logging.StreamHandler,))

        # Reset all property values
        self.initProperties()

    def __del__(self):
        """Called when the render node finishing outputting files."""
        self.endSave()
        try:
            super().__del__()
        except AttributeError:
            pass


outputprocessor = OmniMDLPropertiesOutputProcessor
major, minor, _ = hou.applicationVersion()
# After Houdini 19.5, we only return a OutputProcessor Object (v.s instance before 19.5)
if major * 10 + minor < 195:
    # Must have: module-level function to return a processor instance
    outputprocessor = outputprocessor()


def usdOutputProcessor():
    return outputprocessor
