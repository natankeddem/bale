from typing import Any, AsyncIterable, Coroutine, Dict, List, Optional, Union, Tuple
from pathlib import Path
import stat
from datetime import datetime
import uuid
from nicegui import app, background_tasks, events, ui
from fastapi.responses import StreamingResponse
import asyncssh
from bale import elements as el
from bale.interfaces.zfs import Ssh


def format_bytes(size: Union[int, float]) -> str:
    power = 2**10
    n = 0
    suffixs = {0: "", 1: "K", 2: "M", 3: "G", 4: "T"}
    while size > power:
        size = size / power
        n += 1
    s = ("%.3f" % size).rstrip("0").rstrip(".")
    return f"{s}{suffixs[n]}B"


class SshFileBrowse(ui.dialog):
    def __init__(self, zfs: Ssh, path: str = "/") -> None:
        super().__init__()
        self._zfs: Ssh = zfs
        self._starting_path: str = path
        self._path: Path
        self.path = path
        self._ssh: Optional[asyncssh.SSHClientConnection] = None
        self._sftp: Optional[asyncssh.SFTPClient] = None
        ui.timer(0, self._display, once=True)
        self._card: el.Card
        self._grid: ui.aggrid

    async def _display(self):
        with self, el.Card() as self._card:
            with el.DBody(width="[560px]"):
                with el.WColumn().classes("col"):
                    self._grid = ui.aggrid(
                        {
                            "defaultColDef": {"flex": 1, "sortable": True, "suppressMovable": True, "sortingOrder": ["asc", "desc"]},
                            "columnDefs": [
                                {
                                    "field": "name",
                                    "headerName": "Name",
                                    "flex": 1,
                                    "sort": "desc",
                                    ":comparator": """(valueA, valueB, nodeA, nodeB, isInverted) => {
                                        if (nodeA.data.priority === nodeB.data.priority) {
                                            return (valueA > valueB) ? -1 : 1;
                                        } else {
                                            if (isInverted) {
                                                return (nodeA.data.priority > nodeB.data.priority) ? -1 : 1;
                                            } else{
                                                return (nodeA.data.priority > nodeB.data.priority) ? 1 : -1;
                                            }
                                        }
                                        }""",
                                },
                                {
                                    "field": "size",
                                    "headerName": "Size",
                                    "maxWidth": 100,
                                    ":comparator": """(valueA, valueB, nodeA, nodeB, isInverted) => {
                                        if (nodeA.data.priority === nodeB.data.priority) {
                                            return (nodeA.data.bytes > nodeB.data.bytes) ? -1 : 1;
                                        } else {
                                            if (isInverted) {
                                                return (nodeA.data.priority > nodeB.data.priority) ? -1 : 1;
                                            } else{
                                                return (nodeA.data.priority > nodeB.data.priority) ? 1 : -1;
                                            }
                                        }
                                        }""",
                                },
                            ],
                            "rowSelection": "single",
                        },
                        html_columns=[0],
                        theme="balham-dark",
                    )
                    self._grid.on("cellDoubleClicked", self._handle_double_click)
                    self._grid.tailwind().width("full").height("full")
                with el.WRow() as row:
                    row.tailwind.height("[40px]")
                    el.DButton("Download", on_click=self._start_download)
                    ui.button("Exit", on_click=lambda: self.submit("exit"))
        await self._update_handler()

    async def _connect(self) -> Tuple[asyncssh.SSHClientConnection, asyncssh.SFTPClient]:
        ssh = await asyncssh.connect(self._zfs.hostname, username=self._zfs.username, client_keys=[self._zfs.key_path])
        sftp = await ssh.start_sftp_client()
        return ssh, sftp

    async def _close_handlers(self) -> None:
        if self._sftp is not None:
            self._sftp.exit()
            await self._sftp.wait_closed()
        if self._ssh is not None:
            self._ssh.close()
            await self._ssh.wait_closed()

    async def _ls(self, path) -> List[Dict[str, Union[str, datetime]]]:
        infos = []
        if self._sftp is not None:
            file_attrs = await self._sftp.readdir(path)
            for file_attr in file_attrs:
                if file_attr.filename in ["", ".", ".."]:
                    continue
                info = self._decode_attributes(file_attr.attrs)
                info["name"] = str(Path(path).joinpath(str(file_attr.filename)))
                infos.append(info)
        return infos

    def _decode_attributes(self, attributes: asyncssh.SFTPAttrs) -> Dict[str, Union[int, None, str, datetime]]:
        if attributes.permissions is not None:
            if stat.S_ISDIR(attributes.permissions):
                kind = "directory"
            elif stat.S_ISREG(attributes.permissions):
                kind = "file"
            elif stat.S_ISLNK(attributes.permissions):
                kind = "link"
            else:
                kind = "unknown"
        else:
            kind = "unknown"

        return {
            "size": attributes.size,
            "type": kind,
            "gid": attributes.gid,
            "uid": attributes.uid,
            "time": datetime.utcfromtimestamp(attributes.atime),
            "mtime": datetime.utcfromtimestamp(attributes.mtime),
            "permissions": attributes.permissions,
        }

    async def _update_handler(self) -> None:
        self._grid.call_api_method("showLoadingOverlay")
        if self._ssh is None or self._sftp is None:
            self._ssh, self._sftp = await self._connect()
        paths = await self._ls(self.path)
        priorities = {"directory": "b", "file": "c", "link": "d", "unknown": "e"}
        self._grid.options["rowData"] = [
            {
                "name": f"📁 <strong>{Path(p['name']).name}</strong>" if p["type"] == "directory" else Path(p["name"]).name,
                "type": p["type"],
                "path": p["name"],
                "size": format_bytes(p["size"]),
                "bytes": p["size"],
                "priority": priorities[p["type"]],
            }
            for p in paths
        ]
        if self.path != self._starting_path:
            self._grid.options["rowData"].insert(
                0,
                {"name": "📁 <strong>..</strong>", "type": "directory", "path": self.parent, "priority": "a"},
            )
        self._grid.update()
        self._grid.call_api_method("hideOverlay")

    async def _handle_double_click(self, e: events.GenericEventArguments) -> None:
        self.path = e.args["data"]["path"]
        if e.args["data"]["type"] == "directory":
            await self._update_handler()
        else:
            await self._start_download(e)

    async def _start_download(self, e: events.GenericEventArguments = None) -> None:
        if e is None:
            rows = await ui.run_javascript(f"getElement({self._grid.id}).gridOptions.api.getSelectedRows()")
            row = rows[0]
        else:
            row = e.args["data"]
        download_url: str = f"/download/{uuid.uuid4()}.txt"

        async def read_blocks() -> AsyncIterable[str]:
            offset = 0
            blocksize = 65536
            ssh, sftp = await self._connect()
            async with sftp.open(row["path"], "rb") as remote_file:
                while True:
                    chunk = await remote_file.read(size=blocksize, offset=offset)
                    if not chunk:
                        app.routes[:] = [route for route in app.routes if route.path != download_url]
                        break
                    yield chunk
                    offset = offset + blocksize
            sftp.exit()
            await sftp.wait_closed()
            ssh.close()
            await ssh.wait_closed()

        with self._card:

            @app.get(download_url)
            def download() -> StreamingResponse:
                headers = {"Content-Disposition": f"attachment; filename={row['name']}"}
                return StreamingResponse(read_blocks(), media_type="text/plain", headers=headers)

        ui.download(download_url)

    def __await__(self) -> None:
        ui.timer(0.0001, self._close_handlers, once=True)
        return super().__await__()

    @property
    def path(self) -> str:
        return str(self._path)

    @path.setter
    def path(self, path: str) -> None:
        self._path = Path(path)

    @property
    def parent(self) -> str:
        return str(Path(self._path).parent)


