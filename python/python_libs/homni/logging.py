# SPDX-FileCopyrightText: Copyright (c) 2022-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.
""" This module can be used to instantiate a logging.Logger object

Example::
    from homni import logging

    # Create a module log that will only log to console
    module_logger = logging.get_logger(name=__name__)
    module_logger.debug('This is a debug message')
    logging.set_level(module_logger, logging.logging.INFO)

    # Create a logger that also writes to file
    log_dir = 'C:/Test/NVIDIA/Omniverse'

    import os
    log_file = os.path.join(log_dir, 'test.log')
    file_logger = get_logger(name='myTest', add_file_handler=True, output_log_path=log_file, file_mode=MODE_OVERWRITE)
    file_logger.info('Testing')
    # [INFO myTest (2024-01-11 20:52:24)] Testing
"""

import logging
import os
import re
import sys
from argparse import ArgumentTypeError
from collections.abc import Iterable
from functools import partial

import omni.log
from homni import client as hclient

MODE_OVERWRITE = "w"
MODE_APPEND = "a"

OMNI_LOGGER_NAME = hclient.getConnectorName()

LOGGERS = {}

LOG_MESSAGE_CONSUMER: omni.log.ILogMessageConsumer = None


class LogFormatter(logging.Formatter):
    """Subclassing logging.Formatter to customize output (default for the get function)"""

    def format(self, record):
        """Function that formats the incoming log record

        Args:
            record (logging.LogRecord): Class containing properties about the log record

        Returns:
            str: A formatted string of everything we would like to see in the log output.
        """
        module_string = os.path.normpath(record.pathname)
        if record.levelno < logging.INFO:
            location = f" - {module_string} - {record.funcName}:{record.lineno}"
        else:
            location = ""

        return f"[{record.levelname} {record.name} ({self.formatTime(record, '%Y-%m-%d %H:%M:%S')}){location}] {record.msg}"


class ColorLogFormatter(LogFormatter):
    """Logging color formatter"""

    grey = "\x1b[38;20m"
    green = "\x1b[32;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;1m"
    clear = "\x1b[0m"

    formats = {
        logging.DEBUG: grey,
        logging.INFO: green,
        logging.WARNING: yellow,
        logging.ERROR: red,
        logging.CRITICAL: red,
    }

    def format(self, record):
        color = ColorLogFormatter.formats.get(record.levelno, ColorLogFormatter.clear)  # default no color
        fmt = f"{color}{super().format(record)}\x1b[0m"
        return fmt


def get_logger(
    name,
    formatter=None,
    add_console_handler=True,
    console_default_level=None,
    add_file_handler=False,
    output_log_path=None,
    file_mode=MODE_APPEND,
):
    """Function to get a logging.Logger object

    Args:
        name (str): Name of the log object
        formatter (logging.Formatter, optional): Custom class that formats the logging.LogRecord.
                                                 Resolved to ColorLogFormatter() (Linux) or LogFormatter() (Windows)
                                                 if this argument is None (Default).
        add_console_handler (bool, optional): Provides console output. Defaults to True.
        console_default_level (int, optional): Default logging level for console handler.
        add_file_handler (bool, optional): Provides file output. Defaults to False.
        output_log_path (str, optional): Output log file path if file output is True.
                                         Resolved to ~/Omniverse/Houdini/HoudiniOmni.log if this arg is None or empty str.
        file_mode (str, optional): If file output is True, append or overwrite the file log. Defaults to MODE_APPEND.

    Returns:
        logging.Logger: Logger object to log with
    """
    logger = logging.getLogger(name)
    # Set logger to the lowest level, the handlers filter level.
    logger.setLevel(logging.DEBUG)

    # Clear prior handlers
    for handler in logger.handlers:
        handler.close()
        logger.removeHandler(handler)

    if not formatter:
        if sys.platform == "win32":
            # We don't use ColorLogFormatter for Windows' StreamHandler since Houdini Concole
            # cannot display text color.
            formatter = LogFormatter()
            file_formatter = ColorLogFormatter()
        else:
            file_formatter = formatter = ColorLogFormatter()

    # Default level
    if console_default_level is None:
        console_default_level = get_default_level()

    if add_console_handler:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        # Default level
        console_handler.setLevel(console_default_level)
        logger.addHandler(console_handler)

    if add_file_handler:
        if not output_log_path:
            raise ArgumentTypeError("When adding a file handler, please provide output_log_path argument.")

        if not os.path.exists(os.path.dirname(output_log_path)):
            os.makedirs(os.path.dirname(output_log_path))

        # File
        file_handler = logging.FileHandler(output_log_path, mode=file_mode)
        file_handler.setFormatter(file_formatter)
        # We log everything in the log file.
        file_handler.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)

    logger.propagate = False
    # Add new created logger to collector
    LOGGERS[name] = logger
    return logger


