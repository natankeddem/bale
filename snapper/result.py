from typing import Any, List
from dataclasses import dataclass, field
from datetime import datetime
import time


@dataclass(kw_only=True)
class Result:
    name: str = ""
    command: str = ""
    return_code: int = 0
    stdout_lines: List[str] = field(default_factory=list)
    stderr_lines: List[str] = field(default_factory=list)
    terminated: bool = False
    data: Any = None
    failed: bool = False
    trace: str = ""
    cached: bool = False
    status: str = "success"
    timestamp: float = field(default_factory=time.time)

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

    def to_dict(self):
        return self.__dict__
