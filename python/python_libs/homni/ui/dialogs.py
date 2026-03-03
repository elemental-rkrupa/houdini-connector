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
import pathlib

import hou
from homni import client, logging
from PySide6 import QtCore, QtUiTools, QtWidgets
from PySide6.QtCore import *
from PySide6.QtWidgets import *

LOGGER = logging.get_homni_logger()


class OmniConnectDialog(QDialog):
    instance = None
    timer_interval = 2000
    session_string = ""
    session_connections = []

    def __init__(self, parent=None):

        super(OmniConnectDialog, self).__init__(parent)

        # The connection list items that were selected last,
        # used to attempt to maintain the selection when the
        # connection list is updated.
        self.prev_selected = []

        # This will record the connection update count to monitor
        # connection list changes.
        self.connection_update_count = -1

        self.createGUI()

        self.disconnButton.setEnabled(False)
        self.addBookmarkButton.setEnabled(False)

        self.updateConnectionList()

        self.timer = QTimer()
        self.timer.timeout.connect(self.updateConnectionList)

    def createGUI(self):
        self.setParent(hou.qt.mainWindow(), QtCore.Qt.Window)

        self.setWindowTitle("Connect to Omniverse")
        self.setMinimumWidth(400)

        self.serverEdit = QLineEdit()

        self.formLayout = QFormLayout()
        self.formLayout.addRow("Server:", self.serverEdit)

        self.connButton = QPushButton()
        self.connButton.setText("Connect")
        self.connButton.clicked.connect(self.connectBtnClicked)

        self.addBookmarkButton = QPushButton()
        self.addBookmarkButton.setText("Add to Favorites")
        self.addBookmarkButton.clicked.connect(self.addToBookmarkBtnClicked)

        self.disconnButton = QPushButton()
        self.disconnButton.setText("Disconnect")
        self.disconnButton.clicked.connect(self.disconnectBtnClicked)

        self.connListHeader = QLabel("Open Connections")

        self.connList = QListWidget()
        self.connList.setSizeAdjustPolicy(QListWidget.AdjustToContents)
        self.connList.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.connList.itemSelectionChanged.connect(self.connectionListSelectionChanged)

        self.boxLayout = QVBoxLayout()
        self.boxLayout.addLayout(self.formLayout)
        self.boxLayout.addWidget(self.connButton, 0, Qt.AlignCenter)
        self.boxLayout.addWidget(self.connListHeader)
        self.boxLayout.addWidget(self.connList)
        self.buttonGrpLayout = QHBoxLayout()
        self.buttonGrpLayout.addStretch()
        self.buttonGrpLayout.addWidget(self.disconnButton, 0, Qt.AlignCenter)
        self.buttonGrpLayout.addSpacing(15)
        self.buttonGrpLayout.addWidget(self.addBookmarkButton, 0, Qt.AlignCenter)
        self.buttonGrpLayout.addStretch()
        self.boxLayout.addLayout(self.buttonGrpLayout)

        self.session_message = QLabel(OmniConnectDialog.session_string)
        message_layout = QVBoxLayout()
        message_layout.addWidget(self.session_message)

        self.messageGroupBox = QtWidgets.QGroupBox()
        self.messageGroupBox.setLayout(message_layout)
        self.messageGroupBox.setTitle("Info")
        if OmniConnectDialog.session_string == "":
            self.messageGroupBox.hide()

        self.boxLayout.addWidget(self.messageGroupBox)
        self.setLayout(self.boxLayout)

    def connectBtnClicked(self):
        omni_host = self.serverEdit.text()
        if omni_host and client.isOmniversePath(omni_host):
            omni_host = client.parseOmniPath(omni_host).host
        client.reconnect("omniverse://" + omni_host)
        self.serverEdit.clear()

    def connectionListSelectionChanged(self):
        selected = self.connList.selectedItems()
        num_selected = len(selected)

        self.disconnButton.setEnabled(num_selected > 0)
        self.update_add_bookmark_button_state()

        self.prev_selected = []

        if num_selected > 0:
            for item in selected:
                self.prev_selected.append(item.text())

    def update_add_bookmark_button_state(self):
        """Sets the state and tooltip of add bookmark button based on jump.pref file"""
        is_bookmarked = self.is_selected_connection_bookmarked()
        self.addBookmarkButton.setEnabled(not is_bookmarked)
        selected_items = self.connList.selectedItems()
        label = "In Favorites" if is_bookmarked else "Add to Favorites"
        tool_tip = (
            "Selected item already a favorite in the file browser"
            if is_bookmarked
            else "Click to favorite selected connection in the file browser"
        )
        if len(selected_items) == 0:
            tool_tip = "Select connection.\nIf the favorite does not already exist in the file browser, this button will become available"
            label = "Add to Favorites"
        self.addBookmarkButton.setText(label)
        self.addBookmarkButton.setToolTip(tool_tip)

    def disconnectBtnClicked(self):
        for item in self.connList.selectedItems():
            client.signOut("omniverse://" + item.text())

    def addToBookmarkBtnClicked(self):
        """Adds a favorite to the jump.pref file for the selected item. Since the button that triggers this command is disabled when the connection already exists in the jump.pref file,
        there is no need to check if the connection already exists.
        """

        connections = []
        for item in self.connList.selectedItems():
            connection = f"omniverse://{item.text()}/"
            connections.append(connection)
            if connection not in OmniConnectDialog.session_connections:
                OmniConnectDialog.session_connections.append(connection)
        bookmark_connections(connections)
        self.update_add_bookmark_button_state()

        connections_string = "\n".join(OmniConnectDialog.session_connections)
        message = (
            f"Connection added as favorite - {OmniConnectDialog.session_connections[0]}"
            if len(OmniConnectDialog.session_connections) == 1
            else f"Connections added as favorites:\n{connections_string}"
        )
        OmniConnectDialog.session_string = (
            f"{message}\n\nFile browser favorites will be available after a Houdini restart"
        )
        self.session_message.setText(OmniConnectDialog.session_string)
        self.messageGroupBox.show()

    def updateConnectionList(self):
        if self.connection_update_count == client.connectionUpdateCount():
            # No change to the connection list
            return

        prev_selected = list(self.prev_selected)

        connections = client.listConnections()
        self.connList.clear()

        for conn in connections:
            url = client.parseOmniPath(conn)
            if url and url.host:
                new_conn = url.host
                if url.port:
                    new_conn += ":"
                    new_conn += url.port
                self.connList.addItem(new_conn)

        for name in prev_selected:
            found_items = self.connList.findItems(name, Qt.MatchExactly)
            for item in found_items:
                item.setSelected(True)

        self.connection_update_count = client.connectionUpdateCount()
        self.update_add_bookmark_button_state()
        # self.update_add_all_bookmarks_button_state()

    def closeEvent(self, event):
        self.timer.stop()

    def showEvent(self, event):
        if not self.isMinimized() and not self.timer.isActive():
            self.timer.start(OmniConnectDialog.timer_interval)

    def is_selected_connection_bookmarked(self):
        """Check if the selected connection exists in the jump.pref file"""
        jump_pref_content = get_jump_pref_contents()
        for item in self.connList.selectedItems():
            connection = f"omniverse://{item.text()}/"
            if connection not in jump_pref_content:
                return False
        return True


