from typing import Any, Dict, List, Union
from dataclasses import dataclass, field
import string
import asyncio
from datetime import datetime
import time
import json
import httpx
from nicegui import app, ui
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


class PipeTemplate(string.Template):
    delimiter = ""


class SelectionConfirm:
    def __init__(self, container, label) -> None:
        self._container = container
        self._label = label
        self._visible = None
        self._result = None
        self._submitted = None
        with self._container:
            self._label = ui.label(self._label).tailwind().text_color("primary")
            self._done = el.IButton(icon="done", on_click=lambda: self.submit("confirm"))
            self._cancel = el.IButton(icon="close", on_click=lambda: self.submit("cancel"))

    @property
    def submitted(self) -> asyncio.Event:
        if self._submitted is None:
            self._submitted = asyncio.Event()
        return self._submitted

    def open(self) -> None:
        self._container.visible = True

    def close(self) -> None:
        self._container.visible = False
        self._container.clear()

    def __await__(self):
        self._result = None
        self.submitted.clear()
        self.open()
        yield from self.submitted.wait().__await__()  # pylint: disable=no-member
        result = self._result
        self.close()
        return result

    def submit(self, result) -> None:
        self._result = result
        self.submitted.set()


class Tab:
    _zfs: Dict[str, Ssh] = {}
    _history: List[Result] = []
    _tasks: List[Task] = []

    def __init__(self, spinner, host=None) -> None:
        self._spinner: el.Spinner = spinner
        self.host: str = host
        self._grid: ui.aggrid
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

    def _add_task(self, action: str, command: str, hosts: Union[List[str], None] = None) -> List[Task]:
        if hosts is None:
            hosts = [self.host]
        tasks = []
        for host in hosts:
            tasks.append(Task(action=action, command=command, host=host, status="pending"))
        self._tasks.extend(tasks)
        return tasks

    def _remove_task(self, timestamp: str):
        for task in self._tasks:
            if task.timestamp == timestamp:
                self._tasks.remove(task)
                return task

    def _set_selection(self, mode=None):
        row_selection = "single"
        self._grid.options["columnDefs"][0]["headerCheckboxSelection"] = False
        self._grid.options["columnDefs"][0]["headerCheckboxSelectionFilteredOnly"] = True
        self._grid.options["columnDefs"][0]["checkboxSelection"] = False
        if mode is None:
            pass
        elif mode == "single":
            self._grid.options["columnDefs"][0]["checkboxSelection"] = True
        elif mode == "multiple":
            row_selection = "multiple"
            self._grid.options["columnDefs"][0]["headerCheckboxSelection"] = True
            self._grid.options["columnDefs"][0]["checkboxSelection"] = True
        self._grid.options["rowSelection"] = row_selection
        self._grid.update()

    def get_pipe(self, pipe):
        if pipe not in self.pipes:
            self.pipes[pipe] = {}
        return self.pipes[pipe]

    def get_pipe_status(self, pipe, status):
        if status not in self.get_pipe(pipe):
            self.get_pipe(pipe)[status] = {}
        return self.get_pipe(pipe)[status]

    def process_pipe_data(self, result: Result, data: Any):
        template = PipeTemplate(json.dumps(data))
        json_string = template.safe_substitute(
            name=result.name,
            command=result.command,
            return_code=result.return_code,
            stdout_lines=result.stdout_lines,
            stderr_lines=result.stderr_lines,
            terminated=result.terminated,
            data=result.data,
            trace=result.trace,
            cached=result.cached,
            status=result.status,
            timestamp=result.timestamp,
            failed=result.failed,
            date=result.date,
            time=result.time,
            stdout=result.stdout,
            stderr=result.stderr,
        )
        json_string = json_string.replace("\n", r"\n").replace("\b", r"\b").replace("\f", r"\f").replace("\r", r"\r").replace("\t", r"\t")
        return json.loads(json_string)

    def pipe_result(self, result: Result):
        http = self.get_pipe("http")
        if http.get("enable", False) is True:
            status = "success" if result.status == "success" else "error"
            url = http[status]["url"]
            data = self.process_pipe_data(result=result, data=http[status]["data"])
            headers = http[status]["headers"]
            httpx.post(url=url, json=data, headers=headers)

    @property
    def zfs(self) -> Ssh:
        return self._zfs[self.host]

    @property
    def _zfs_hosts(self) -> List[str]:
        return list(self._zfs.keys())

    @property
    def common(self) -> Dict[str, Any]:
        if "common" not in app.storage.general:
            app.storage.general["common"] = {}
        return app.storage.general["common"]

    @property
    def pipes(self) -> Dict[str, Any]:
        if "pipes" not in self.common:
            self.common["pipes"] = {}
        return self.common["pipes"]
