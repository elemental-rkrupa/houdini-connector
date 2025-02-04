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
from homni import logging as hlogging
from pxr import Sdf

LOGGER = hlogging.get_homni_logger()


class OmniUsdFormatOutputProcessor(base.OutputProcessor):
    """
    Underlying file format for output files with the extension '.usd'.
    For example:
        (usda) output.usd -> Saved as ASCII
        (usdc) output.usd -> Saved as Binary
    """

    theParameters = None
    theUsdFormatParmName = "OmniUsdFormat_usdformat"

    def __init__(self):
        """There is only one object of each output processor class that is
        ever created in a Houdini session. Therefore be very careful
        about what data gets put in this object.
        """
        super().__init__()
        self.initProperties()

    @staticmethod
    def name():
        return "omniusdformat"

    @staticmethod
    def displayName():
        return "Omniverse USD Format"

    def initProperties(self):
        self.usdformat = "usdc"

    @staticmethod
    def parameters():
        """
        Returns a string containing Houdini dialog script describing the
        parameters this processor shows to the user for configuration. You can
        generate the dialog script by building up a `hou.ParmTemplateGroup`
        with `hou.ParmTemplate` objects inside, and then returning the value
        from `hou.ParmTemplateGroup.asDialogScript()`:

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
        if not OmniUsdFormatOutputProcessor.theParameters:
            parameters = hou.ParmTemplateGroup()

            # Help Card
            helpcardlabelparm = hou.LabelParmTemplate(
                "OmniUsdFormat_help",
                "Message",
                column_labels=(
                    [
                        "Underlying file format for output files with the extension '.usd'.\n"
                        "For example:\n"
                        "    (usda) output.usd -> Saved as ASCII\n"
                        "    (usdc) output.usd -> Saved as Binary\n"
                    ]
                ),
            )
            helpcardlabelparm.setTags({"sidefx::look": "block"})
            parameters.append(helpcardlabelparm)

            usdformatparm = hou.MenuParmTemplate(
                OmniUsdFormatOutputProcessor.theUsdFormatParmName,
                "USD Format",
                menu_items=(["usdc", "usda"]),
                menu_labels=(["Binary (usdc)", "ASCII (usda)"]),
                default_value=0,
                menu_type=hou.menuType.Normal,
            )
            usdformatparm.setHelp(
                "Underlying USD file format for output files with the extension '.usd'.\n"
                "For example:\n"
                "    (usda) output.usd -> Saved as ASCII\n"
                "    (usdc) output.usd -> Saved as Binary\n"
                "Note that by default USD files with '.usd' extension will be saved as ASCII in Nucleus "
                "if this option is disabled."
            )
            parameters.append(usdformatparm)
            OmniUsdFormatOutputProcessor.theParameters = parameters.asDialogScript()
        return OmniUsdFormatOutputProcessor.theParameters

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

    def processAsset(self, asset_path, asset_path_for_save, referencing_layer_path, asset_is_layer, for_save):
        """This is for H19.0 backward compatible."""
        if asset_is_layer and os.path.splitext(asset_path_for_save)[-1] == ".usd":
            asset_path_for_save = Sdf.Layer.CreateIdentifier(asset_path_for_save, {"format": self.usdformat})
        return asset_path_for_save

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
        LOGGER.debug("Omniverse USD FORMAT BEGIN")
        super().beginSave(config_node, config_overrides, *args, **kwargs)
        self.initProperties()

        # Get usdformat parm value
        usdformatparm = config_node.parm(OmniUsdFormatOutputProcessor.theUsdFormatParmName)
        if usdformatparm:
            self.usdformat = usdformatparm.evalAsString()

    def endSave(self):
        try:
            super().endSave()
        except AttributeError:
            pass

        # Reset all property values
        self.initProperties()

        LOGGER.debug("Omniverse USD DEFAULT FORMAT END")

    def __del__(self):
        """Called when the render node finishing outputting files."""
        self.endSave()
        try:
            super().__del__()
        except AttributeError:
            pass


outputprocessor = OmniUsdFormatOutputProcessor
major, minor, _ = hou.applicationVersion()
# After Houdini 19.5, we only return a OutputProcessor Object (v.s instance before 19.5)
if major * 10 + minor < 195:
    # Must have: module-level function to return a processor instance
    outputprocessor = outputprocessor()


def usdOutputProcessor():
    return outputprocessor
