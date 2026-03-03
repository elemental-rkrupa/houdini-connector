# SPDX-FileCopyrightText: Copyright (c) 2020-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.
import asyncio
import logging
import os
import re
import subprocess
import sys

import homni.utils
import hou
import omni.asset_validator
from homni import client
from homni import logging as hlogging
from homni.client import LogLevel
from homni.ui import dialogs
from PySide6 import QtCore, QtWidgets

LOGGER = hlogging.get_homni_logger()


def createSeparator():
    separator = QtWidgets.QFrame()
    separator.setFrameShape(QtWidgets.QFrame.HLine)
    separator.setFrameShadow(QtWidgets.QFrame.Sunken)
    separator.setLineWidth(1)
    return separator


class OmniPanel(QtWidgets.QWidget):
    log_directory = os.path.join(client.getCacheDir(), "log")
    group_stylesheet = """QGroupBox {

    border: 1px solid gray;
    # border-color: #76b900;
    margin-top: 1ex; /* leave space at the top for the title */
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top center; /* position at the top center */
    padding: 0 20px;

}
"""
    timer_interval = 2000

    def __init__(self, *args, **kwargs):

        super(OmniPanel, self).__init__(*args, **kwargs)

        self.createGUI()

        self.updateLogLevelCombo()

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.updateUI)

    def createGUI(self):

        # Main Layout
        layout = QtWidgets.QVBoxLayout()

        versionLabel = QtWidgets.QLabel()
        versionLabel.setText("Omniverse Plugin v" + client.getVersionString())

        toolLayout = QtWidgets.QHBoxLayout()
        self.connButton = QtWidgets.QPushButton()
        self.connButton.setText("Manage Connections")
        self.connButton.clicked.connect(self.connectBtnClicked)

        self.saveButton = QtWidgets.QPushButton()
        self.saveButton.setText("Save Hip")
        self.saveButton.setToolTip(
            "Hip Save utility that manages backup folder creation and backup copies on the Nucleus server"
        )
        self.saveButton.clicked.connect(self.saveButtonClicked)

        self.copyFilesButton = QtWidgets.QPushButton()
        self.copyFilesButton.setText("Copy Files")
        self.copyFilesButton.setToolTip(
            "Copy file utility that handles file copy to the Nucleus server - "
            "handy if you want to share HDA files with others."
        )
        self.copyFilesButton.clicked.connect(self.copyFilesButtonClicked)

        toolLayout.addStretch()
        toolLayout.addWidget(self.connButton)
        toolLayout.addSpacing(20)
        toolLayout.addWidget(self.saveButton)
        toolLayout.addWidget(self.copyFilesButton)
        toolLayout.addStretch()

        toolGroupBox = QtWidgets.QGroupBox()
        toolGroupBox.setLayout(toolLayout)
        toolGroupBox.setTitle("Tools")
        # toolGroupBox.setStyleSheet(OmniPanel.group_stylesheet)

        self.openLogFolderButton = QtWidgets.QPushButton()
        self.openLogFolderButton.setText("Open Folder")
        self.openLogFolderButton.setToolTip("Opens up the log folder.")
        self.openLogFolderButton.clicked.connect(self.openLogFolderButtonClicked)

        self.logLevelCombo = QtWidgets.QComboBox()
        self.logLevelCombo.setMaximumWidth(300)
        self.initLogLevelComboItems(self.logLevelCombo)
        self.logLevelCombo.currentIndexChanged.connect(self.logLevelComboIndexChanged)

        log_layout = QtWidgets.QHBoxLayout()
        log_layout.addStretch()
        log_layout.addWidget(self.logLevelCombo)
        log_layout.addSpacing(20)
        log_layout.addWidget(self.openLogFolderButton)
        log_layout.addStretch()

        logGroupBox = QtWidgets.QGroupBox()
        logGroupBox.setLayout(log_layout)
        logGroupBox.setTitle("Logging")
        # logGroupBox.setStyleSheet(OmniPanel.group_stylesheet)

        layout.addWidget(versionLabel, 0, QtCore.Qt.AlignCenter)
        layout.addWidget(toolGroupBox)
        layout.addWidget(logGroupBox)
        layout.addStretch()
        self.setLayout(layout)

    def connectBtnClicked(self):
        dialogs.showConnectDialog()

    def saveButtonClicked(self):
        homni.utils.save_helper()

    def copyFilesButtonClicked(self):
        homni.utils.file_copy_helper()

    def openLogFolderButtonClicked(self):
        if not os.path.exists(OmniPanel.log_directory):
            msg = rf"Log directory does not exist - {OmniPanel.log_directory}"
            if hou.isUIAvailable():
                hou.ui.displayMessage(msg)
            else:
                LOGGER.error(msg)
            return

        #  os.startflie only available in Windows
        if sys.platform == "win32":
            os.startfile(OmniPanel.log_directory)
        else:
            try:
                subprocess.call(["xdg-open", OmniPanel.log_directory])
            except Exception:
                msg = rf"Unable to open log directory - {OmniPanel.log_directory}"
                if hou.isUIAvailable():
                    hou.ui.displayMessage(msg)
                else:
                    LOGGER.error(msg)

    def initLogLevelComboItems(sefl, combo):
        combo.addItem("Error", LogLevel.LogLevel_Error)
        combo.addItem("Warning", LogLevel.LogLevel_Warning)
        combo.addItem("Info", LogLevel.LogLevel_Info)
        combo.addItem("Verbose", LogLevel.LogLevel_Verbose)
        combo.addItem("Debug", LogLevel.LogLevel_Debug)

    def updateUI(self):
        self.updateLogLevelCombo()

    def logLevelComboIndexChanged(self, index):
        data = self.logLevelCombo.itemData(index)
        client.setLogLevel(data)
        # Update all loggers and handlers from homni.logging
        for logger in hlogging.LOGGERS.values():
            hlogging.set_level(logger, max(int(data), 1) * 10, (logging.StreamHandler,))

    def findDataIndex(self, data):
        """
        Returns the index of the item with the given data.
        This is needed as a workaround because QComboBox.findData(data)
        doesn't work for custom types, apparently.
        """
        for index in range(self.logLevelCombo.count()):
            if data == self.logLevelCombo.itemData(index):
                return index

        return -1

    def updateLogLevelCombo(self):
        data = client.getLogLevel()
        cur_data = self.logLevelCombo.currentData()

        if data != cur_data:
            new_index = self.findDataIndex(data)
            if new_index >= 0:
                self.logLevelCombo.setCurrentIndex(new_index)
            else:
                LOGGER.error(f"Coding error: couldn't find log level combobox index for {data}")

    def liveProcessBtnClicked(self):
        client.usdLiveProcess()

    def closeEvent(self, event):
        self.timer.stop()

    def showEvent(self, event):
        if not self.isMinimized() and not self.timer.isActive():
            self.timer.start(OmniPanel.timer_interval)


