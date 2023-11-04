from datetime import datetime
from . import SelectionConfirm, Tab
from nicegui import ui
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
