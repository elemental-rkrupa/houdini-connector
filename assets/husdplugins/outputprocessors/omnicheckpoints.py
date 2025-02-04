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

# Omni Imports
import omni.usd_resolver
from homni import client as hclient
from homni import logging as hlogging

LOGGER = hlogging.get_homni_logger()


major, minor, _ = hou.applicationVersion()
HVER_INT = major * 10 + minor


class OmniCheckpointsOutputProcessor(base.OutputProcessor):
    """Process creating checkpoint files. USD layers only. Other formats, e.g. textures files, are
    handled by their own output processors. This processing happens after the USD layers are
    saved to disk by a USD ROP.
    """

    theParameters = None
    theCommentParmName = "OmniCheckpoints_comment"
    theVerboseToggleParmName = "OmniCheckpoints_verbose"

    def __init__(self):
        """There is only one object of each output processor class that is
        ever created in a Houdini session. Therefore be very careful
        about what data gets put in this object.
        """
        super().__init__()
        self.initProperties()

    @staticmethod
    def name():
        """The name (token) this output processor is known as."""
        return "omnicheckpoints"

    @staticmethod
    def displayName():
        """Returns a label to describe the processor, in the list of output
        processors shown to the user.
        """
        return "Omniverse Checkpoint Options"

    def initProperties(self):
        self.comment = ""
        self.verbose = False

    @staticmethod
    def parameters():
        """Returns a string containing Houdini dialog script describing the
        checkpoint comment parameter.
        """
        if not OmniCheckpointsOutputProcessor.theParameters:
            parameters = hou.ParmTemplateGroup()

            # Help Card
            helpcardlabelparm = hou.LabelParmTemplate(
                "OmniCheckpoints_help",
                "Message",
                column_labels=(
                    [
                        "Process creating checkpoint files. USD layers only. Other formats, e.g. textures files, are \n"
                        "handled by their own output processors. This processing happens after the USD layers are \n"
                        "saved to disk by a USD ROP.\n"
                    ]
                ),
            )
            helpcardlabelparm.setTags({"sidefx::look": "block"})
            parameters.append(helpcardlabelparm)

            # commnet parm
            commentstringparm = hou.StringParmTemplate(
                OmniCheckpointsOutputProcessor.theCommentParmName,
                "Checkpoints Comment",
                1,
                ("New Version",),
                help="Comment to associate with the checkpoints.",
            )
            parameters.append(commentstringparm)

            # verbose parm
            verbosetoggleparm = hou.ToggleParmTemplate(
                OmniCheckpointsOutputProcessor.theVerboseToggleParmName, "Verbose Output", False
            )
            parameters.append(verbosetoggleparm)

            OmniCheckpointsOutputProcessor.theParameters = parameters.asDialogScript()

        return OmniCheckpointsOutputProcessor.theParameters

    def beginSave(self, config_node, config_overrides, *args, **kwargs):
        """Called when a node using this processor starts to write out files.
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

        # Init properties. Make sure they are clean.
        self.initProperties()

        # Check for the comment parm
        commentstringparm = config_node.parm(self.theCommentParmName)
        if commentstringparm:
            self.comment = commentstringparm.evalAsString()

        # Check for the verbose parm
        verbosetoggleparm = config_node.parm(self.theVerboseToggleParmName)
        if verbosetoggleparm:
            self.verbose = verbosetoggleparm.evalAsInt()
            # verbose is on - turn LOGGER level to debug.
            if self.verbose:
                hlogging.set_level(LOGGER, logging.DEBUG, handler_types=(logging.StreamHandler,))

        omni.usd_resolver.set_checkpoint_message(self.comment)

    def processSavePath(self, asset_path, *args, **kwargs):
        """
        Called when the render node needs to determine where on disk to save
        an asset. The `asset_path` is the file path as Houdini knows it
        (for example, from USD metadata or a Houdini parameter).

        :param asset_path: The path to the asset, as specified in Houdini.
            This string comes with expressions and environment variables (such
            as `$HIP`) expanded already, so if you want to compare to another
            path, you should also expand that path (for example, with
            `os.path.expandvars()` or `hou.text.expandString()`).
        :param is_layer: A boolean value indicating whether this asset is
            a USD layer file. If this is `False`, the asset is something else
            (for example, a texture or volume file).
        """
        asset_path = super().processSavePath(asset_path, *args, **kwargs)

        # Note that the signature of processSavePath in
        # 19.0 -> processSavePath(self, asset_path, is_layer)
        # 19.5 -> processSavePath(self, asset_path, referencing_layer_path, is_layer)
        is_layer = args[0] if HVER_INT < 195 else args[1]
        # We only interested in USD layers.
        if is_layer and self.verbose:
            LOGGER.info(rf"Saving USD file - {asset_path}. Comment: {self.comment}")
        return asset_path

    def endSave(self):
        """Called when the render node finishing outputting files."""
        try:
            super().endSave()
        except AttributeError:
            # endSave has been removed from outputprocessor in Houdini 19.5
            pass

        # Flush data.
        omni.usd_resolver.set_checkpoint_message("")

        if self.verbose:
            # Set back LOGGER level
            hlogging.set_level(LOGGER, int(hclient.getLogLevel()) * 10, handler_types=(logging.StreamHandler,))

    def __del__(self):
        """Called when the render node finishing outputting files."""
        self.endSave()
        try:
            super().__del__()
        except AttributeError:
            pass


outputprocessor = OmniCheckpointsOutputProcessor
# After Houdini 19.5, we only return a OutputProcessor Object (v.s instance before 19.5)
if HVER_INT < 195:
    # Must have: module-level function to return a processor instance
    outputprocessor = outputprocessor()


def usdOutputProcessor():
    return outputprocessor