class SshFileFind(SshFileBrowse):
    async def _display(self):
        with self, el.Card() as self._card:
            with el.DBody(height="fit", width="[90vw]"):
                with el.WColumn().classes("col"):
                    filesystems = await self._zfs.filesystems
                    self._filesystem = el.DSelect(list(filesystems.data.keys()), label="filesystem", with_input=True, on_change=self._update_handler)
                    with el.WRow():
                        self._pattern = ui.input("Pattern").classes("col").on("keydown.enter", handler=self._update_handler)
                        el.LgButton(icon="search", on_click=self._update_handler)
                    self._grid = ui.aggrid(
                        {
                            "defaultColDef": {"flex": 1, "sortable": True, "suppressMovable": True, "sortingOrder": ["asc", "desc"]},
                            "columnDefs": [
                                {"field": "name", "headerName": "Name", "flex": 1, "sort": "desc", "resizable": True},
                                {"field": "location", "headerName": "Location", "flex": 1, "resizable": True},
                                {
                                    "headerName": "Modified",
                                    "field": "modified_timestamp",
                                    "filter": "agTextColumnFilter",
                                    "maxWidth": 125,
                                    ":cellRenderer": """(data) => {
                                        var date = new Date(data.value * 1000).toLocaleString(undefined, {dateStyle: 'short', timeStyle: 'short', hour12: false});;
                                        return date;
                                    }""",
                                },
                                {
                                    "field": "size",
                                    "headerName": "Size",
                                    "maxWidth": 100,
                                    ":comparator": """(valueA, valueB, nodeA, nodeB, isInverted) => {
                                            return (nodeA.data.bytes > nodeB.data.bytes) ? -1 : 1;
                                        }""",
                                },
                            ],
                            "rowSelection": "single",
                        },
                        html_columns=[0],
                        theme="balham-dark",
                    )
                    self._grid.on("cellDoubleClicked", self._handle_double_click)
                    self._grid.tailwind().height("[320px]").width("full")
                with el.WRow() as row:
                    row.tailwind.height("[40px]")
                    el.DButton("Download", on_click=self._start_download)
                    ui.button("Exit", on_click=lambda: self.submit("exit"))
                self._grid.call_api_method("hideOverlay")

    async def _update_handler(self) -> None:
        if len(self._pattern.value) > 0 and self._filesystem is not None:
            self._grid.call_api_method("showLoadingOverlay")
            self._filesystem.props("readonly")
            self._pattern.props("readonly")
            files = await self._zfs.find_files_in_snapshots(filesystem=self._filesystem.value, pattern=self._pattern.value)
            self._grid.options["rowData"] = files.data
            if files.truncated is True:
                el.notify("Too many files found, truncating list.", type="warning")
            self._grid.update()
            self._filesystem.props(remove="readonly")
            self._pattern.props(remove="readonly")
            self._grid.call_api_method("hideOverlay")

    async def _handle_double_click(self, e: events.GenericEventArguments) -> None:
        await self._start_download(e)
