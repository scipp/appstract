# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2024 Scipp contributors (https://github.com/scipp)
import argparse
import asyncio
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from importlib.metadata import entry_points
from typing import Protocol, TypeVar

from .asyncs import AsyncApplication, MessageProtocol, MessageRouter
from .constructors import (
    Factory,
    ProviderGroup,
    SingletonProvider,
    multiple_constant_providers,
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

    async def echo(self, msg: MessageProtocol) -> None:
        await asyncio.sleep(0.5)
        self.error(msg.content)


class Narc(LogMixin):
    logger: AppLogger

    async def shout(self) -> AsyncGenerator[MessageProtocol, None]:
        self.info("Going to shout hello world 3 times...")
        messages = ("Hello World", "Heelllloo World!", "Heeelllllloooo World!")
        for msg in messages:
            self.info(msg)
            yield HelloWorldMessage(msg)
            await asyncio.sleep(1)

        yield AsyncApplication.Stop(content=None)


def run_helloworld():
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
        app.register_handler(HelloWorldMessage, echo.echo)

        # Daemons
        app.register_daemon(narc.shout)
        app.run()