def get_default_level():
    """Get default logging level from environment variable - HOMNI_LOGLEVEL
    If the environment variable is not defined, level ERROR - 40 will be returned.

    Returns:
        int: Log level in int type.
    """
    try:
        level = int(hclient.getLogLevel())
    except Exception:
        try:
            level = int(os.environ.get("HOMNI_LOGLEVEL", 4))
        except Exception:
            level = 4

    # The omni.client logging level is 0-5 v.s Python logging level 10-50
    # We are assuming the user is using omni.client system.. multiply the environment by 10
    level = max(level, 1) * 10

    if level >= 50:
        level = logging.CRITICAL
    elif level >= 40:
        level = logging.ERROR
    elif level >= 30:
        level = logging.WARNING
    elif level >= 20:
        level = logging.INFO
    else:
        level = logging.DEBUG
    return level


def set_level(logger, level, handler_types=None):
    """Set log level for all log handlers

    Args:
        logger (logging.Logger): Log to set level to
        level (int): Set by passing int directly or using the logging class enums:
                        CRITICAL = 50
                        FATAL = CRITICAL
                        ERROR = 40
                        WARNING = 30
                        WARN = WARNING
                        INFO = 20
                        DEBUG = 10
                        NOTSET = 0
        hander_types (None|iterable, optional): If this argument is given, only set level to handlers
                                                that are in the handler_types.
    """
    for handler in logger.handlers:
        if isinstance(handler_types, Iterable):
            # Note we don't use isinstance, we check exact type here.
            if any(filter(lambda x: type(handler) is x, handler_types)):
                handler.setLevel(level)
        else:
            handler.setLevel(level)


def get_default_log_directory():
    """Get the default log file directory.

    Returns:
        str: Log file directory path.
    """
    return os.path.join(hclient.getCacheDir(), "log")


def get_homni_log_file_path():
    """Get the default log file path.

    Returns:
        str: Log file path.
    """
    return os.path.join(get_default_log_directory(), "HoudiniOmni.log")


def get_hda_log_file_path(node):
    """Get the hda log file path.

    Returns:
        str: Hda log file path.
    """
    file_name = re.sub(r"[^a-zA-Z0-9]", "_", node.path())
    # Log saved to ~/Omniverse/Houdini/{node_type}/{node_path}.log
    return os.path.join(get_default_log_directory(), node.type().name(), f"{file_name}.log")


def get_homni_logger():
    """Function to get a the main pacakge logging.Logger object

    Returns:
        logging.Logger: Logger object to log with
    """
    logger = LOGGERS.get(OMNI_LOGGER_NAME)
    if not logger:
        logger = get_logger(
            name=OMNI_LOGGER_NAME,
            add_file_handler=True,
            output_log_path=get_homni_log_file_path(),
            file_mode=MODE_OVERWRITE,
        )
    return logger


def get_hda_logger(node):
    """Function to get a logging.Logger object for given node.

    Args:
        node (hou.Node): hou.Node object for the hda logger.

    Returns:
        logging.Logger: Logger object to log with
    """
    logger_name = node.path()
    logger = LOGGERS.get(logger_name)
    if not logger:
        logger = get_logger(
            name=logger_name,
            add_file_handler=True,
            output_log_path=get_hda_log_file_path(node),
            file_mode=MODE_OVERWRITE,
        )
    return logger


def register_omni_log(logger: logging.Logger = None):
    """Add log consumer function to omni.log

    Args:
        logger (logging.Logger): Logger object where omni.log messages will be redirected to.
                                 If not given, logger from get_homni_logger() will be used.
    """

    def omni_log(logger: logging.Logger, channel: str, level: omni.log.Level, msg: str):
        if level == omni.log.Level.VERBOSE:
            logger.debug(f"[{channel}] {msg}")
        elif level == omni.log.Level.INFO:
            logger.info(f"[{channel}] {msg}")
        elif level == omni.log.Level.WARN:
            logger.warning(f"[{channel}] {msg}")
        elif level == omni.log.Level.ERROR:
            logger.error(f"[{channel}] {msg}")
        elif level == omni.log.Level.FATAL:
            logger.critical(f"[{channel}] {msg}")
        else:
            logger.debug(f"[{channel}] [{level}] {msg}")

    if logger is None:
        logger = get_homni_logger()
    LOG_MESSAGE_CONSUMER = omni.log.get_log().add_message_consumer(partial(omni_log, logger))


def deregister_omni_log(logger: logging.Logger):
    """Remove log consumer function from omni.log

    Args:
        logger (logging.Logger): Logger object where omni.log messages will not be redirected to anymore.
    """
    logger.debug(f"Deregister logger: {logger.name}")
    if LOG_MESSAGE_CONSUMER:
        omni.log.get_log().remove_message_consumer(LOG_MESSAGE_CONSUMER)

    logger.debug(f"{logger.name} removed.")
