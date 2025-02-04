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

import hou
import husd.outputprocessor as base
from homni import client as hclient
from homni import logging as hlogging
from omni import client

LOGGER = hlogging.get_homni_logger()


class OmniSimpleRelativePathsOutputProcessor(base.OutputProcessor):
    theParameters = None
    theVerboseToggleParmName = "OmniSimpleRelativePaths_verbose"

    def __init__(self):
        """There is only one object of each output processor class that is
        ever created in a Houdini session. Therefore be very careful
        about what data gets put in this object.
        """
        super().__init__()
        self.initProperties()

    def initProperties(self):
        self.verbose = False

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
        if not OmniSimpleRelativePathsOutputProcessor.theParameters:
            parameters = hou.ParmTemplateGroup()

            # Verbose
            verbosetoggleparm = hou.ToggleParmTemplate(
                OmniSimpleRelativePathsOutputProcessor.theVerboseToggleParmName, "Verbose Output", False
            )
            parameters.append(verbosetoggleparm)

            OmniSimpleRelativePathsOutputProcessor.theParameters = parameters.asDialogScript()
        return OmniSimpleRelativePathsOutputProcessor.theParameters

    @staticmethod
    def name():
        return "OmniSimplerelativepaths"

    @staticmethod
    def displayName():
        return "Omniverse Use Relative Paths"

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

    def processAsset(self, asset_path, asset_path_for_save, referencing_layer_path, asset_is_layer, for_save):
        """This is for H19.0 backward compatible."""
        # We don't do anything if it is a reference path already. Users knows what they are doing.
        if asset_path.startswith("./") or asset_path.startswith("../"):
            return asset_path

        # All referencing paths should be expressed as relative to the
        # referencing layer.
        # We use Omni client api to handle relative omniverse url
        if hclient.isOmniversePath(asset_path):
            new_asset_path = client.make_relative_url(referencing_layer_path, asset_path)
        else:
            new_asset_path = hou.text.relpath(asset_path, referencing_layer_path)

        if self.verbose and new_asset_path != asset_path:
            LOGGER.info(
                f"Cenerated relative output path - {new_asset_path} from {asset_path}. "
                f"Based path - {referencing_layer_path}."
            )
        return new_asset_path

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

        # Check for the verbose parm
        verbosetoggleparm = config_node.parm(self.theVerboseToggleParmName)
        if verbosetoggleparm:
            self.verbose = verbosetoggleparm.evalAsInt()
            # verbose is on - turn LOGGER level to debug.
            if self.verbose:
                hlogging.set_level(LOGGER, logging.DEBUG, handler_types=(logging.StreamHandler,))

        if self.verbose:
            LOGGER.info("Omniverse Simple Relative Paths Output Processor BEGIN")

    def endSave(self):
        try:
            super().endSave()
        except AttributeError:
            pass

        if self.verbose:
            LOGGER.info("Omniverse Simple Relative Paths Output Processor END")

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


outputprocessor = OmniSimpleRelativePathsOutputProcessor
major, minor, _ = hou.applicationVersion()
# After Houdini 19.5, we only return a OutputProcessor Object (v.s instance before 19.5)
if major * 10 + minor < 195:
    # Must have: module-level function to return a processor instance
    outputprocessor = outputprocessor()


def usdOutputProcessor():
    return outputprocessor
