import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Union
from pathlib import Path
from functools import cache
from datetime import datetime
import time
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore


@dataclass(kw_only=True)
class Automation:
    id: str = ""
    name: str = ""
    app: str = "remote"
    hosts: List[str] = field(default_factory=list)
    host: str = ""
    command: str = ""
    schedule_mode: str = ""
    triggers: Dict[str, str] = field(default_factory=dict)
    options: Dict[str, Any] = field(default_factory=dict)
    pipe_success: bool = False
    pipe_error: bool = False
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__


@dataclass(kw_only=True)
class Zfs_Autobackup(Automation):
    app: str = "zfs_autobackup"
    prop: str = "autobackup:{name}"
    target_host: str = ""
    target_path: str = ""
    target_paths: List[str] = field(default_factory=list)
    parentchildren: List[str] = field(default_factory=list)
    parent: List[str] = field(default_factory=list)
    children: List[str] = field(default_factory=list)
    exclude: List[str] = field(default_factory=list)


class _Scheduler:
    def __init__(self) -> None:
        path = Path("data").resolve()
        url = f"sqlite:///{path}/scheduler.sqlite"
        self.scheduler = AsyncIOScheduler()
        self.scheduler.add_jobstore("sqlalchemy", url=url)

    async def start(self) -> None:
        self.scheduler.start()
        while True:
            await asyncio.sleep(1000)


@cache
def Scheduler() -> _Scheduler:
    return _Scheduler()
