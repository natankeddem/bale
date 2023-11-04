from typing import Dict, List, Union
import asyncio
from asyncio.subprocess import Process, PIPE
import contextlib
import shlex
from datetime import datetime
from nicegui import app, ui
from snapper.result import Result
import logging

logger = logging.getLogger(__name__)


def load_terminal_css():
    app.add_static_files("/static", "static")
    ui.add_head_html('<link href="static/xterm.css" rel="stylesheet">')


class Terminal(ui.element, component="../../static/terminal.js", libraries=["../../static/xterm.js"]):  # type: ignore[call-arg]
    def __init__(
        self,
        options: Dict,
    ) -> None:
        super().__init__()
        self._props["options"] = options

    def call_terminal_method(self, name: str, *args) -> None:
        self.run_method("call_api_method", name, *args)


class Cli:
    def __init__(self, seperator: Union[bytes, None] = b"\n") -> None:
        self.seperator: Union[bytes, None] = seperator
        self.stdout: List[str] = []
        self.stderr: List[str] = []
        self._terminate: asyncio.Event = asyncio.Event()
        self._busy: bool = False
        self.prefix_line: str = ""
        self._stdout_terminals: List[Terminal] = []
        self._stderr_terminals: List[Terminal] = []

    async def _wait_on_stream(self, stream: asyncio.streams.StreamReader) -> Union[str, None]:
        if self.seperator is None:
            buf = await stream.read(140)
        else:
            try:
                buf = await stream.readuntil(self.seperator)
            except asyncio.exceptions.IncompleteReadError as e:
                buf = e.partial
            except Exception as e:
                raise e
        return buf.decode("utf-8")

    async def _read_stdout(self, stream: asyncio.streams.StreamReader) -> None:
        while True:
            buf = await self._wait_on_stream(stream=stream)
            if buf:
                self.stdout.append(buf)
                for terminal in self._stdout_terminals:
                    terminal.call_terminal_method("write", buf)
            else:
                break

    async def _read_stderr(self, stream: asyncio.streams.StreamReader) -> None:
        while True:
            buf = await self._wait_on_stream(stream=stream)
            if buf:
                self.stderr.append(buf)
                for terminal in self._stderr_terminals:
                    terminal.call_terminal_method("write", buf)
            else:
                break

    async def _controller(self, process: Process) -> None:
        while process.returncode is None:
            if self._terminate.is_set():
                process.terminate()
            try:
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(process.wait(), 0.1)
            except Exception as e:
                logger.exception(e)

    def terminate(self) -> None:
        self._terminate.set()

    async def execute(self, command: str) -> Result:
        self._busy = True
        c = shlex.split(command, posix=False)
        try:
            process = await asyncio.create_subprocess_exec(*c, stdout=PIPE, stderr=PIPE)
            if process is not None and process.stdout is not None and process.stderr is not None:
                self.stdout.clear()
                self.stderr.clear()
                self._terminate.clear()
                terminated = False
                now = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
                self.prefix_line = f"<{now}> {command}\n"
                for terminal in self._stdout_terminals:
                    terminal.call_terminal_method("write", "\n" + self.prefix_line)
                await asyncio.gather(
                    self._controller(process=process),
                    self._read_stdout(stream=process.stdout),
                    self._read_stderr(stream=process.stderr),
                )
                if self._terminate.is_set():
                    terminated = True
                await process.wait()
        except Exception as e:
            raise e
        finally:
            self._terminate.clear()
            self._busy = False
        return Result(command=command, stdout_lines=self.stdout.copy(), stderr_lines=self.stderr.copy(), terminated=terminated)

    async def shell(self, command: str) -> Result:
        self._busy = True
        try:
            process = await asyncio.create_subprocess_shell(command, stdout=PIPE, stderr=PIPE)
            if process is not None and process.stdout is not None and process.stderr is not None:
                self.stdout.clear()
                self.stderr.clear()
                self._terminate.clear()
                now = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
                self.prefix_line = f"<{now}> {command}\n"
                for terminal in self._stdout_terminals:
                    terminal.call_terminal_method("write", "\n" + self.prefix_line)
                await asyncio.gather(
                    self._read_stdout(stream=process.stdout),
                    self._read_stderr(stream=process.stderr),
                )
                await process.wait()
        except Exception as e:
            raise e
        finally:
            self._busy = False
        return Result(command=command, stdout_lines=self.stdout.copy(), stderr_lines=self.stderr.copy(), terminated=False)

    def register_stdout_terminal(self, terminal: Terminal) -> None:
        if terminal not in self._stdout_terminals:
            terminal.call_terminal_method("write", self.prefix_line)
            for line in self.stdout:
                terminal.call_terminal_method("write", line)
            self._stdout_terminals.append(terminal)

    def register_stderr_terminal(self, terminal: Terminal) -> None:
        if terminal not in self._stderr_terminals:
            for line in self.stderr:
                terminal.call_terminal_method("write", line)
            self._stderr_terminals.append(terminal)

    def release_stdout_terminal(self, terminal: Terminal) -> None:
        if terminal in self._stdout_terminals:
            self._stdout_terminals.remove(terminal)

    def release_stderr_terminal(self, terminal: Terminal) -> None:
        if terminal in self._stderr_terminals:
            self._stderr_terminals.remove(terminal)

    def register_terminal(self, terminal: Terminal) -> None:
        self.register_stdout_terminal(terminal=terminal)
        self.register_stderr_terminal(terminal=terminal)

    def release_terminal(self, terminal: Terminal) -> None:
        self.release_stdout_terminal(terminal=terminal)
        self.release_stderr_terminal(terminal=terminal)

    @property
    def is_busy(self):
        return self._busy
