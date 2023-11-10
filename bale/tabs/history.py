from datetime import datetime
import json
from . import SelectionConfirm, Tab
from nicegui import ui, events
from bale import elements as el
from bale.result import Result
from bale.interfaces import zfs
import logging

logger = logging.getLogger(__name__)


class History(Tab):
    def _build(self):
        async def display_result(e):
            if e.args["data"] is not None:
                result = Result().from_dict(e.args["data"])
                await self._display_result(result)

        with el.WColumn() as col:
            col.tailwind.height("full")
            self._confirm = el.WRow()
            self._confirm.visible = False
            with el.WRow().classes("justify-between").bind_visibility_from(self._confirm, "visible", value=False):
                with ui.row().classes("items-center"):
                    el.SmButton(text="Remove", on_click=self._remove_history)
                    el.SmButton(text="HTTP Pipe", on_click=self._setup_http_pipe)
                with ui.row().classes("items-center"):
                    el.SmButton(text="Refresh", on_click=lambda _: self._grid.update())
            self._grid = ui.aggrid(
                {
                    "suppressRowClickSelection": True,
                    "rowSelection": "multiple",
                    "paginationAutoPageSize": True,
                    "pagination": True,
                    "defaultColDef": {"resizable": True, "sortable": True, "suppressMovable": True, "sortingOrder": ["asc", "desc"]},
                    "columnDefs": [
                        {
                            "headerName": "Host",
                            "field": "name",
                            "filter": "agTextColumnFilter",
                            "maxWidth": 100,
                        },
                        {
                            "headerName": "Command",
                            "field": "command",
                            "filter": "agTextColumnFilter",
                            "flex": 1,
                        },
                        {"headerName": "Date", "field": "date", "filter": "agDateColumnFilter", "maxWidth": 100},
                        {"headerName": "Time", "field": "time", "maxWidth": 100},
                        {
                            "headerName": "Status",
                            "field": "status",
                            "filter": "agTextColumnFilter",
                            "maxWidth": 100,
                            "cellClassRules": {
                                "text-red-300": "x == 'error'",
                                "text-green-300": "x == 'success'",
                            },
                        },
                    ],
                    "rowData": self._history,
                },
                theme="balham-dark",
            )
            self._grid.tailwind().width("full").height("5/6")
            self._grid.on("cellClicked", lambda e: display_result(e))

    def update_history(self):
        self._grid.update()

    async def _remove_history(self):
        self._set_selection(mode="multiple")
        result = await SelectionConfirm(container=self._confirm, label=">REMOVE<")
        if result == "confirm":
            rows = await self._grid.get_selected_rows()
            for row in rows:
                self._history.remove(row)
            self._grid.update()
        self._set_selection()

    async def _setup_http_pipe(self):
        http = {}

        def set_url(status: str, url: str) -> None:
            http[status]["url"] = url

        def set_content(status: str, e: events.JsonEditorChangeEventArguments) -> None:
            http[status]["data"] = e.content["json"]["data"]
            http[status]["headers"] = e.content["json"]["headers"]

        def show_controls(status):
            if status not in http:
                http[status] = {}
            url = el.DInput(label="URL", on_change=lambda e: set_url(status, e.value))
            rps = Result().properties
            sv = []
            for rp in rps:
                sv.append(f"{{{rp}}}")
            properties = {"content": {"json": {"data": {}, "headers": {}, "Special Values": sv}}}
            editor = el.JsonEditor(properties=properties, on_change=lambda e: set_content(status, e))
            url.value = self.get_pipe_status("http", status).get("url", "https://www.ntfy.sh/")
            editor.properties["content"]["json"]["data"] = self.get_pipe_status("http", status).get(
                "data",
                {
                    "topic": "mytopic",
                    "tags": ["turtle"],
                    "title": "Successful Automation Run for {name}",
                    "message": "{stdout}",
                },
            )
            editor.properties["content"]["json"]["headers"] = self.get_pipe_status("http", status).get("headers", {"Authorization": "Bearer tk_..."})
            editor.update()
            http[status]["data"] = editor.properties["content"]["json"]["data"]
            http[status]["headers"] = editor.properties["content"]["json"]["headers"]

        with ui.dialog() as host_dialog, el.Card():
            with el.DBody(height="[90vh]", width="[560px]"):
                with ui.stepper() as stepper:
                    with ui.step("General"):
                        with el.WColumn().classes("col justify-start"):
                            enable = el.DCheckbox("Enable")
                            enable.value = self.get_pipe("http").get("enable", False)
                        el.LgButton("NEXT", on_click=lambda _: stepper.next())
                    with ui.step("On Success"):
                        with el.WColumn().classes("col justify-start"):
                            show_controls(status="success")
                        el.LgButton("NEXT", on_click=lambda _: stepper.next())
                    with ui.step("On Error"):
                        with el.WColumn().classes("col justify-start"):
                            show_controls(status="error")
                        el.DButton("SAVE", on_click=lambda: host_dialog.submit("save"))

        result = await host_dialog
        if result == "save":
            http["enable"] = enable.value
            self.pipes["http"] = http
