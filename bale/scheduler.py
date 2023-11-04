import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Union
from pathlib import Path
from functools import cache
from datetime import datetime
import time
from apscheduler.schedulers.asyncio import AsyncIOScheduler


@dataclass(kw_only=True)
class Automation:
    id: str
    app: str
    hosts: List[str]
    host: str
    command: str
    schedule_mode: str
    triggers: Dict[str, str]
    options: Union[Dict[str, Any], None] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__


@dataclass(kw_only=True)
class Zfs_Autobackup(Automation):
    app: str = "zfs_autobackup"
    execute_mode: str = "local"
    target_host: str
    target_path: str
    target_paths: List[str]
    filesystems: Dict[str, Union[str, List[str], Dict[str, str]]]


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
