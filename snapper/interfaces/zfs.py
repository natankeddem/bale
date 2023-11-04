from typing import Any, Dict, Union
import re
from datetime import datetime
from dataclasses import dataclass
from snapper.result import Result
from snapper.interfaces import ssh
from snapper import elements as el
import logging

logger = logging.getLogger(__name__)


@dataclass(kw_only=True)
class Snapshot:
    name: str
    action: str = "snapshot"
    recursive: bool = False

    @property
    def command(self):
        return f"zfs {self.action}{self._recursive} {self.name}"

    @property
    def _recursive(self):
        return " -r" if self.recursive else " "


@dataclass(kw_only=True)
class SnapshotCreate(Snapshot):
    pass


@dataclass(kw_only=True)
class SnapshotDestroy(Snapshot):
    action: str = "destroy"


@dataclass(kw_only=True)
class SnapshotRename(Snapshot):
    new_name: str
    action: str = "rename"

    @property
    def command(self):
        return f"{super().command} {self.new_name}"


@dataclass(kw_only=True)
class SnapshotHold(Snapshot):
    action: str = "hold"
    tag: str = "keep"

    @property
    def command(self):
        return f"zfs {self.action}{self._recursive} {self.tag} {self.name}"


@dataclass(kw_only=True)
class SnapshotRelease(SnapshotHold):
    action: str = "release"


def format_bytes(size: Union[int, float]) -> str:
    # 2**10 = 1024
    power = 2**10
    n = 0
    suffixs = {0: "", 1: "K", 2: "M", 3: "G", 4: "T"}
    while size > power:
        size = size / power
        n += 1
    s = ("%.3f" % size).rstrip("0").rstrip(".")
    return f"{s}{suffixs[n]}B"


class Zfs:
    def __init__(self) -> None:
        self._last_run_time: Dict[str, datetime] = {}
        self._last_data: Dict[str, Any] = {}

    def notify(self, command: str):
        el.notify(command)

    async def execute(self, command: str) -> Result:
        self.notify(command)
        return Result(command=command)

    def invalidate_query(self, query: Union[str, None] = None):
        if query is None:
            self._last_run_time = {}
        else:
            if query in self._last_run_time:
                del self._last_run_time[query]

    def is_query_ready_to_execute(self, query: str, timeout: int):
        now = datetime.now()
        if query in self._last_run_time:
            if (now - self._last_run_time[query]).total_seconds() > timeout:
                self._last_run_time[query] = now
                return True
            else:
                return False
        else:
            self._last_run_time[query] = now
            return True

    async def add_filesystem_prop(self, filesystem: str, prop: str, value: str) -> Result:
        result = await self.execute(f"zfs set {prop}={value} {filesystem}")
        return result

    async def remove_filesystem_prop(self, filesystem: str, prop: str) -> Result:
        result = await self.execute(f"zfs inherit {prop} {filesystem}")
        return result

    async def filesystems_with_prop(self, prop: str) -> Result:
        result = await self.execute(f"zfs get -Hp -t filesystem,volume {prop}")
        filesystems = []
        for line in result.stdout_lines:
            matches = re.match("^(?P<name>[^\t]+)\t(?P<property>[^\t]+)\t(?P<value>[^\t]+)\t(?P<source>[^\n]+)", line)
            if matches is not None:
                md = matches.groupdict()
                if md["property"] == prop and md["source"] == "local":
                    filesystems.append(md["name"])
            result = Result(data=filesystems, cached=False)
        return result

    async def holds_for_snapshot(self, snapshot: str = "") -> Result:
        query = "holds_for_snapshot"
        if self.is_query_ready_to_execute(query, 60):
            result = await self.execute("zfs holds -H -r $(zfs list -t snapshot -H -o name)")
            tags: Dict[str, list[str]] = {}
            for line in result.stdout_lines:
                matches = re.match("^(?P<filesystem>[^@]+)@(?P<name>[^\t]+)\t(?P<tag>[^\t]+)\t(?P<creation>[^\n]+)", line)
                if matches is not None:
                    md = matches.groupdict()
                    s = f"{md['filesystem']}@{md['name']}"
                    if s not in tags:
                        tags[s] = []
                    tags[s].append(md["tag"])
                self._last_data[query] = tags
                if snapshot in self._last_data[query]:
                    result.data = self._last_data[query][snapshot]
                else:
                    result.data = []
        else:
            if snapshot in self._last_data[query]:
                data = self._last_data[query][snapshot]
            else:
                data = []
            result = Result(data=data, cached=True)
        return result

    @property
    async def filesystems(self) -> Result:
        query = "filesystems"
        if self.is_query_ready_to_execute(query, 60):
            result = await self.execute("zfs list -Hp -t filesystem -o name,used,avail,refer,mountpoint")
            filesystems = dict()
            for line in result.stdout_lines:
                matches = re.match(
                    "^(?P<filesystem>[^\t]+)\t(?P<used_bytes>[^\t]+)\t(?P<avail_bytes>[^\t]+)\t(?P<refer_bytes>[^\t]+)\t(?P<mountpoint>[^\n]+)",
                    line,
                )
                if matches is not None:
                    md = matches.groupdict()
                    filesystem = md.pop("filesystem")
                    filesystems[filesystem] = md
            self._last_data[query] = filesystems
            result.data = self._last_data[query]
        else:
            result = Result(data=self._last_data[query], cached=True)
        return result

    @property
    async def snapshots(self) -> Result:
        query = "snapshots"
        if self.is_query_ready_to_execute(query, 60):
            result = await self.execute("zfs list -Hp -t snapshot -o name,used,creation,userrefs")
            snapshots = dict()
            for line in result.stdout_lines:
                matches = re.match(
                    "^(?P<filesystem>[^@]+)@(?P<name>[^\t]+)\t(?P<used_bytes>[^\t]+)\t(?P<creation>[^\t]+)\t(?P<userrefs>[^\n]+)", line
                )
                if matches is not None:
                    md = matches.groupdict()
                    md["creation_date"] = datetime.fromtimestamp(int(md["creation"])).strftime("%Y/%m/%d")
                    md["creation_time"] = datetime.fromtimestamp(int(md["creation"])).strftime("%H:%M")
                    md["used"] = format_bytes(int(md["used_bytes"]))
                    snapshot = f"{md['filesystem']}@{md['name']}"
                    snapshots[snapshot] = md
            self._last_data[query] = snapshots
            result.data = self._last_data[query]
        else:
            result = Result(data=self._last_data[query], cached=True)
        return result


class Ssh(ssh.Ssh, Zfs):
    def __init__(self, path: str, host: str, hostname: str = "", username: str = "", password: Union[str, None] = None) -> None:
        super().__init__(path, host, hostname, username, password)
        Zfs.__init__(self)

    def notify(self, command: str):
        el.notify(f"<{self.host}> {command}")

    async def execute(self, command: str) -> Result:
        self.notify(command)
        result = await super().execute(command)
        if result.stderr != "":
            el.notify(result.stderr, type="negative")
        result.name = self.host
        return result
