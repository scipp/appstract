# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2023 Scipp contributors (https://github.com/scipp)
from __future__ import annotations

from logging import FileHandler
from typing import NewType

from rich.logging import RichHandler

from ..constructors import ProviderGroup
from .formatters import AppCrafterFileFormatter, AppCrafterStreamHighlighter
from .resources import FileHandlerBasePath


class AppCrafterFileHandler(FileHandler):
    def __del__(self) -> None:
        self.close()


_handler_providers = ProviderGroup()


@_handler_providers.provider
def provide_appstract_filehandler(
    filename: FileHandlerBasePath, formatter: AppCrafterFileFormatter
) -> AppCrafterFileHandler:
    """Returns a file handler."""
    handler = AppCrafterFileHandler(filename)
    handler.formatter = formatter
    return handler


class AppCrafterStreamHandler(RichHandler): ...


ShowPath = NewType("ShowPath", bool)
DEFAULT_SHOW_PATH = ShowPath(True)


@_handler_providers.provider
def provide_appstract_streamhandler(
    highlighter: AppCrafterStreamHighlighter,
    show_path: ShowPath = DEFAULT_SHOW_PATH,
) -> AppCrafterStreamHandler:
    """Returns a ``RichHandler`` with :py:class:``AppCrafterStreamHighlighter``."""

    return AppCrafterStreamHandler(highlighter=highlighter, show_path=show_path)
