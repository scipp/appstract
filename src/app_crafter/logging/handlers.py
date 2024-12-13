# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2023 Scipp contributors (https://github.com/scipp)
from __future__ import annotations

from logging import FileHandler

from rich.logging import RichHandler

from ..constructors import ProviderGroup
from .formatters import AppCrafterFileFormatter, AppCrafterStreamHighlighter
from .resources import FileHandlerBasePath


class AppCrafterFileHandler(FileHandler):
    def __del__(self) -> None:
        self.close()


_handler_providers = ProviderGroup()


@_handler_providers.provider
def provide_app_crafter_filehandler(
    filename: FileHandlerBasePath, formatter: AppCrafterFileFormatter
) -> AppCrafterFileHandler:
    """Returns a file handler."""
    handler = AppCrafterFileHandler(filename)
    handler.formatter = formatter
    return handler


class AppCrafterStreamHandler(RichHandler): ...


@_handler_providers.provider
def provide_app_crafter_streamhandler(
    highlighter: AppCrafterStreamHighlighter,
) -> AppCrafterStreamHandler:
    """Returns a ``RichHandler`` with :py:class:``AppCrafterStreamHighlighter``."""

    return AppCrafterStreamHandler(highlighter=highlighter)