class AssetValidatorTreeModel(QtCore.QAbstractItemModel):
    def __init__(self, data, parent=None):
        super(AssetValidatorTreeModel, self).__init__(parent)
        self.rootItem = data
        self.initDefaults()

    def initDefaults(self):
        disabledCategories = []
        enabledCategories = []
        enabledRules = []
        disabledRules = []

        def setDefaultStatus(item, parentIndex=self.index(0, 0, QtCore.QModelIndex())):
            index = self.index(item.row(), 0, parentIndex)
            updated = False
            if isinstance(item, CategoryItem):
                if item.name in disabledCategories:
                    item.checked = False
                    updated = True
                if item.name in enabledCategories:
                    item.checked = True
                    updated = True

            elif isinstance(item, CheckerItem):
                if item.name in disabledRules:
                    item.checked = False
                    updated = True
                if item.name in enabledRules:
                    item.checked = True
                    updated = True
            if updated:
                self.setData(
                    index, QtCore.Qt.Checked if item.checked else QtCore.Qt.Unchecked, QtCore.Qt.CheckStateRole
                )

            for childItem in item.children:
                setDefaultStatus(childItem, index)

        for categoryItem in self.rootItem.children[0].children:  # self.rootItem.children[0] is the ruleItem
            setDefaultStatus(categoryItem)

    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()):
        return len(parent.internalPointer().children) if parent.isValid() else 1

    def columnCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()):
        return 1

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if not index.isValid():
            return None

        item = index.internalPointer()

        if role == QtCore.Qt.CheckStateRole and index.column() == 0:
            return QtCore.Qt.Checked if item.checked else QtCore.Qt.Unchecked
        elif role == QtCore.Qt.DisplayRole:
            return item.name
        elif role == QtCore.Qt.ToolTipRole:
            return item.description  # Set tooltip for each item

    def flags(self, index):
        if not index.isValid():
            return QtCore.Qt.NoItemFlags

        return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsUserCheckable

    def setData(self, index, value, role=QtCore.Qt.EditRole, checkUncheckParent=True, checkUncheckChildren=True):
        if role == QtCore.Qt.CheckStateRole and index.column() == 0:
            item = index.internalPointer()
            item.checked = value == QtCore.Qt.Checked

            if checkUncheckChildren:
                # Check or uncheck all child items
                self.checkUncheckChildren(index, value)

            if checkUncheckParent:
                # Check or uncheck parent item if all siblings have the same state
                self.checkUncheckParent(index)

            self.dataChanged.emit(index, index)
            return True
        return False

    def checkUncheckChildren(self, parentIndex, value):
        parentItem = parentIndex.internalPointer()
        for row in range(parentItem.rowCount()):
            childIndex = self.index(row, 0, parentIndex)
            self.setData(childIndex, value, QtCore.Qt.CheckStateRole, checkUncheckParent=False)

    def checkUncheckParent(self, childIndex):
        parentIndex = self.parent(childIndex)
        if parentIndex.isValid():
            parentItem = parentIndex.internalPointer()
            allChecked = True
            allUnchecked = True
            for row in range(parentItem.rowCount()):
                childIndex = self.index(row, 0, parentIndex)
                state = self.data(childIndex, QtCore.Qt.CheckStateRole)
                if state == QtCore.Qt.Checked:
                    allUnchecked = False
                elif state == QtCore.Qt.Unchecked:
                    allChecked = False

            parentState = (
                QtCore.Qt.Checked
                if allChecked
                else (QtCore.Qt.Unchecked if allUnchecked else QtCore.Qt.PartiallyChecked)
            )
            self.setData(parentIndex, parentState, QtCore.Qt.CheckStateRole, checkUncheckChildren=False)

    def parent(self, index):
        if not index.isValid():
            return QtCore.QModelIndex()

        parentItem = index.internalPointer().parent

        if parentItem == self.rootItem:
            return QtCore.QModelIndex()

        return self.createIndex(parentItem.row(), 0, parentItem)

    def index(self, row, column, parent=QtCore.QModelIndex()):
        if not self.hasIndex(row, column, parent):
            return QtCore.QModelIndex()

        if not parent.isValid():
            parentItem = self.rootItem
        else:
            parentItem = parent.internalPointer()

        childItem = parentItem.child(row)
        if childItem:
            return self.createIndex(row, column, childItem)
        else:
            return QtCore.QModelIndex()


