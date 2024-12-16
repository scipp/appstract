# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2024 Scipp contributors (https://github.com/scipp)
"""Asynchronous application components."""

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable, Coroutine, Generator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from typing import (
    Any,
    Protocol,
    TypeVar,
    runtime_checkable,
)

from .logging import AppLogger
from .mixins import LogMixin


@runtime_checkable
class EventMessageProtocol(Protocol):
    content: Any


class HandlerProtocol(Protocol):
    """Callable object that accepts a single message as the first positional argument.

    These handlers are called by :class:`~MessageRouter` whenever another
    handler or a daemon publishes the relevant message (by type).
    """

    def __call__(self, message: EventMessageProtocol) -> Any: ...


class AsyncHandlerProtocol(Protocol):
    """Awaitable object that accepts a single message as the first positional argument.

    These handlers are awaited by :class:`~MessageRouter` whenever another
    handler or a daemon publishes the relevant message (by type).
    """

    def __call__(self, message: EventMessageProtocol) -> Any: ...


class DaemonMessageGeneratorProtocol(Protocol):
    """Callable object that returns a message generator.

    Daemon message generators are expected to have a long life cycle.
    i.e. repeatedly monitoring a data pipe, or listening to a message broker.

    They are expected to be created and iterated by the :class:`~Application` object.
    The reason why it is not done by :class:`~MessageRouter` is that
    the application object should be able to control the life cycle of the daemon.

    And the ``Daemon``s are not expected to receive any message from the message router.
    Therefore the message router does not have to know about the daemons.

    """

    def __call__(self) -> Generator[EventMessageProtocol | None, None]: ...


class AsyncDaemonMessageGeneratorProtocol(Protocol):
    """Awaitable object that returns an asynchronous message generator.

    Daemon message generators are expected to have a long life cycle.
    i.e. repeatedly monitoring a data pipe, or listening to a message broker.

    They are expected to be created and iterated by the :class:`~Application` object.
    The reason why it is not done by :class:`~MessageRouter` is that
    the application object should be able to control the life cycle of the daemon.

    And the ``Daemon``s are not expected to receive any message from the message router.
    Therefore the message router does not have to know about the daemons.

    """

    def __call__(self) -> AsyncGenerator[EventMessageProtocol | None, None]: ...


MessageT = TypeVar("MessageT", bound=EventMessageProtocol)
HandlerT = TypeVar("HandlerT", bound=Callable)


