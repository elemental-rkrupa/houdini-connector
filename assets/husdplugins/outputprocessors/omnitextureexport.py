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


class OmniTextureExportOutputProcessor(base.OutputProcessor):
    """
    Saves texture assets to a 'materials/textures' directory which is
    a sibling of the referencing USD file.
    """

    theParameters = None
    theOverwriteToggleParmName = "OmniTextureExport_overwrite"
    theVerboseToggleParmName = "OmniTextureExport_verbose"

    # List of supported texture extensions.
    theTextureExtensions = (
        ".bmp",
        ".dds",
        ".exr",
        ".gif",
        ".hdr",
        ".jpeg",
        ".jpg",
        ".png",
        ".psd",
        ".tga",
        ".rat",
        ".pic",
    )

    # List of unsupported paths syntax.
    # Consideration: We should glob all udim texture files and upload them to omniverse. Skip udim for now.
    unsupportedRegex = (r".*(\.<UDIM>\.).*",)

    def __init__(self):
        """There is only one object of each output processor class that is
        ever created in a Houdini session. Therefore be very careful
        about what data gets put in this object.
        """
        super().__init__()
        self.initProperties()

    @staticmethod
    def name():
        return "omnitextureexport"

    @staticmethod
    def displayName():
        return "Omniverse Texture Export"

    def initProperties(self):
        self.overwrite = False
        self.verbose = False
        self.saved_files = set()

    @staticmethod
    def parameters():
        if not OmniTextureExportOutputProcessor.theParameters:
            parameters = hou.ParmTemplateGroup()

            # Help Card
            helpcardlabelparm = hou.LabelParmTemplate(
                "OmniTextureExport_help",
                "Message",
                column_labels=(
                    [
                        "Saves texture assets to a 'materials/textures' directory which is a sibling of the\n"
                        "referencing USD file.\n"
                    ]
                ),
            )
            helpcardlabelparm.setTags({"sidefx::look": "block"})
            parameters.append(helpcardlabelparm)

            overwritetoggleparm = hou.ToggleParmTemplate(
                OmniTextureExportOutputProcessor.theOverwriteToggleParmName, "Overwrite Existing Files", False
            )
            parameters.append(overwritetoggleparm)

            verbosetoggleparm = hou.ToggleParmTemplate(
                OmniTextureExportOutputProcessor.theVerboseToggleParmName, "Verbose Output", False
            )
            parameters.append(verbosetoggleparm)

            OmniTextureExportOutputProcessor.theParameters = parameters.asDialogScript()
        return OmniTextureExportOutputProcessor.theParameters

    def saveTexture(self, src_path, dst_path):

        if self.verbose:
            LOGGER.info(rf"Attempting to save {src_path} to {dst_path}.")

        if hou.text.abspath(src_path) == hou.text.abspath(dst_path):
            if self.verbose:
                LOGGER.warning("Source and destination paths are equal, skipping export.")
            # Source and destination are the same, do nothing.
            return

        norm_dst = client.normalize_url(dst_path)

        if norm_dst in self.saved_files:
            if self.verbose:
                LOGGER.warning("Destination has already been saved, skipping export.")
            return

        dst_url = client.break_url(norm_dst)

        # Only handle 'omniverse' or empty schemes. This is
        # to avoid trying to write to a scheme we can't stat.
        if dst_url.scheme and dst_url.scheme != "omniverse":
            if self.verbose:
                LOGGER.warning("Skipping saving to path with unsupported scheme.")
            return

        norm_src = client.normalize_url(src_path)

        if norm_src == norm_dst:
            if self.verbose:
                LOGGER.warning("Source and destination paths are equal, skipping export.")
            # Source and destination are the same, do nothing.
            return

        if not self.overwrite and client.stat(norm_dst)[0] == client.Result.OK:
            # We are not allowed to overwrite and the file already exists, do nothing.
            if self.verbose:
                LOGGER.warning("Destination file already exists, skipping export.")
            return

        if self.verbose:
            # On Windows normalized paths will contain backslashes. This can cause errors when
            # logging.  For example, '\Users' will be interpreted as an invalid unicode escape
            # starting with '\U', generating a 'unicodeescape' error when attempting to log.
            # For this reason, we use raw string for logging.
            LOGGER.info(rf"Saving texture {norm_src} to {norm_dst}.")

        if norm_src.startswith("opdef:"):
            file_buf = hou.readBinaryFile(norm_src)
            result = client.write_file(norm_dst, file_buf)
        else:
            behavior = client.CopyBehavior.OVERWRITE if self.overwrite else client.CopyBehavior.ERROR_IF_EXISTS
            result = client.copy(norm_src, norm_dst, behavior)

        if result == client.Result.OK:
            self.saved_files.add(norm_dst)
        else:
            LOGGER.error(rf"Failed saving texture {norm_src} to {norm_dst} - {result}")

    def processReferencePath(self, asset_path, referencing_layer_path, asset_is_layer):
        asset_path = super().processReferencePath(asset_path, referencing_layer_path, asset_is_layer)
        return self.processAsset(asset_path, "", referencing_layer_path, asset_is_layer, for_save=False)

    def processSavePath(self, asset_path, referencing_layer_path, asset_is_layer):
        asset_path = super().processSavePath(asset_path, referencing_layer_path, asset_is_layer)
        return self.processAsset("", asset_path, referencing_layer_path, asset_is_layer, for_save=True)

    def processAsset(self, asset_path, asset_path_for_save, referencing_layer_path, asset_is_layer, for_save):
        if not asset_is_layer and not for_save and referencing_layer_path:
            referencing_layer_path = Sdf.Layer.SplitIdentifier(referencing_layer_path)[0]

            # Get the asset extension.
            ext_split = os.path.splitext(asset_path)
            if not ext_split[1].lower() in self.theTextureExtensions:
                # This isn't an image type in our list so return path unchanged.
                return asset_path

            # Unsupported texture path
            for regex in self.unsupportedRegex:
                if re.match(regex, asset_path):
                    if self.verbose:
                        LOGGER.warning(
                            rf"Skip Exporting {asset_path} referenced by {referencing_layer_path}. "
                            rf"Unsupported file syntax: {regex}"
                        )
                    return asset_path

            if self.verbose:
                LOGGER.info(rf"Exporting {asset_path} referenced by {referencing_layer_path}.")

            if asset_path.startswith("opdef:"):
                # This is an embedded file.
                # Replace the '?' in the filename with an underscore.
                file_name = os.path.basename(asset_path.replace("?", "_"))
            else:
                file_name = os.path.basename(asset_path)

            target_dir = os.path.dirname(referencing_layer_path)

            if not file_name:
                # This shouldn't happen.
                LOGGER.warning(rf"Couldn't get filename for asset {asset_path}.")
                return asset_path

            if not target_dir:
                # This shouldn't happen.
                LOGGER.warning(
                    rf"Couldn't get target directory for asset {asset_path} "
                    "with referencing layer {referencing_layer_path}."
                )
                return asset_path

            abs_asset_path = hou.text.abspath(
                hou.text.normpath(asset_path), hou.text.normpath(os.path.dirname(referencing_layer_path))
            )

            dst_path = client.normalize_url(
                hou.text.normpath(os.path.join(target_dir, "materials", "textures", file_name))
            )
            result_path = client.make_relative_url(referencing_layer_path, dst_path)

            if self.verbose:
                LOGGER.info(rf"Returning relative path {result_path}.")

            stat_result = client.stat(abs_asset_path)[0]
            if stat_result == client.Result.OK:
                self.saveTexture(abs_asset_path, dst_path)
                return result_path
            elif self.verbose:
                if stat_result == client.Result.ERROR_NOT_FOUND:
                    LOGGER.error(rf"Skip saving texture - {abs_asset_path} does not exist.")
                else:
                    LOGGER.error(rf"{stat_result}. Texture not saved - {abs_asset_path}")

        return asset_path

    def beginSave(self, config_node, config_overrides, *args, **kwargs):
        """Note that the *args are different between Houdini 19.0 and 19.5
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

        # Check for the verbose parm
        verbosetoggleparm = config_node.parm(self.theVerboseToggleParmName)
        if verbosetoggleparm:
            self.verbose = verbosetoggleparm.evalAsInt()
            # verbose is on - turn LOGGER level to debug.
            if self.verbose:
                hlogging.set_level(LOGGER, logging.DEBUG, handler_types=(logging.StreamHandler,))

        if self.verbose:
            LOGGER.info("Omniverse Texture Export BEGIN SAVE")

    def endSave(self):
        try:
            super().endSave()
        except AttributeError:
            pass

        if self.verbose:
            if self.saved_files:
                LOGGER.info("Saved texture files:\n" rf"{self.saved_files}")
            else:
                LOGGER.info("No textures were saved")
            LOGGER.info("Omniverse Texture Export END SAVE")

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


outputprocessor = OmniTextureExportOutputProcessor
major, minor, _ = hou.applicationVersion()
# After Houdini 19.5, we only return a OutputProcessor Object (v.s instance before 19.5)
if major * 10 + minor < 195:
    # Must have: module-level function to return a processor instance
    outputprocessor = outputprocessor()


def usdOutputProcessor():
    return outputprocessor
