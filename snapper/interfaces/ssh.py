from typing import Dict, Union
import os
import asyncio
from pathlib import Path
from snapper.result import Result
from snapper.interfaces.cli import Cli


def get_hosts(path):
    path = f"{Path(path).resolve()}/config"
    hosts = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines:
                if line.startswith("Host "):
                    hosts.append(line.split(" ")[1].strip())
        return hosts
    except FileNotFoundError:
        return []


async def get_public_key(path: str) -> str:
    path = Path(path).resolve()
    if "id_rsa.pub" not in os.listdir(path) or "id_rsa" not in os.listdir(path):
        await Cli().shell(f"""ssh-keygen -t rsa -N "" -f {path}/id_rsa""")
    with open(f"{path}/id_rsa.pub", "r", encoding="utf-8") as reader:
        return reader.read()


class Ssh:
    def __init__(
        self, path: str, host: str, hostname: str = "", username: str = "", password: Union[str, None] = None, seperator: bytes = b"\n"
    ) -> None:
        self._raw_path: str = path
        self._path: Path = Path(path).resolve()
        self.host: str = host
        self.password: Union[str, None] = password
        self.use_key: bool = False
        if password is None:
            self.use_key = True
        self._key_path: str = f"{self._path}/id_rsa"
        self._base_cmd: str = ""
        self._full_cmd: str = ""
        self._cli = Cli(seperator=seperator)
        self._config_path: str = f"{self._path}/config"
        self._config: Dict[str, Dict[str, str]] = {}
        self.read_config()
        self.hostname: str = hostname or self._config.get(host, {}).get("HostName", "")
        self.username: str = username or self._config.get(host, {}).get("User", "")
        self.set_config()

    def read_config(self) -> None:
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for line in lines:
                    line = line.strip()
                    if line == "" or line.startswith("#"):
                        continue
                    if line.startswith("Host "):
                        current_host = line.split(" ")[1].strip()
                        self._config[current_host] = {}
                    else:
                        key, value = line.split(" ", 1)
                        self._config[current_host][key.strip()] = value.strip()
        except FileNotFoundError:
            self._config = {}

    def write_config(self) -> None:
        with open(self._config_path, "w", encoding="utf-8") as f:
            for host, config in self._config.items():
                f.write(f"Host {host}\n")
                for key, value in config.items():
                    f.write(f"    {key} {value}\n")
                f.write("\n")

    def set_config(self) -> None:
        self._config[self.host] = {
            "IdentityFile": self._key_path,
            "PasswordAuthentication": "no",
            "StrictHostKeychecking": "no",
            "IdentitiesOnly": "yes",
        }
        if self.hostname != "":
            self._config[self.host]["HostName"] = self.hostname
        if self.username != "":
            self._config[self.host]["User"] = self.username
        self.write_config()

    def remove(self) -> None:
        del self._config[self.host]
        self.write_config()

    async def execute(self, command: str) -> Result:
        self._base_cmd = f"{'' if self.use_key else f'sshpass -p {self.password} '} ssh -F {self._config_path} {self.host}"
        self._full_cmd = f"{self._base_cmd} {command}"
        return await self._cli.execute(self._full_cmd)

    async def send_key(self) -> Result:
        await get_public_key(self._raw_path)
        cmd = (
            f"sshpass -p {self.password} "
            f"ssh-copy-id -o IdentitiesOnly=yes -i {self._key_path} "
            f"-o StrictHostKeychecking=no {self.username}@{self.hostname}"
        )
        return await self._cli.execute(cmd)

    @property
    def config_path(self):
        return self._config_path
