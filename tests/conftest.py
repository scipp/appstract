# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2023 Scipp contributors (https://github.com/scipp)
# These fixtures cannot be found by pytest,
# if they are not defined in `conftest.py` under `tests` directory.
from collections.abc import Generator
from typing import Literal

import pytest

from app_crafter.constructors import Factory


def pytest_addoption(parser: pytest.Parser):
    parser.addoption("--slow-test", action="store_true", default=False)


@pytest.fixture(scope='session')
def slow_test(request: pytest.FixtureRequest) -> Literal[True]:
    """
    Requires --slow-test flag.
    """
    if not request.config.getoption('--slow-test'):
        pytest.skip("Skipping slow tests. Use ``--slow-test`` option to run this test.")
    return True


@pytest.fixture
def local_logger() -> Generator[Literal[True], None, None]:
    """
    Keep a copy of logger names in logging.Logger.manager.loggerDict
    and remove newly added loggers at the end of the context.

    It will help a test not to interfere other tests.
    """
    from app_crafter.logging._test_helpers import local_logger as _local_logger

    with _local_logger():
        yield True


@pytest.fixture
def default_factory() -> Factory:
    """Returns a Factory that has all default providers of ``app_crafter``."""
    from app_crafter.logging.providers import log_providers

    return Factory(log_providers)
