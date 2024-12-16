# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2024 Scipp contributors (https://github.com/scipp)
import argparse
import asyncio
import time
from collections.abc import AsyncGenerator, Generator
from dataclasses import dataclass
from importlib.metadata import entry_points
from typing import Protocol, TypeVar

from .constructors import (
    Factory,
    ProviderGroup,
    SingletonProvider,
    multiple_constant_providers,
)
from .event_driven import (
    AsyncApplication,
    EventMessageProtocol,
    MessageRouter,
    StopEventMessage,
    SyncApplication,
)
from .logging import AppLogger
from .logging.providers import log_providers
from .mixins import LogMixin

T = TypeVar("T", bound="ArgumentInstantiable")


def list_entry_points() -> list[str]:
    return [ep.name for ep in entry_points(group='beamlime.workflow_plugin')]


def build_arg_parser(*sub_group_classes: type) -> argparse.ArgumentParser:
    """Builds the minimum argument parser for the highest-level entry point."""
    parser = argparse.ArgumentParser(description="BEAMLIME configuration.")
    parser.add_argument(
        "--log-level",
        help="Set logging level. Default is INFO.",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
    )
    for sub_group_class in sub_group_classes:
        if callable(add_arg := getattr(sub_group_class, "add_argument_group", None)):
            add_arg(parser)

    return parser


class ArgumentInstantiable(Protocol):
    @classmethod
    def add_argument_group(cls, parser: argparse.ArgumentParser) -> None: ...

    @classmethod
    def from_args(cls: type[T], logger: AppLogger, args: argparse.Namespace) -> T: ...


def instantiate_from_args(
    logger: AppLogger, args: argparse.Namespace, tp: type[T]
) -> T:
    return tp.from_args(logger=logger, args=args)


@dataclass
class HelloWorldMessage:
    content: str


class Echo(LogMixin):
    logger: AppLogger

    async def async_echo(self, msg: EventMessageProtocol) -> None:
        await asyncio.sleep(1)
        self.error(msg.content)
        await asyncio.sleep(1)

    def sync_echo(self, msg: EventMessageProtocol) -> None:
        time.sleep(1)
        self.error(msg.content)
        time.sleep(1)


class Narc(LogMixin):
    logger: AppLogger

    async def async_shout(self) -> AsyncGenerator[EventMessageProtocol, None]:
        self.info("Going to shout hello world 3 times...")
        messages = ("Hello World", "Heelllloo World!", "Heeelllllloooo World!")
        for msg in messages:
            await asyncio.sleep(1)
            self.info(msg)
            yield HelloWorldMessage(msg)
            await asyncio.sleep(1)

        yield StopEventMessage(content=None)

    def sync_shout(self) -> Generator[EventMessageProtocol, None, None]:
        self.info("Going to shout hello world 3 times...")
        messages = ("Hello World", "Heelllloo World!", "Heeelllllloooo World!")
        for msg in messages:
            time.sleep(1)
            self.info(msg)
            yield HelloWorldMessage(msg)
            time.sleep(1)
        yield StopEventMessage(content=None)


def run_async_helloworld():
    arg_name_space: argparse.Namespace = build_arg_parser().parse_args()
    parameters = {argparse.Namespace: arg_name_space}

    factory = Factory(
        log_providers,
        ProviderGroup(
            SingletonProvider(AsyncApplication),
            SingletonProvider(MessageRouter),
            Echo,
            Narc,
        ),
    )

    with multiple_constant_providers(factory, parameters):
        factory[AppLogger].setLevel(arg_name_space.log_level.upper())
        app = factory[AsyncApplication]
        echo = factory[Echo]
        narc = factory[Narc]

        # Handlers
        app.register_handler(HelloWorldMessage, echo.async_echo)

        # Daemons
        app.register_daemon(narc.async_shout)
        app.run()


def run_sync_helloworld():
    arg_name_space: argparse.Namespace = build_arg_parser().parse_args()
    parameters = {argparse.Namespace: arg_name_space}

    factory = Factory(
        log_providers,
        ProviderGroup(
            SingletonProvider(SyncApplication),
            SingletonProvider(MessageRouter),
            Echo,
            Narc,
        ),
    )

    with multiple_constant_providers(factory, parameters):
        factory[AppLogger].setLevel(arg_name_space.log_level.upper())
        app = factory[SyncApplication]
        echo = factory[Echo]
        narc = factory[Narc]

        # Handlers
        app.register_handler(HelloWorldMessage, echo.sync_echo)

        # Daemons
        app.register_daemon(narc.sync_shout)
        app.run()
