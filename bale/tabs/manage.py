import asyncio
from copy import deepcopy
from nicegui import ui
from . import SelectionConfirm, Tab, Task
from bale.result import Result
from bale import elements as el
from bale.interfaces import zfs
from bale.interfaces import sshdl
import logging

logger = logging.getLogger(__name__)


class Manage(Tab):
    def _build(self):
        with el.WColumn() as col:
            col.tailwind.height("full")
            self._confirm = el.WRow()
            self._confirm.visible = False
            with el.WRow().classes("justify-between").bind_visibility_from(self._confirm, "visible", value=False):
                with ui.row().classes("items-center"):
                    el.SmButton(text="Create", on_click=self._create_snapshot)
                    el.SmButton(text="Destroy", on_click=self._destroy_snapshot)
                    el.SmButton(text="Rename", on_click=self._rename_snapshot)
                    el.SmButton(text="Hold", on_click=self._hold_snapshot)
                    el.SmButton(text="Release", on_click=self._release_snapshot)
                    el.SmButton(text="Browse", on_click=self._browse)
                    el.SmButton(text="Find", on_click=self._find)
                with ui.row().classes("items-center"):
                    self._auto = ui.checkbox("Auto")
                    self._auto.props(f"left-label keep-color color=primary")
                    self._auto.tailwind.text_color("primary")
                    el.SmButton(text="Tasks", on_click=self._display_tasks)
                    el.SmButton(text="Refresh", on_click=self.display_snapshots)
            self._grid = ui.aggrid(
                {
                    "suppressRowClickSelection": True,
                    "rowSelection": "multiple",
                    "paginationAutoPageSize": True,
                    "pagination": True,
                    "defaultColDef": {
                        "resizable": True,
                        "sortable": True,
                        "suppressMovable": True,
                        "sortingOrder": ["asc", "desc"],
                    },
                    "columnDefs": [
                        {
                            "headerName": "Name",
                            "field": "name",
                            "filter": "agTextColumnFilter",
                            "flex": 1,
                        },
                        {"headerName": "Filesystem", "field": "filesystem", "filter": "agTextColumnFilter", "flex": 1},
                        {
                            "headerName": "Used",
                            "field": "used",
                            "maxWidth": 100,
                            ":comparator": """(valueA, valueB, nodeA, nodeB, isInverted) => {
                                                return (nodeA.data.used_bytes > nodeB.data.used_bytes) ? -1 : 1;
                                            }""",
                        },
                        {"headerName": "Creation Date", "field": "creation_date", "filter": "agDateColumnFilter", "maxWidth": 150},
                        {"headerName": "Creation Time", "field": "creation_time", "maxWidth": 150},
                        {"headerName": "Holds", "field": "userrefs", "filter": "agNumberColumnFilter", "maxWidth": 100},
                    ],
                    "rowData": [],
                },
                theme="balham-dark",
            )
            self._grid.tailwind().width("full").height("5/6")

    async def display_snapshots(self):
        self._spinner.visible = True
        self.zfs.invalidate_query()
        snapshots = await self.zfs.snapshots
        await self.zfs.filesystems
        await self.zfs.holds_for_snapshot()
        self._grid.options["rowData"] = list(snapshots.data.values())
        self._grid.update()
        self._spinner.visible = False

    async def _browse(self) -> None:
        self._set_selection(mode="multiple")
        result = await SelectionConfirm(container=self._confirm, label=">BROWSE<")
        if result == "confirm":
            rows = await self._grid.get_selected_rows()
            filesystems = await self.zfs.filesystems
            mount_path = filesystems.data[rows[0]["filesystem"]]["mountpoint"]
            await sshdl.SshFileBrowse(zfs=self.zfs, path=f"{mount_path}/.zfs/snapshot/{rows[0]['name']}")

    async def _find(self) -> None:
        await sshdl.SshFileFind(zfs=self.zfs)

    async def _create_snapshot(self):
        with ui.dialog() as dialog, el.Card():
            self._spinner.visible = True
            with el.DBody():
                with el.WColumn():
                    zfs_hosts = el.DSelect(self._zfs_hosts, value=[self.host], with_input=True, multiple=True, label="Hosts")
                    filesystem_list = await self.zfs.filesystems
                    filesystem_list = list(filesystem_list.data.keys())
                    filesystems = el.DSelect(filesystem_list, with_input=True, multiple=True, label="Filesystems")
                    name = el.DInput(label="Name")
                    recursive = el.DCheckbox("Recursive")
                with el.WRow():
                    el.DButton("Create", on_click=lambda: dialog.submit("create"))
                self._spinner.visible = False

        result = await dialog
        if result == "create":
            for filesystem in filesystems.value:
                self._add_task(
                    "create",
                    zfs.SnapshotCreate(name=f"{filesystem}@{name.value}", recursive=recursive.value).command,
                    hosts=zfs_hosts.value,
                )

    async def _destroy_snapshot(self):
        with ui.dialog() as dialog, el.Card():
            with el.DBody():
                with el.WColumn():
                    zfs_hosts = el.DSelect(self._zfs_hosts, value=[self.host], with_input=True, multiple=True, label="Hosts")
                    recursive = el.DCheckbox("Recursive")
                with el.WRow():
                    el.DButton("Destroy", on_click=lambda: dialog.submit("destroy"))
        self._set_selection(mode="multiple")
        result = await SelectionConfirm(container=self._confirm, label=">DESTROY<")
        if result == "confirm":
            result = await dialog
            if result == "destroy":
                rows = await self._grid.get_selected_rows()
                for row in rows:
                    self._add_task(
                        "destroy",
                        zfs.SnapshotDestroy(name=f"{row['filesystem']}@{row['name']}", recursive=recursive.value).command,
                        hosts=zfs_hosts.value,
                    )
        self._set_selection()

    async def _rename_snapshot(self):
        with ui.dialog() as dialog, el.Card():
            with el.DBody():
                with el.WColumn():
                    zfs_hosts = el.DSelect(self._zfs_hosts, value=[self.host], with_input=True, multiple=True, label="Hosts")
                    mode = el.DSelect(["full", "replace"], value="full", label="Mode")
                    recursive = el.DCheckbox("Recursive")
                    new_name = el.DInput(label="New Name").bind_visibility_from(mode, "value", value="full")
                    original = el.DInput(label="Original").bind_visibility_from(mode, "value", value="replace")
                    replace = el.DInput(label="Replace").bind_visibility_from(mode, "value", value="replace")
                with el.WRow():
                    el.DButton("Rename", on_click=lambda: dialog.submit("rename"))
        self._set_selection(mode="multiple")
        result = await SelectionConfirm(container=self._confirm, label=">RENAME<")
        if result == "confirm":
            result = await dialog
            if result == "rename":
                rows = await self._grid.get_selected_rows()
                for row in rows:
                    if mode.value == "full":
                        rename = new_name.value
                    if mode.value == "replace":
                        rename = row["name"].replace(original.value, replace.value)
                    if row["name"] != rename:
                        self._add_task(
                            "rename",
                            zfs.SnapshotRename(name=f"{row['filesystem']}@{row['name']}", new_name=rename, recursive=recursive.value).command,
                            hosts=zfs_hosts.value,
                        )
                    else:
                        el.notify(f"Skipping rename of {row['filesystem']}@{row['name']}!")
        self._set_selection()

    async def _hold_snapshot(self):
        with ui.dialog() as dialog, el.Card():
            with el.DBody():
                with el.WColumn():
                    zfs_hosts = el.DSelect(self._zfs_hosts, value=[self.host], with_input=True, multiple=True, label="Hosts")
                    tag = el.DInput(label="Tag")
                    recursive = el.DCheckbox("Recursive")
                with el.WRow():
                    el.DButton("Hold", on_click=lambda: dialog.submit("hold"))
        self._set_selection(mode="multiple")
        result = await SelectionConfirm(container=self._confirm, label=">HOLD<")
        if result == "confirm":
            result = await dialog
            if result == "hold":
                rows = await self._grid.get_selected_rows()
                for row in rows:
                    self._add_task(
                        "hold",
                        zfs.SnapshotHold(
                            name=f"{row['filesystem']}@{row['name']}",
                            tag=tag.value,
                            recursive=recursive.value,
                        ).command,
                        hosts=zfs_hosts.value,
                    )
        self._set_selection()

    async def _release_snapshot(self):
        all_tags = []
        with ui.dialog() as dialog, el.Card():
            with el.DBody():
                with el.WColumn():
                    zfs_hosts = el.DSelect(self._zfs_hosts, value=[self.host], with_input=True, multiple=True, label="Hosts")
                    tags = el.DSelect(all_tags, with_input=True, multiple=True, label="Tags")
                    recursive = el.DCheckbox("Recursive")
                with el.WRow():
                    el.DButton("Release", on_click=lambda: dialog.submit("release"))
        self._set_selection(mode="multiple")
        result = await SelectionConfirm(container=self._confirm, label=">RELEASE<")
        if result == "confirm":
            self._spinner.visible = True
            rows = await self._grid.get_selected_rows()
            for row in rows:
                holds = await self.zfs.holds_for_snapshot(f"{row['filesystem']}@{row['name']}")
                for tag in holds.data:
                    if tag not in all_tags:
                        all_tags.append(tag)
            if len(all_tags) > 0:
                tags.update()
                self._spinner.visible = False
                result = await dialog
                if result == "release":
                    if len(tags.value) > 0:
                        for tag in tags.value:
                            for row in rows:
                                self._add_task(
                                    "release",
                                    zfs.SnapshotRelease(
                                        name=f"{row['filesystem']}@{row['name']}",
                                        tag=tag,
                                        recursive=recursive.value,
                                    ).command,
                                    hosts=zfs_hosts.value,
                                )
        self._set_selection()

    async def _display_tasks(self):
        def update_status(timestamp, status, result=None):
            for row in grid.options["rowData"]:
                if timestamp == row.timestamp:
                    row.status = status
                    if result is not None:
                        row.result = deepcopy(result)
                        self.add_history(deepcopy(result))
                    grid.update()
                    return row

        async def apply():
            spinner.visible = True
            rows = await grid.get_selected_rows()
            for row in rows:
                task = Task(**row)
                if task.status == "pending":
                    update_status(task.timestamp, "running")
                    result = await self.zfs.execute(task.command)
                    if result.stdout == "" and result.stderr == "":
                        status = "success"
                        result.failed = False
                    else:
                        status = "error"
                        result.failed = True
                    update_status(task.timestamp, status, result)
            spinner.visible = False

        async def dry_run():
            spinner.visible = True
            rows = await grid.get_selected_rows()
            for row in rows:
                if row["status"] == "pending":
                    await zfs.Zfs().execute(row["command"])
            spinner.visible = False

        async def reset():
            rows = await grid.get_selected_rows()
            for row in rows:
                for grow in grid.options["rowData"]:
                    if row["command"] == grow.command:
                        grow.status = "pending"
                grid.update()

        async def display_result(e):
            if e.args["data"]["result"] is not None:
                result = Result(**e.args["data"]["result"])
                await self._display_result(result=result)

        with ui.dialog() as dialog, el.Card():
            with el.DBody(height="[80vh]", width="[80vw]"):
                with el.WColumn().classes("col"):
                    grid = ui.aggrid(
                        {
                            "suppressRowClickSelection": True,
                            "rowSelection": "multiple",
                            "paginationAutoPageSize": True,
                            "pagination": True,
                            "defaultColDef": {"sortable": True},
                            "columnDefs": [
                                {
                                    "headerName": "Host",
                                    "field": "host",
                                    "headerCheckboxSelection": True,
                                    "headerCheckboxSelectionFilteredOnly": True,
                                    "checkboxSelection": True,
                                    "filter": "agTextColumnFilter",
                                    "maxWidth": 100,
                                },
                                {
                                    "headerName": "Action",
                                    "field": "action",
                                    "filter": "agTextColumnFilter",
                                    "maxWidth": 100,
                                },
                                {
                                    "headerName": "Command",
                                    "field": "command",
                                    "filter": "agTextColumnFilter",
                                    "flex": 1,
                                },
                                {
                                    "headerName": "Status",
                                    "field": "status",
                                    "filter": "agTextColumnFilter",
                                    "maxWidth": 100,
                                    "cellClassRules": {
                                        "text-blue-300": "x == 'pending'",
                                        "text-yellow-300": "x == 'running'",
                                        "text-red-300": "x == 'error'",
                                        "text-green-300": "x == 'success'",
                                    },
                                },
                            ],
                            "rowData": self._tasks,
                        },
                        theme="balham-dark",
                    ).on("cellClicked", lambda e: display_result(e))
                    grid.tailwind().width("full").height("full")
                    grid.call_api_method("selectAll")
                with el.WRow() as row:
                    row.tailwind.height("[40px]")
                    spinner = el.Spinner()
                    el.DButton("Apply", on_click=apply)
                    el.DButton("Dry Run", on_click=dry_run)
                    el.DButton("Reset", on_click=reset)
                    el.DButton("Remove", on_click=lambda: dialog.submit("finish"))
                    el.DButton("Exit", on_click=lambda: dialog.submit("exit"))
                    el.Spinner(master=spinner)

        await dialog
        tasks = list()
        for task in self._tasks:
            if task.status != "success":
                tasks.append(task)
        self._tasks = tasks
        await self.display_snapshots()
