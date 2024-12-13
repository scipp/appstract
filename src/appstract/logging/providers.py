# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2023 Scipp contributors (https://github.com/scipp)
from __future__ import annotations

import logging
from typing import Literal, NewType

from ..constructors.providers import merge as merge_providers
from .formatters import _formatter_providers
from .handlers import AppCrafterFileHandler, AppCrafterStreamHandler, _handler_providers
from .resources import _resources_providers

LogLevels = Literal["DEBUG", "INFO", "WARNING", "ERROR"]
AppLogger = NewType("AppLogger", logging.Logger)

log_providers = merge_providers(
    _formatter_providers,
    _handler_providers,
    _resources_providers,
)


@log_providers.provider
def get_logger(
    stream_handler: AppCrafterStreamHandler | None = None, verbose: bool = True
) -> AppLogger:
    """
    Retrieves a default logger and add ``stream_handler`` if ``verbose``.

    """
    from appstract import __name__ as default_name

    logger = logging.getLogger(default_name)
    if verbose and not logger.handlers:
        logger.addHandler(stream_handler or AppCrafterStreamHandler())

    return AppLogger(logger)


FileHandlerConfigured = NewType("FileHandlerConfigured", bool)


@log_providers.provider
def initialize_file_handler(
    logger: AppLogger, file_handler: AppCrafterFileHandler
) -> FileHandlerConfigured:
    """
    Add a file handler to the ``logger``.
    It creates the directory at ``dir_path`` if it does not exist.
    File name is automatically created.

    To adjust file name with different prefix or extension,
    see ``create_log_file_path``.
    """
    from .resources import check_file_handlers

    check_file_handlers(logger)
    _hdlrs = [
        hdlr for hdlr in logger.handlers if isinstance(hdlr, AppCrafterFileHandler)
    ]
    file_paths = [hdlr.baseFilename for hdlr in _hdlrs]
    if any(file_paths):
        logger.warning(
            "Attempt to add a new file handler to the current logger, "
            "but a file handler is already configured. "
            "Log file base path is %s"
            "Aborting without changing the logger...",
            file_paths,
        )
        return FileHandlerConfigured(True)

    logger.info("Start collecting logs into %s", file_handler.baseFilename)
    logger.addHandler(file_handler)

    return FileHandlerConfigured(True)
