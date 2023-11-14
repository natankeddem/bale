from typing import Any, Dict, Union
import re
from datetime import datetime
from dataclasses import dataclass
from bale.result import Result
from bale.interfaces import ssh
from bale import elements as el
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
        command = command if len(command) < 160 else command[:160] + "..."
        el.notify(command)

    async def execute(self, command: str, notify: bool = True) -> Result:
        if notify:
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
        if query in self._last_run_time and query in self._last_data:
            if (now - self._last_run_time[query]).total_seconds() > timeout:
                return True
            else:
                return False
        else:
            return True

    def set_query_time(self, query: str):
        self._last_run_time[query] = datetime.now()

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

    async def holds_for_snapshot(self, snapshot: Union[str, None] = None) -> Result:
        query = "holds_for_snapshot"
        if self.is_query_ready_to_execute(query, 60):
            with_holds = []
            if snapshot is None:
                snapshots = await self.snapshots
                for _name, _data in snapshots.data.items():
                    if int(_data["userrefs"]) > 0:
                        with_holds.append(_name)
                with_holds = " ".join(with_holds)
            else:
                with_holds = [snapshot]
            if len(with_holds) > 0:
                result = await self.execute(f"zfs holds -H -r {with_holds}", notify=False)
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
                return Result(data=[])
        else:
            if snapshot in self._last_data[query]:
                data = self._last_data[query][snapshot]
            else:
                data = []
            result = Result(data=data, cached=True)
        self.set_query_time(query)
        return result

    async def find_files_in_snapshots(self, filesystem: str, pattern: str) -> Result:
        filesystems = await self.filesystems
        if filesystem in filesystems.data.keys():
            if "mountpoint" in filesystems.data[filesystem]:
                command = f"find {filesystems.data[filesystem]['mountpoint']}/.zfs/snapshot -type f -name '{pattern}' -printf '%h\t%f\t%s\t%T@\n'"
                result = await self.execute(command=command, notify=False)
                files = []
                for line in result.stdout_lines:
                    matches = re.match(
                        "^(?P<location>[^\t]+)\t(?P<name>[^\t]+)\t(?P<bytes>[^\t]+)\t(?P<modified_timestamp>[^\n]+)",
                        line,
                    )
                    if matches is not None:
                        md = matches.groupdict()
                        md["path"] = f"{md['location']}/{md['name']}"
                        md["size"] = format_bytes(int(md["bytes"]))
                        md["modified_datetime"] = datetime.fromtimestamp(float(md["modified_timestamp"])).strftime("%Y/%m/%d %H:%M:%S")
                        files.append(md)
                result.data = files
                return result
        return Result()

    @property
    async def filesystems(self) -> Result:
        query = "filesystems"
        if self.is_query_ready_to_execute(query, 60):
            result = await self.execute("zfs list -Hp -t filesystem -o name,used,avail,refer,mountpoint", notify=False)
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
        self.set_query_time(query)
        return result

    @property
    async def snapshots(self) -> Result:
        query = "snapshots"
        if self.is_query_ready_to_execute(query, 60):
            result = await self.execute("zfs list -Hp -t snapshot -o name,used,creation,userrefs", notify=False)
            snapshots = dict()
            for line in result.stdout_lines:
                matches = re.match("^(?P<filesystem>[^@]+)@(?P<name>[^\t]+)\t(?P<used_bytes>[^\t]+)\t(?P<creation>[^\t]+)\t(?P<userrefs>[^\n]+)", line)
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
        self.set_query_time(query)
        return result


class Ssh(ssh.Ssh, Zfs):
    def __init__(self, path: str, host: str, hostname: str = "", username: str = "", password: Union[str, None] = None) -> None:
        super().__init__(path, host, hostname, username, password)
        Zfs.__init__(self)

    def notify(self, command: str):
        super().notify(f"<{self.host}> {command}")

    async def execute(self, command: str, notify: bool = True) -> Result:
        if notify:
            self.notify(command)
        result = await super().execute(command)
        if result.stderr != "":
            el.notify(result.stderr, type="negative")
        result.name = self.host
        return result
