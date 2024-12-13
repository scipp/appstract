# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2023 Scipp contributors (https://github.com/scipp)
from logging import Logger

from appstract.constructors import Factory
from appstract.logging import AppLogger, get_logger


def test_get_logger_default(local_logger: bool):
    assert local_logger

    default_logger: Logger = get_logger()
    assert default_logger is get_logger()
    assert default_logger.name == "appstract"


def test_logger_provider(local_logger: bool, default_factory: Factory):
    assert local_logger
    with default_factory.local_factory() as factory:
        assert factory[AppLogger] is get_logger()
        assert factory[AppLogger].name == "appstract"
