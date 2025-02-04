# SPDX-FileCopyrightText: Copyright (c) 2022-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.
import os
import time

import hou
import pytest
from homni import client as hclient
from homni import logging
from omni import client

LOGGER = logging.get_logger("hclient pytest", console_default_level=logging.logging.DEBUG)


TEST_SERVER = "omniverse://localhost"

POWER_POLE_PATH = f"{TEST_SERVER}/NVIDIA/Demos/Connect/Houdini/example_powerlines/powerpole.usd"

TEST_COPY_PATH = f"{TEST_SERVER}/Projects/connect/houdini/test_copy.usd"


def get_download_path():

    return os.path.normpath(
        os.path.join(
            get_cache_base_dir(),
            "Omniverse",
            "Houdini",
            "NVIDIA",
            "Demos",
            "Connect",
            "Houdini",
            "example_powerlines",
            "powerpole.usd",
        )
    )


def get_cache_base_dir():

    return os.path.normpath(
        os.path.realpath(
            os.environ.get("HOME")
            or os.environ.get("USERPROFILE")
            or os.path.join(os.environ.get("HOMEPATH"), os.environ.get("HOMEDRIVE"))
        )
    )


def connect():

    if hclient.connected():

        return True

    hclient.reconnect(TEST_SERVER)

    for retry in range(3):

        if hclient.connected():

            return True

        LOGGER.warning(f"Unable to connect to {TEST_SERVER} - retry {retry+1}/3 in 5 seconds..")

        time.sleep(5)

    return False


def test_initialize():

    assert hclient.initialize()


def test_getCacheDir():

    base_dir = get_cache_base_dir()

    assert os.path.normpath(os.path.join(base_dir, "Omniverse", "Houdini")) == os.path.normpath(
        os.path.dirname(hclient.getCacheDir())
    )


def test_getLogFileBaseName():

    assert hclient.getLogFileBaseName() == "HoudiniOmniClient.log"


@pytest.mark.parametrize(
    "path,expected",
    [
        ("omniverse://aaa/bbb.c", True),
        ("omni://aaa/bbb.c", True),
        ("http://aaa/bbb.c", False),
        (r"C:\aaa\bbb.c", False),
    ],
)
def test_isOmniversePath(path, expected):

    assert hclient.isOmniversePath(path) is expected


@pytest.mark.parametrize(
    "level",
    [
        hclient.LogLevel_Error,
        hclient.LogLevel_Verbose,
        hclient.LogLevel_Info,
        hclient.LogLevel_Warning,
        hclient.LogLevel_Debug,
    ],
)
def test_setgetLogLevel(level):

    hclient.setLogLevel(level)

    assert hclient.getLogLevel() == level


# Connection required tests


def test_connected():

    assert connect()


def test_download():

    assert connect()

    assert get_download_path() == os.path.normpath(os.path.realpath(hclient.download(POWER_POLE_PATH)))


def test_copy():

    assert connect()

    assert hclient.copy(POWER_POLE_PATH, TEST_COPY_PATH, True)

    assert client.read_file(TEST_COPY_PATH)[0] == client.Result.OK


def test_delete():

    assert connect()

    hclient.delete(TEST_COPY_PATH)

    assert client.read_file(TEST_COPY_PATH)[0] == client.Result.ERROR_NOT_FOUND


def test_getLocalFile():

    assert os.path.exists(hclient.getLocalFile(POWER_POLE_PATH))


def test_signOut():

    assert connect()

    hclient.signOut(TEST_SERVER)

    assert hclient.connected() is False