def showConnectDialog():
    if OmniConnectDialog.instance is None:
        OmniConnectDialog.instance = OmniConnectDialog(hou.qt.mainWindow())

    OmniConnectDialog.instance.showNormal()


def is_connection_bookmarked(connection: str) -> bool:
    """

    Args:
        connection (str): Server url with an ending '/'

    Returns:
        (bool) True/False if the connection url is a favorite already

    """
    jump_pref_content = get_jump_pref_contents()
    if connection not in jump_pref_content:
        return False
    return True


def get_jump_pref_path() -> str:
    """
    Gets the user pref path to the jump.pref file

    Returns:
        (str) Path to the jump.pref file

    """
    return "{user_pref_dir}/jump.pref".format(user_pref_dir=hou.getenv("HOUDINI_USER_PREF_DIR"))


def ensure_jump_pref() -> bool:
    """
    Ensures that the jump.pref file exists
    Returns:
        (bool) True/False of the existence of the file

    """
    jump_pref_path = get_jump_pref_path()
    if not os.path.exists(jump_pref_path):
        pathlib.Path(jump_pref_path).touch(exist_ok=True)
    return os.path.exists(jump_pref_path)


def get_jump_pref_contents() -> list:
    """
    Gets the contents of the jump.pref file and filters out new lines
    Returns:
        (list) List of url strings

    """
    jump_pref_path = get_jump_pref_path()
    contents = []
    if not os.path.exists(jump_pref_path):
        return contents

    with open(jump_pref_path) as jump_pref:
        raw_content = jump_pref.readlines()
        contents = [line.rstrip("\n") for line in raw_content]
    return contents


def bookmark_connections(connections):
    """
    Favorites connections to the jump.pref file
    Args:
        connections (list): A list of string urls to favorite.
    """
    jump_pref_path = get_jump_pref_path()
    contents = []
    file_exists = ensure_jump_pref()
    if not file_exists:
        message = "jump.pref file could not be created, skipping favorite creation"
        if hou.isUIAvailable():
            hou.ui.displayMessage(message)
        else:
            LOGGER.warning(message)
        return

    with open(jump_pref_path) as jump_pref:
        raw_content = jump_pref.readlines()
        contents = [line.rstrip("\n") for line in raw_content]
        contents.extend(connections)

    with open(jump_pref_path, "w") as jump_pref:
        jump_pref.write("\n".join(contents))
