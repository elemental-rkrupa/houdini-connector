# SPDX-FileCopyrightText: Copyright (c) 2020-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import os

import hou
import husd.outputprocessor as base
from homni import logging
from omni import client

LOGGER = logging.get_homni_logger()


class OmniStatOutputProcessor(base.OutputProcessor):
    """
    Queries file information for every path that is processed for save
    and logs a warning for any file that doesn't allow write access or that
    doesn't exist after the save, to help detect failures when saving to
    the Omniverse server.

    IMPORTANT:  This processor must always be the last in the list of outuput
    processors on the USD ROP, to ensure that OmniStatOutputProcessor.processAsset()
    is called with the final versions of the outupt ptahs, after every other processor
    has been applied.
    """

    theParameters = None
    theErrorToggleParmName = "omnistat_error"

    def __init__(self):
        """There is only one object of each output processor class that is
        ever created in a Houdini session. Therefore be very careful
        about what data gets put in this object.
        """
        super(OmniStatOutputProcessor, self).__init__()
        # Whether to raise an error for missing files.
        self.raise_error = False
        self.savedPaths = set()

    @staticmethod
    def name():
        return "omnistat"

    @staticmethod
    def displayName():
        return "Stat Omniverse Paths"

    def flagError(self, err_msg):
        """
        Logs the given error message to standard out or raises
        an error, depending on the user's preference.
        """
        if self.raise_error:
            raise hou.OperationFailed(err_msg)
        else:
            LOGGER.error(err_msg)

    @staticmethod
    def parameters():
        if not OmniStatOutputProcessor.theParameters:
            parameters = hou.ParmTemplateGroup()
            errortoggleparm = hou.ToggleParmTemplate(
                OmniStatOutputProcessor.theErrorToggleParmName, "Error on Inaccessible or Missing Outputs", False
            )
            parameters.append(errortoggleparm)
            OmniStatOutputProcessor.theParameters = parameters.asDialogScript()
        return OmniStatOutputProcessor.theParameters

    def processReferencePath(self, asset_path, referencing_layer_path, asset_is_layer):
        asset_path = super(OmniStatOutputProcessor, self).processReferencePath(
            asset_path, referencing_layer_path, asset_is_layer
        )
        return self.processAsset(asset_path, "", referencing_layer_path, asset_is_layer, for_save=False)

    def processSavePath(self, asset_path, referencing_layer_path, asset_is_layer):
        asset_path = super(OmniStatOutputProcessor, self).processSavePath(
            asset_path, referencing_layer_path, asset_is_layer
        )
        return self.processAsset("", asset_path, referencing_layer_path, asset_is_layer, for_save=True)

    def processAsset(self, asset_path, asset_path_for_save, referencing_layer_path, asset_is_layer, for_save):
        if for_save:
            self.savedPaths.add(asset_path)

            # Check if we have write access.
            stat_info = client.stat(asset_path)

            if stat_info[0] == client.Result.OK and (stat_info[1].access & client.AccessFlags.WRITE == 0):
                msg = "WARNING: No write permission to save {0} to {1}.".format(self.config_node.path(), asset_path)
                self.flagError(msg)

        return asset_path

    def beginSave(self, config_node, config_overrides, *args, **kwargs):
        """Note that the *args are different between Houdini 19.0 and 19.5
        19.0:
            (t, )
        19.5:
            (lop_node, t,)
        """
        super(OmniStatOutputProcessor, self).beginSave(config_node, config_overrides, *args, **kwargs)
        self.raise_error = False
        self.savedPaths.clear()

        # Check for the toggle parameter to enable errors.
        errortoggleparm = config_node.parm(self.theErrorToggleParmName)
        if errortoggleparm:
            self.raise_error = errortoggleparm.evalAsInt()

    def endSave(self):
        super(OmniStatOutputProcessor, self).endSave()
        # Stat the paths that were processed for saves, to help detect write failures.
        for path in self.savedPaths:
            stat_info = client.stat(path)
            if stat_info[0] != client.Result.OK:
                msg = "WARNING: Couldn't stat file {0} saved from {1}.  HINT: Make sure the server name is valid, that you have write permissions for the given path, and that there were no other errors on the ROP.".format(
                    path, self.config_node.path()
                )
                self.flagError(msg)

        self.raise_error = False
        self.savedPaths.clear()


outputprocessor = OmniStatOutputProcessor
major, minor, _ = hou.applicationVersion()
# After Houdini 19.5, we only return a OutputProcessor Object (v.s instance before 19.5)
if major * 10 + minor < 195:
    # Must have: module-level function to return a processor instance
    outputprocessor = outputprocessor()


def usdOutputProcessor():
    return outputprocessor
