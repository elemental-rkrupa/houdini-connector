# SPDX-FileCopyrightText: Copyright (c) 2020-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import hou
import omni.client
from homni import logging

LOGGER = logging.get_homni_logger()


def run():
    """After save callback to inform user of problematic backup option."""
    try:
        url = omni.client.break_url(hou.hipFile.path())
        # If we are not dealing with nucleus path, we can skip this pre-save callback
        if not url.host:
            return

        if hou.getPreference("autoIncrement") == "2" or hou.getPreference("autoSaveIncrement") == "2":
            if hou.getenv("HOMNI_ENABLE_SAVE_WARNINGS", "1") == "1":
                message = 'The Houdini Save and Load Options preference is set to "Make Numbered Backup"'
                help_message = 'This option will pop open the "bad backup directory" message you just saw when working with hip files on the Nucleus server. \n\nTo eliminate this message, use the provided Omniverse -> Save Hip\n\nAlternatively,  use another save preference Edit -> Preferences -> Save and load options.\nFor versioning, you can also use Nucleus Checkpoints.\n\nSee Omniverse -> Online Documentation for details'
                if hou.isUIAvailable():
                    button_clicked = hou.ui.displayMessage(
                        text=message,
                        severity=hou.severityType.Warning,
                        help=help_message,
                        title="Nucleus incompatible save preference found",
                        buttons=("OK", "Turn off this warning (session)"),
                    )
                    if button_clicked == 1:
                        hou.putenv("HOMNI_ENABLE_SAVE_WARNINGS", "0")

    except (Exception, hou.Error):
        LOGGER.warning("After save callback error occurred")


if "kwargs" in globals() and not kwargs["autosave"] and kwargs["success"]:
    run()
