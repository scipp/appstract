# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2023 Scipp contributors (https://github.com/scipp)
"""Protocols for the app-crafter package and matching mixins"""

from __future__ import annotations

from logging import Logger
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LoggingProtocol(Protocol):  # pragma: no cover
    """General Logging Protocol"""

    @property
    def logger(self) -> Logger: ...

    def debug(self, msg: str, *args: Any) -> None: ...

    def info(self, msg: str, *args: Any) -> None: ...

    def warning(self, msg: str, *args: Any) -> None: ...

    def error(self, msg: str, *args: Any) -> None: ...


def _compose_msg(application: str, message: str) -> str:
    from .logging.formatters import _DEFAULT_MESSAGE_HEADERS

    return _DEFAULT_MESSAGE_HEADERS.fmt % (application, message)


class LogMixin:
    """Logging interfaces."""

    def debug(
        self: LoggingProtocol, msg: str, *args: Any, stacklevel=2, **kwargs: Any
    ) -> None:
        self.logger.debug(
            _compose_msg(self.__class__.__qualname__, msg),
            *args,
            stacklevel=stacklevel,
            **kwargs,
        )

    def info(
        self: LoggingProtocol, msg: str, *args: Any, stacklevel=2, **kwargs: Any
    ) -> None:
        self.logger.info(
            _compose_msg(self.__class__.__qualname__, msg),
            *args,
            stacklevel=stacklevel,
            **kwargs,
        )

    def warning(
        self: LoggingProtocol, msg: str, *args: Any, stacklevel=2, **kwargs: Any
    ) -> None:
        self.logger.warning(
            _compose_msg(self.__class__.__qualname__, msg),
            *args,
            stacklevel=stacklevel,
            **kwargs,
        )

    def error(
        self: LoggingProtocol, msg: str, *args: Any, stacklevel=2, **kwargs: Any
    ) -> None:
        self.logger.error(
            _compose_msg(self.__class__.__qualname__, msg),
            *args,
            stacklevel=stacklevel,
            **kwargs,
        )