class MessageRouter(LogMixin):
    """A message router that routes messages to handlers."""

    logger: AppLogger

    def __init__(self):
        from queue import Queue

        self.handlers: dict[
            type[EventMessageProtocol], list[Callable[[EventMessageProtocol], Any]]
        ] = {}
        self.awaitable_handlers: dict[
            type[EventMessageProtocol],
            list[Callable[[EventMessageProtocol], Awaitable[Any]]],
        ] = {}
        self.message_pipe = Queue()

    @contextmanager
    def _handler_wrapper(
        self, handler: Callable[..., Any], message: EventMessageProtocol
    ) -> Generator[None, None, None]:
        try:
            self.debug(f"Routing event {type(message)} to handler {handler}...")
            yield
        except Exception as e:
            self.warning(f"Failed to handle event {type(message)}")
            raise e
        else:
            self.debug(f"Routing event {type(message)} to handler {handler} done.")

    def _register(
        self,
        *,
        handler_list: dict[type[MessageT], list[HandlerT]],
        event_tp: type[MessageT],
        handler: HandlerT,
    ):
        if event_tp in handler_list:
            handler_list[event_tp].append(handler)
        else:
            handler_list[event_tp] = [handler]

    def register_handler(
        self,
        event_tp: type[MessageT],
        handler: Callable[[MessageT], Any] | Callable[[MessageT], Awaitable[Any]],
    ):
        if asyncio.iscoroutinefunction(handler):
            handler_list = self.awaitable_handlers
        else:
            handler_list = self.handlers

        self._register(handler_list=handler_list, event_tp=event_tp, handler=handler)

    def _collect_results(self, result: Any) -> list[EventMessageProtocol]:
        """Append or extend ``result`` to ``self.message_pipe``.

        It filters out non-AppstractMessage objects from ``result``.
        """
        if isinstance(result, EventMessageProtocol):
            return [result]
        elif isinstance(result, tuple):
            return [_msg for _msg in result if isinstance(_msg, EventMessageProtocol)]
        else:
            return []

    def sync_route(self, message: EventMessageProtocol) -> None:
        # Synchronous handlers
        results = []
        for handler in (handlers := self.handlers.get(type(message), [])):
            with self._handler_wrapper(handler, message):
                results.extend(self._collect_results(handler(message)))

        # No handlers
        if not handlers:
            self.warning(f"No handler for event {type(message)}. Ignoring...")

        # Re-route the results
        for result in results:
            self.message_pipe.put(result)

    async def async_route(self, message: EventMessageProtocol) -> None:
        # Synchronous handlers
        results = []
        for handler in (handlers := self.handlers.get(type(message), [])):
            await asyncio.sleep(0)  # Let others use the event loop.
            with self._handler_wrapper(handler, message):
                results.extend(self._collect_results(handler(message)))

        # Asynchronous handlers
        for handler in (
            awaitable_handlers := self.awaitable_handlers.get(type(message), [])
        ):
            with self._handler_wrapper(handler, message):
                results.extend(self._collect_results(await handler(message)))

        # No handlers
        if not (handlers or awaitable_handlers):
            self.warning(f"No handler for event {type(message)}. Ignoring...")

        # Re-route the results
        for result in results:
            self.message_pipe.put(result)

    async def async_run(self) -> AsyncGenerator[EventMessageProtocol | None, None]:
        """Message router daemon."""
        while True:
            await asyncio.sleep(0)
            if self.message_pipe.empty():
                await asyncio.sleep(0.1)
            while not self.message_pipe.empty():
                await self.async_route(self.message_pipe.get())
            yield

    def sync_run(self) -> Generator[EventMessageProtocol | None, None]:
        """Message router daemon."""
        while True:
            if self.message_pipe.empty():
                yield
            while not self.message_pipe.empty():
                self.sync_route(self.message_pipe.get())
                yield
            yield

    async def send_message_async(self, message: EventMessageProtocol) -> None:
        self.message_pipe.put(message)
        await asyncio.sleep(0)

    def send_message(self, message: EventMessageProtocol) -> None:
        self.message_pipe.put(message)


@dataclass
class StopEventMessage:
    """A message to break the routing loop."""

    content: Any


class ApplicationMixin:
    def stop_tasks(self, message: EventMessageProtocol | None = None) -> None:
        self.info('Stop running application %s...', self.__class__.__name__)
        if message is not None and not isinstance(message, StopEventMessage):
            raise TypeError(
                f"Expected message of type {StopEventMessage}, got {type(message)}."
            )
        self._break = True

    def register_handler(
        self, event_tp: type[MessageT], handler: Callable[[MessageT], Any]
    ) -> None:
        """Register handlers to the application message router."""
        self.message_router.register_handler(event_tp, handler)

    def register_daemon(
        self,
        daemon: DaemonMessageGeneratorProtocol | AsyncDaemonMessageGeneratorProtocol,
    ) -> None:
        """Register a daemon generator to the application.

        Registered daemons will be scheduled in the event loop
        as :func:`~Application.run` method is called.
        The future of the daemon will be collected in the ``self.tasks`` list.
        """
        self.daemons.append(daemon)

    @contextmanager
    def _handle_keyboard_interrupt(self):
        _interrupted_count = 0
        try:
            yield
        except KeyboardInterrupt as e:
            if _interrupted_count < 1:
                self.info("Received a keyboard interrupt. Exiting...")
                self.info("Press Ctrl+C one more time to kill immediately.")
                self.message_router.message_pipe.put_nowait(
                    AsyncApplication.Stop(content=None)
                )
            else:
                raise e


