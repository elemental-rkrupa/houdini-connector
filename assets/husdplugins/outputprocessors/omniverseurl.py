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

import homni
import homni.client
import hou
import husd.outputprocessor as base
import omni
import omni.client
from homni import logging

LOGGER = logging.get_homni_logger()


class OmniverseUrlOutputProcessor(base.OutputProcessor):
    """
    Performs the processing necessary to save files with Omniverse URLs.
    Note that this should usually be the first output processor to be applied,
    to avoid modifying the URL before OmniverseUrlOutputProcessor.processAsset()
    is called.
    """

    @staticmethod
    def name():
        return "omniverseurl"

    @staticmethod
    def displayName():
        return "Omniverse URL"

    def processReferencePath(self, asset_path, referencing_layer_path, asset_is_layer):
        asset_path = super(OmniverseUrlOutputProcessor, self).processReferencePath(
            asset_path, referencing_layer_path, asset_is_layer
        )
        return self.processAsset(asset_path, "", referencing_layer_path, asset_is_layer, for_save=False)

    def processSavePath(self, asset_path, referencing_layer_path, asset_is_layer):
        asset_path = super(OmniverseUrlOutputProcessor, self).processSavePath(
            asset_path, referencing_layer_path, asset_is_layer
        )
        return self.processAsset("", asset_path, referencing_layer_path, asset_is_layer, for_save=True)

    def processAsset(self, asset_path, asset_path_for_save, referencing_layer_path, asset_is_layer, for_save):
        """
        Normalizes the Omniverse URL and registers the corresponding absolute
        filesystem prefix so that the USD ROP recognizes the URL as an
        absoloute path.  Adding the prefix is performed internally with a call
        to the HDK function UTaddAbsolutePathPrefix().

        For example, the path omni://localhost/Users/test/foo.usd
        would be normalized as omniverse://localhost/Users/test/foo.usd and the
        string omniverse://localhost would be added as an absolute path prefix.
        If we don't do this, the USD ROP will attempt to handle the original omni:
        URL as a relative filesystem path and will prepend the current
        directory (os.getcwd()) to the URL, which is incorrect.
        """

        if for_save or asset_path_for_save:
            asset_path = omni.client.normalize_url(asset_path)

            if for_save and homni.client.isOmniversePath(asset_path):
                url = omni.client.break_url(asset_path)
                if url:
                    # Consideration: do we ever need to handle paths with no host?
                    if url.host:
                        homni.client.addBookmark(url.host)
                else:
                    LOGGER.warning(rf"Couldn't parse URL for Omniverse path {asset_path}.")

        return asset_path


outputprocessor = OmniverseUrlOutputProcessor
major, minor, _ = hou.applicationVersion()
# After Houdini 19.5, we only return a OutputProcessor Object (v.s instance before 19.5)
if major * 10 + minor < 195:
    # Must have: module-level function to return a processor instance
    outputprocessor = outputprocessor()


def usdOutputProcessor():
    return outputprocessor
