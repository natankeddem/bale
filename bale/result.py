from typing import Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from copy import deepcopy
import time


@dataclass(kw_only=True)
class Result:
    name: str = ""
    command: str = ""
    return_code: Optional[int] = 0
    stdout_lines: List[str] = field(default_factory=list)
    stderr_lines: List[str] = field(default_factory=list)
    terminated: bool = False
    data: Any = None
    trace: str = ""
    cached: bool = False
    status: str = "success"
    timestamp: float = field(default_factory=time.time)

    @property
    def failed(self) -> bool:
        return False if self.status == "success" else True

    @property
    def date(self) -> str:
        return datetime.fromtimestamp(self.timestamp).strftime("%Y/%m/%d")

    @property
    def time(self) -> str:
        return datetime.fromtimestamp(self.timestamp).strftime("%H:%M:%S")

    @property
    def stdout(self) -> str:
        return "".join(self.stdout_lines)

    @property
    def stderr(self) -> str:
        return "".join(self.stderr_lines)

    @property
    def properties(self) -> List:
        return list(self.to_dict().keys())

    def to_dict(self):
        d = deepcopy(self.__dict__)
        d["failed"] = self.failed
        d["date"] = self.date
        d["time"] = self.time
        d["stdout"] = self.stdout
        d["stderr"] = self.stderr
        return d

    def from_dict(self, d):
        self.name = d["name"]
        self.command = d["command"]
        self.return_code = d["return_code"]
        self.stdout_lines = d["stdout_lines"]
        self.stderr_lines = d["stderr_lines"]
        self.terminated = d["terminated"]
        self.data = d["data"]
        self.trace = d["trace"]
        self.cached = d["cached"]
        self.status = d["status"]
        self.timestamp = d["timestamp"]
        return self