class SyncApplication(ApplicationMixin, LogMixin):
    """Synchronous Application class.

    Main Responsibilities:
        - Register handling methods if applicable.
        - Create/collect tasks of daemons.
        - Start the daemons including the message router.

    """

    def __init__(self, logger: AppLogger, message_router: MessageRouter) -> None:
        self.tasks: dict[Callable, Generator] = {}
        self.logger = logger
        self.message_router = message_router
        self.daemons: list[DaemonMessageGeneratorProtocol] = [
            self.message_router.sync_run
        ]
        self.register_handler(StopEventMessage, self.stop_tasks)
        self._break = False
        super().__init__()

    def register_daemon(self, daemon: DaemonMessageGeneratorProtocol) -> None:
        """Register a daemon generator to the application.

        Synchronous application allows only synchronous daemons.

        Registered daemons will be used in the :func:``~SynchronousApplication.run``.
        The generator(daemons) will be collected in the ``self.tasks`` dictionary.
        """
        self.daemons.append(daemon)

    def cancel_all_tasks(self) -> None:
        """Cancel all tasks.

        Effectively remove all existing message generators.
        """
        self.tasks.clear()

    @contextmanager
    def _daemon_wrapper(
        self, daemon: DaemonMessageGeneratorProtocol
    ) -> Generator[None, None]:
        try:
            self.info('Running daemon %s', daemon.__class__.__qualname__)
            yield
        except Exception as e:
            self.error(f"Daemon {daemon} failed. Cancelling all other tasks...")
            # Break all daemon generator loops.
            self._break = True
            # Let other daemons/handlers clean up.
            self.message_router.sync_route(StopEventMessage(None))
            # Make sure all other async tasks are cancelled.
            self.cancel_all_tasks()
            raise e
        else:
            self.info("Daemon %s completed.", daemon.__class__.__qualname__)

    def _create_daemon_tasks(
        self,
    ) -> dict[DaemonMessageGeneratorProtocol, Generator]:
        def run_daemon(daemon: DaemonMessageGeneratorProtocol):
            with self._daemon_wrapper(daemon):
                for message in daemon():
                    if message is not None:
                        self.message_router.send_message(message)
                    if self._break:
                        break
                    yield

        return {daemon: run_daemon(daemon) for daemon in self.daemons}

    def run(self):
        """Start running all daemons including a message router
        until a stop message is received, a keyboard interrupt is received,
        or all daemons are completed.

        Note that this call will block the later code execution
        and it is not suitable for receiving user input or running
        in a Jupyter Notebook.
        Use :class:`~AsyncApplication` if you want to
        run the application asynchronously.

        """
        with self._handle_keyboard_interrupt():
            self.info('Start running %s...', self.__class__.__qualname__)
            if self.tasks:
                raise RuntimeError(
                    "Application is already running. "
                    "Cancel all tasks and clear them before running it again."
                )

            daemon_tasks = self._create_daemon_tasks()
            self.tasks.update(daemon_tasks)
            while not self._break:
                cur_tasks = (
                    self.tasks.copy()
                )  # Avoid RuntimeError: dictionary changed size during iteration
                for daemon, task in cur_tasks.items():
                    try:
                        next(task)
                    except StopIteration:  # noqa: PERF203
                        self.info("Daemon %s completed.", daemon.__class__.__qualname__)
                        self.tasks.pop(daemon)
                        if not self.tasks:
                            self.info("All daemons completed.")
                            break

    def run_after_run(self):
        """This method is only available for :class:`~AsyncApplication`."""
        raise NotImplementedError("This method is only available for AsyncApplication.")