class CheckableItem:
    def __init__(self, name, parent=None, description=""):
        self.name = name
        self.parent = parent
        self.children = []
        self.checked = True
        self.description = description or name

        if parent is not None:
            parent.addChild(self)

    def addChild(self, child):
        self.children.append(child)

    def child(self, row):
        if 0 <= row < len(self.children):
            return self.children[row]
        return None

    def rowCount(self):
        return len(self.children)

    def row(self):
        if self.parent is not None:
            return self.parent.children.index(self)
        return 0


class CategoryItem(CheckableItem):
    pass


class CheckerItem(CheckableItem):
    def __init__(self, checker, parent=None):
        super(CheckerItem, self).__init__(checker.__name__, parent=parent, description=checker.GetDescription())
        self.checker = checker


class AssetValidatorTreeViewPane(QtWidgets.QWidget):
    def __init__(self, data, parent=None):
        super(AssetValidatorTreeViewPane, self).__init__(parent)
        self.model = AssetValidatorTreeModel(data)
        self.treeView = QtWidgets.QTreeView(self)
        self.treeView.setModel(self.model)
        self.treeView.setItemDelegate(AssetValidatorItemDelegate(self.treeView))
        self.treeView.setHeaderHidden(True)

        self.resultTextEdit = QtWidgets.QTextEdit(self)
        self.resultTextEdit.setReadOnly(True)  # Make the text field read-only

        self.okButton = QtWidgets.QPushButton("Validate", self)
        self.okButton.clicked.connect(self.handleOK)

        # Create a splitter to allow adjusting the size of the text field
        splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)

        widget = QtWidgets.QWidget(splitter)
        layout = QtWidgets.QVBoxLayout(widget)
        layout.addWidget(self.treeView)
        layout.addWidget(self.okButton)

        splitter.addWidget(widget)
        splitter.addWidget(self.resultTextEdit)
        sizes = [splitter.size().height() * 0.7, splitter.size().height() * 0.3]
        splitter.setSizes(sizes)

        # Add QLineEdit and QLabel for the path field
        self.pathLabel = QtWidgets.QLabel("LOP Node Path: ", self)
        self.pathLineEdit = QtWidgets.QLineEdit(self)
        if hou.node("/stage").displayNode():
            self.pathLineEdit.setText(hou.node("/stage").displayNode().path())

        # Layout for the QLineEdit and QLabel
        path_layout = QtWidgets.QHBoxLayout()
        path_layout.addWidget(self.pathLabel)
        path_layout.addWidget(self.pathLineEdit)

        # Main layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(path_layout)
        layout.addWidget(splitter)

        self.setWindowTitle("Omniverse USD Validator")

        # Expand the first item by default
        self.treeView.setExpanded(self.model.index(0, 0, QtCore.QModelIndex()), True)

    @staticmethod
    def getResultText(result):
        resultText = ""
        filteredIssues = set()
        issues = result.issues()
        messagesToSkip = [
            r"Found unresolvable external dependency 'anon:.*",
            r".*anon:.*:LOP:rootlayer.*",
            r".*Prim </HoudiniLayerInfo>.*",
            r"Root layer of the stage '' does not have the '.usdc' extension.",
        ]

        for issue in issues:
            for messagePattern in messagesToSkip:
                next_issue = False
                if re.match(messagePattern, issue.message):
                    next_issue = True
                    break
            if next_issue:
                continue

            suggestion = issue.suggestion.message if issue.suggestion else "No Suggestion."
            filteredIssues.add((issue.message, suggestion))

        for issue, suggestion in filteredIssues:
            resultText = resultText + f"ISSUE: {issue}\nSUGGESTION: {suggestion}\n\n{'-'*150}\n\n"

        resultText = resultText + "\nValidation Done."
        return resultText

    async def _validate(self, engine, stage):
        validating_str = "Validating ..."
        self.resultTextEdit.setPlainText(validating_str)
        task = asyncio.ensure_future(engine.validate_async(stage))

        while not task.done():
            validating_str += ".."
            self.resultTextEdit.setPlainText(validating_str)
            await asyncio.sleep(1)

        result = task.result()
        self.resultTextEdit.setPlainText(self.getResultText(result))

    def handleOK(self):
        checkedItems, uncheckedItems = self.getCheckedAndUncheckedItems()
        enabled_checkers = [item.checker for item in checkedItems]

        engine = omni.asset_validator.ValidationEngine(init_rules=False)
        for checker in enabled_checkers:
            engine.enableRule(checker)

        nodePath = self.pathLineEdit.text()
        node = hou.node(nodePath)
        if not node:
            self.resultTextEdit.setPlainText(f"Node '{nodePath}' does not exits.")
            return

        if not hasattr(node, "stage"):
            self.resultTextEdit.setPlainText(f"Node '{nodePath}' has no USD stage. Is it a LOP node?")
            return

        stage = node.stage()
        if not stage:
            self.resultTextEdit.setPlainText(f"Stage of node '{nodePath}' does not exits.")
            return

        if hou.applicationVersion()[0] >= 20:
            asyncio.ensure_future(self._validate(engine, stage))
        else:
            LOGGER.warn("Validating.. This might block your session for seconds.")
            # This is a block call :( We have to do it in H19
            asyncio.run(self._validate(engine, stage))

    def getCheckedAndUncheckedItems(self):
        checkedItems = []
        uncheckedItems = []
        root_item = self.model.rootItem
        self._collectCheckedAndUncheckedItems(root_item, checkedItems, uncheckedItems)
        return checkedItems, uncheckedItems

    def _collectCheckedAndUncheckedItems(self, item, checkedItems, uncheckedItems):
        if isinstance(item, CheckerItem):
            if item.checked:
                checkedItems.append(item)
            else:
                uncheckedItems.append(item)

        for childItem in item.children:
            self._collectCheckedAndUncheckedItems(childItem, checkedItems, uncheckedItems)


class AssetValidatorItemDelegate(QtWidgets.QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        checkbox = QtWidgets.QCheckBox(parent)
        checkbox.clicked.connect(self.commitData)
        return checkbox

    def setEditorData(self, editor, index):
        value = index.model().data(index, QtCore.Qt.CheckStateRole)
        editor.setChecked(value == QtCore.Qt.Checked)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.checkState(), QtCore.Qt.CheckStateRole)


def createAssetValidatorTreeViewPane():
    registry = omni.asset_validator.get_category_rules_registry()
    rules = {}
    for category in registry.categories:
        rules[category] = registry.get_rules(category)

    root = CheckableItem("root")  # True Root, this can only have 1 child item
    rulesItem = CheckableItem("Rules", root)
    for category, checkers in rules.items():
        categoryItem = CategoryItem(category, rulesItem)
        for checker in checkers:
            CheckerItem(checker, parent=categoryItem)

    return AssetValidatorTreeViewPane(root)
