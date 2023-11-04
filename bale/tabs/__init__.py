from typing import Any, Dict, List, Union
from dataclasses import dataclass, field
import asyncio
from datetime import datetime
import time
from nicegui import ui
from bale.interfaces.zfs import Ssh
from bale import elements as el
from bale.result import Result
from bale.interfaces import cli


@dataclass(kw_only=True)
class Task:
    action: str
    command: str
    status: str
    host: str
    result: Union[Result, None] = None
    history: float = field(default_factory=time.time)
    timestamp: float = field(default_factory=time.time)


class Tab:
    _zfs: Dict[str, Ssh] = {}
    _history: List[Result] = []
    _tasks: List[Task] = []

    def __init__(self, spinner, host=None) -> None:
        self._spinner: el.Spinner = spinner
        self.host: str = host
        self._build()

    def _build(self):
        pass

    @classmethod
    def register_connection(cls, host: str) -> None:
        cls._zfs[host] = Ssh(path="data", host=host)

    async def _display_result(self, result: Result) -> None:
        with ui.dialog() as dialog, el.Card():
            with el.DBody(height="fit", width="fit"):
                with el.WColumn():
                    with el.Card() as card:
                        card.tailwind.width("full")
                        with el.WRow() as row:
                            row.tailwind.justify_content("around")
                            with ui.column() as col:
                                col.tailwind.max_width("lg")
                                ui.label(f"Host Name: {result.name}").classes("text-secondary")
                                ui.label(f"Command: {result.command}").classes("text-secondary")
                                ui.label(f"Date: {result.date}").classes("text-secondary")
                            with ui.column() as col:
                                col.tailwind.max_width("lg")
                                ui.label(f"Task has failed: {result.failed}").classes("text-secondary")
                                ui.label(f"Data is cached: {result.cached}").classes("text-secondary")
                                ui.label(f"Time: {result.time}").classes("text-secondary")
                    with el.Card() as card:
                        with el.WColumn():
                            terminal = cli.Terminal(options={"rows": 20, "cols": 120, "convertEol": True})
                            for line in result.stdout_lines:
                                terminal.call_terminal_method("write", line)
                            for line in result.stderr_lines:
                                terminal.call_terminal_method("write", line)
                with el.WRow() as row:
                    row.tailwind.height("[40px]")
                    el.DButton("Exit", on_click=lambda: dialog.submit("exit"))
        await dialog

    def add_history(self, result: Result) -> None:
        result.status = "error" if result.failed else "success"
        r = result.to_dict()
        if len(self._history) > 1000:
            self._history.pop(0)
        self._history.append(r)

    def _add_task(self, action: str, command: str, hosts: Union[List[str], None] = None) -> None:
        if hosts is None:
            hosts = [self.host]
        for host in hosts:
            self._tasks.append(Task(action=action, command=command, host=host, status="pending"))

    def _remove_task(self, timestamp: str):
        for task in self._tasks:
            if task.timestamp == timestamp:
                self._tasks.remove(task)
                return task

    @property
    def zfs(self) -> Ssh:
        return self._zfs[self.host]

    @property
    def _zfs_hosts(self) -> List[str]:
        return list(self._zfs.keys())