class AsyncApplication(ApplicationMixin, LogMixin):
    """Asynchronous Application class.

    Main Responsibilities:
        - Create/retrieve event loop if needed.
        - Create tasks if an event loop exists already.
        - Register handling methods if applicable.
        - Create/collect tasks of daemons.

    """

    def __init__(self, logger: AppLogger, message_router: MessageRouter) -> None:
        import asyncio

        self.loop: asyncio.AbstractEventLoop
        self.tasks: dict[Callable, asyncio.Task] = {}
        self.logger = logger
        self.message_router = message_router
        self.daemons: list[
            AsyncDaemonMessageGeneratorProtocol | DaemonMessageGeneratorProtocol
        ] = [self.message_router.async_run]
        self.register_handler(StopEventMessage, self.stop_tasks)
        self._break = False
        super().__init__()

    def register_daemon(
        self,
        daemon: DaemonMessageGeneratorProtocol | AsyncDaemonMessageGeneratorProtocol,
    ) -> None:
        """Register a daemon generator to the application.

        Asynchronous application allows both synchronous and asynchronous daemons.

        Registered daemons will be scheduled in the event loop
        as :func:`~Application.run` method is called.
        The future of the daemon will be collected in the ``self.tasks`` dictionary.
        """
        self.daemons.append(daemon)

    def cancel_all_tasks(self) -> None:
        """Cancel all tasks."""
        for task in self.tasks.values():
            task.cancel()

        self.tasks.clear()

    @asynccontextmanager
    async def _daemon_wrapper(
        self,
        daemon: AsyncDaemonMessageGeneratorProtocol | DaemonMessageGeneratorProtocol,
    ) -> AsyncGenerator[None, None]:
        try:
            self.info('Running daemon %s', daemon.__class__.__qualname__)
            yield
        except Exception as e:
            # Make sure all other async tasks are cancelled.
            # It is because raising an exception will destroy only the task
            # that had an error raised and may not affect other tasks in some cases,
            # e.g. in Jupyter Notebooks.
            self.error(f"Daemon {daemon} failed. Cancelling all other tasks...")
            # Break all daemon generator loops.
            self._break = True
            # Let other daemons/handlers clean up.
            await self.message_router.async_route(StopEventMessage(None))
            # Make sure all other async tasks are cancelled.
            self.cancel_all_tasks()
            raise e
        else:
            self.info("Daemon %s completed.", daemon.__class__.__qualname__)

    def _create_daemon_coroutines(
        self,
    ) -> dict[
        AsyncDaemonMessageGeneratorProtocol | DaemonMessageGeneratorProtocol, Coroutine
    ]:
        async def run_daemon(
            daemon: AsyncDaemonMessageGeneratorProtocol
            | DaemonMessageGeneratorProtocol,
        ):
            async with self._daemon_wrapper(daemon):
                generator = daemon()
                if isinstance(generator, AsyncGenerator):
                    async for message in generator:
                        if message is not None:
                            await self.message_router.send_message_async(message)
                        if self._break:
                            break
                        await asyncio.sleep(0)
                elif isinstance(generator, Generator):
                    for message in generator:
                        if message is not None:
                            await self.message_router.send_message_async(message)
                        if self._break:
                            break
                        await asyncio.sleep(0)

        return {daemon: run_daemon(daemon) for daemon in self.daemons}

    def run(self):
        """
        Register all handling methods and run all daemons.

        It retrieves or creates an event loop
        and schedules all coroutines(run methods) of its daemons.

        See :doc:`/developer/async_programming` for more details about
        why it handles the event loop like this.

        This method is only when the ``Application`` object needs to start the
        event loop itself.
        If there is a running event loop expected, use ```` instead.

        """
        import asyncio

        from appstract.schedulers import temporary_event_loop

        with self._handle_keyboard_interrupt():
            self.info('Start running %s...', self.__class__.__qualname__)
            if self.tasks:
                raise RuntimeError(
                    "Application is already running. "
                    "Cancel all tasks and clear them before running it again."
                )

            with temporary_event_loop() as loop:
                self.loop = loop
                daemon_coroutines = self._create_daemon_coroutines()
                daemon_tasks = {
                    daemon: loop.create_task(coro)
                    for daemon, coro in daemon_coroutines.items()
                }
                self.tasks.update(daemon_tasks)
                if not loop.is_running():
                    loop.run_until_complete(asyncio.gather(*self.tasks.values()))

    def run_after_run(self):
        """
        Register all handling methods and run all daemons.

        It schedules all coroutines(run methods) of its daemons.

        """
        import asyncio

        with self._handle_keyboard_interrupt():
            self.info('Start running %s...', self.__class__.__qualname__)
            if self.tasks:
                raise RuntimeError(
                    "Application is already running. "
                    "Cancel all tasks and clear them before running it again."
                )
            self.loop = asyncio.get_event_loop()
            daemon_coroutines = self._create_daemon_coroutines()
            daemon_tasks = {
                daemon: self.loop.create_task(coro)
                for daemon, coro in daemon_coroutines.items()
            }
            self.tasks.update(daemon_tasks)
