from typing import Any, Dict, List, Union
import asyncio
from datetime import datetime
import json
import string
from apscheduler.triggers.combining import AndTrigger
from apscheduler.triggers.combining import OrTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from . import SelectionConfirm, Tab
from nicegui import ui, Tailwind, events
from bale import elements as el
from bale.result import Result
from bale.interfaces import cli
from bale.interfaces import ssh
from bale.interfaces import zfs
from bale.apps import zab
from bale import scheduler
from cron_validator import CronValidator
from cron_descriptor import get_description
import logging


logger = logging.getLogger(__name__)

job_handlers: Dict[str, Union[cli.Cli, ssh.Ssh]] = {}


def populate_job_handler(app: str, job_id: str, host: str):
    tab = Tab(host=None, spinner=None)
    if job_id not in job_handlers:
        if app == "remote":
            job_handlers[job_id] = ssh.Ssh("data", host=host)
        else:
            job_handlers[job_id] = cli.Cli()
    return job_handlers[job_id]


class CommandTemplate(string.Template):
    delimiter = ""


async def automation_job(**kwargs) -> None:
    if "data" in kwargs:
        jd = json.loads(kwargs["data"])
        command = CommandTemplate(jd["command"])
        tab = Tab(host=None, spinner=None)
        if jd["app"] == "zfs_autobackup":
            d = scheduler.Zfs_Autobackup(**jd)
            populate_job_handler(app=d.app, job_id=d.id, host=d.host)
            if job_handlers[d.id].is_busy is False:
                result = await job_handlers[d.id].execute(command.safe_substitute(host=d.host))
                result.name = d.host
                result.status = "success" if result.return_code == 0 else "error"
                if d.pipe_success is True and result.status == "success":
                    tab.pipe_result(result=result)
                if d.pipe_error is True and result.status != "success":
                    tab.pipe_result(result=result)
                tab.add_history(result=result)
            else:
                logger.warning("Job Skipped!")
        elif jd["app"] == "remote":
            d = scheduler.Automation(**jd)
            populate_job_handler(app=d.app, job_id=d.id, host=d.host)
            if job_handlers[d.id].is_busy is False:
                result = await job_handlers[d.id].execute(command.safe_substitute(host=d.host))
                result.name = d.host
                if d.pipe_success is True and result.status == "success":
                    tab.pipe_result(result=result)
                if d.pipe_error is True and result.status != "success":
                    tab.pipe_result(result=result)
                tab.add_history(result=result)
            else:
                logger.warning("Job Skipped!")
        elif jd["app"] == "local":
            d = scheduler.Automation(**jd)
            populate_job_handler(app=d.app, job_id=d.id, host=d.host)
            if job_handlers[d.id].is_busy is False:
                result = await job_handlers[d.id].execute(command.safe_substitute(host=d.host))
                result.name = d.host
                if d.pipe_success is True and result.status == "success":
                    tab.pipe_result(result=result)
                if d.pipe_error is True and result.status != "success":
                    tab.pipe_result(result=result)
                tab.add_history(result=result)
            else:
                logger.warning("Job Skipped!")


class Automation(Tab):
    def __init__(self, spinner, host: Union[str, None] = None) -> None:
        self._automations: List[Dict[str, str]] = []
        self._selection_mode = None
        self.scheduler = scheduler.Scheduler()
        self.options: Dict[str, Any] = {}
        self.picked_options: Dict[str, str] = {}
        self.triggers: Dict[str, str] = {}
        self.picked_triggers: Dict[str, str] = {}
        self.job_data: Dict[str, str] = {}
        self.job_names: List[str] = []
        self.default_options: Dict[str, str] = {}
        self.build_command: str = ""
        self.target_host: el.DSelect
        self.target_paths: List[str] = [""]
        self.target_path: el.DSelect
        self.fs: Dict[str, Union[str, List[str], Dict[str, str]]]
        self.current_option: el.FSelect
        self.options_scroll: ui.scroll_area
        self.option_controls: Dict[str, Dict[str, Any]] = {}
        self.current_help: ui.tooltip
        self.default_triggers: Dict[str, Dict[str, str]] = {}
        self.current_trigger: el.FSelect
        self.stepper: ui.stepper
        self.auto_name: el.DInput
        self.schedule_em: el.ErrorAggregator
        self.app: el.DSelect
        self.schedule_mode: el.DSelect
        self.ss_spinner: el.Spinner
        self.as_spinner: el.Spinner
        self.command: el.DInput
        self.save: el.DButton
        self.triggers_scroll: ui.scroll_area
        self.trigger_controls: Dict[str, str] = {}
        self.hosts: el.DSelect
        super().__init__(spinner, host)

    def _build(self) -> None:
        with el.WColumn() as col:
            col.tailwind.height("full")
            self._confirm = el.WRow()
            self._confirm.visible = False
            with el.WRow().classes("justify-between").bind_visibility_from(self._confirm, "visible", value=False):
                with ui.row().classes("items-center"):
                    el.SmButton("Create", on_click=self._create_automation)
                    el.SmButton("Remove", on_click=self._remove_automation)
                    el.SmButton("Edit", on_click=self._edit_automation)
                    # el.SmButton("Duplicate", on_click=self._duplicate_automation)
                    el.SmButton("Run Now", on_click=self._run_automation)
                with ui.row().classes("items-center"):
                    el.SmButton(text="Refresh", on_click=self._update_automations)
            self._grid = ui.aggrid(
                {
                    "suppressRowClickSelection": True,
                    "rowSelection": "single",
                    "paginationAutoPageSize": True,
                    "pagination": True,
                    "defaultColDef": {
                        "flex": 1,
                        "resizable": True,
                        "sortable": True,
                        "autoHeight": True,
                        "wrapText": True,
                        "suppressMovable": True,
                        "sortingOrder": ["asc", "desc"],
                    },
                    "columnDefs": [
                        {
                            "headerName": "Name",
                            "field": "name",
                            "filter": "agTextColumnFilter",
                            "maxWidth": 150,
                        },
                        {"headerName": "Command", "field": "command", "filter": "agTextColumnFilter"},
                        {"headerName": "Next Date", "field": "next_run_date", "filter": "agDateColumnFilter", "maxWidth": 100},
                        {"headerName": "Next Time", "field": "next_run_time", "maxWidth": 100},
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
                    "rowData": self._automations,
                },
                theme="balham-dark",
            )
            self._grid.tailwind().width("full").height("5/6")
            self._grid.on("cellClicked", lambda e: self._display_job(e))
            self._update_automations()

    async def _display_job(self, job_data) -> None:
        job_id = f"{job_data.args['data']['name']}@{self.host}"

        for job in self.scheduler.scheduler.get_jobs():
            if job.id == job_id:
                if "data" in job.kwargs:
                    jd = json.loads(job.kwargs["data"])
                    populate_job_handler(app=jd["app"], job_id=job.id, host=self.host)
                    break

        async def run():
            for job in self.scheduler.scheduler.get_jobs():
                if job.id == job_id:
                    job.modify(next_run_time=datetime.now())
                    break

        def terminate():
            if job_id in job_handlers:
                job_handlers[job_id].terminate()

        with ui.dialog() as dialog, el.Card():
            with el.DBody(height="fit", width="fit"):
                with el.WColumn():
                    with el.Card():
                        terminal = cli.Terminal(options={"rows": 20, "cols": 120, "convertEol": True})
                        if job_id in job_handlers:
                            job_handlers[job_id].register_terminal(terminal)
                with el.WRow() as row:
                    row.tailwind.height("[40px]")
                    spinner = el.Spinner()
                    el.LgButton("Run Now", on_click=run)
                    el.LgButton("Terminate", on_click=terminate)
                    el.LgButton("Exit", on_click=lambda: dialog.submit("exit"))
                    el.Spinner(master=spinner)
            if job_id in job_handlers:
                spinner.bind_visibility_from(job_handlers[job_id], "is_busy")

        await dialog
        if job_id in job_handlers:
            job_handlers[job_id].release_terminal(terminal)

    def _update_automations(self) -> None:
        self._automations.clear()
        for job in self.scheduler.scheduler.get_jobs():
            if job.next_run_time is not None:
                next_run_date = job.next_run_time.strftime("%Y/%m/%d")
                next_run_time = job.next_run_time.strftime("%H:%M")
            else:
                next_run_date = "NA"
                next_run_time = "NA"
            if "data" in job.kwargs:
                jd = json.loads(job.kwargs["data"])
                if self.host == jd["host"]:
                    self._automations.append(
                        {
                            "name": job.id.split("@")[0],
                            "command": jd["command"],
                            "next_run_date": next_run_date,
                            "next_run_time": next_run_time,
                            "status": "",
                        }
                    )
        self._grid.update()

    async def _remove_automation(self) -> None:
        self._set_selection(mode="multiple")
        result = await SelectionConfirm(container=self._confirm, label=">REMOVE<")
        if result == "confirm":
            rows = await self._grid.get_selected_rows()
            for row in rows:
                for job in self.scheduler.scheduler.get_jobs():
                    j = job.id.split("@")[0]
                    if j == row["name"]:
                        self.scheduler.scheduler.remove_job(job.id)
                self._automations.remove(row)
            self._grid.update()
        self._set_selection()

    async def _run_automation(self) -> None:
        self._set_selection(mode="multiple")
        result = await SelectionConfirm(container=self._confirm, label=">RUN<")
        if result == "confirm":
            rows = await self._grid.get_selected_rows()
            for row in rows:
                job_id = f"{row['name']}@{self.host}"
                for job in self.scheduler.scheduler.get_jobs():
                    if job_id == job.id:
                        job.modify(next_run_time=datetime.now())
        self._set_selection()

    async def _duplicate_automation(self) -> None:
        rows = await self._grid.get_selected_rows()
        if len(rows) == 1:
            with ui.dialog() as dialog, el.Card():
                with el.DBody():
                    with el.WColumn():
                        host = el.DSelect(self._zfs_hosts, value=self.host, label="Host", with_input=True)
                    with el.WRow():
                        el.DButton("Duplicate", on_click=lambda: dialog.submit("duplicate"))
        result = await dialog
        if result == "confirm":
            for job in self.scheduler.scheduler.get_jobs():
                if job.id == rows[0]["name"]:
                    self.scheduler.scheduler.add_job(
                        automation_job,
                        trigger=build_triggers(),
                        kwargs={"data": json.dumps(auto.to_dict())},
                        id=self.auto_name.value.lower(),
                        coalesce=True,
                        max_instances=1,
                        replace_existing=True,
                    )

    async def _edit_automation(self) -> None:
        self._set_selection(mode="single")
        result = await SelectionConfirm(container=self._confirm, label=">EDIT<")
        if result == "confirm":
            rows = await self._grid.get_selected_rows()
            await self._create_automation(rows[0]["name"])
        self._set_selection()

    async def _add_prop_to_fs(
        self,
        host: str,
        prop: str,
        value: str,
        module: str = "autobackup",
        filesystems: Union[List[str], None] = None,
    ) -> None:
        if filesystems is not None:
            full_prop = f"{module}:{prop}"
            for fs in filesystems:
                result = await self._zfs[host].add_filesystem_prop(filesystem=fs, prop=full_prop, value=value)
                self.add_history(result=result)

    async def _remove_prop_from_all_fs(self, host: str, prop: str, module: str = "autobackup") -> None:
        full_prop = f"{module}:{prop}"
        filesystems_with_prop_result = await self._zfs[host].filesystems_with_prop(full_prop)
        filesystems_with_prop = list(filesystems_with_prop_result.data)
        for fs in filesystems_with_prop:
            result = await self._zfs[host].remove_filesystem_prop(filesystem=fs, prop=full_prop)
            self.add_history(result=result)

    async def _create_automation(self, name: str = "") -> None:
        tw_rows = Tailwind().width("full").align_items("center").justify_content("between")
        self.options = {}
        self.picked_options = {}
        self.triggers = {}
        self.picked_triggers = {}
        self.job_data = {}
        jobs = self.scheduler.scheduler.get_jobs()
        self.job_names = []
        job = None
        for job in jobs:
            j = job.id.split("@")[0]
            self.job_names.append(j)
            if name == j:
                job = self.scheduler.scheduler.get_job(job.id)
                self.job_data.update(json.loads(job.kwargs["data"]))

        def validate_name(n: str):
            if len(n) > 0 and n.islower() and "@" not in n and (n not in self.job_names or name != ""):
                return True
            return False

        def add_option(option, value=""):
            if option is not None and option != "" and option not in self.picked_options and not (self.options[option]["required"] is True and value == ""):
                with self.options_scroll:
                    with ui.row() as option_row:
                        option_row.tailwind(tw_rows)
                        with ui.row() as row:
                            row.tailwind.align_items("center")
                            self.picked_options[option] = value
                            self.option_controls[option] = {
                                "control": el.FInput(
                                    option,
                                    on_change=lambda e, option=option: set_option(option, e.value),
                                    read_only=self.options[option]["control"] == "label",
                                ),
                                "row": option_row,
                            }
                            self.option_controls[option]["control"].value = value
                            with ui.button(icon="help"):
                                ui.tooltip(self.options[option]["description"])
                        if self.options[option]["required"] is not True:
                            ui.button(icon="remove", on_click=lambda _, option=option: remove_option(option)).tailwind.margin("mr-8")
                self.build_command()

        def remove_option(option):
            self.options_scroll.remove(self.option_controls[option]["row"])
            del self.picked_options[option]
            del self.option_controls[option]
            self.build_command()

        def set_option(option, value: str):
            self.picked_options[option] = value
            self.build_command()

        def option_changed(e):
            self.current_help.text = self.options[e.value]["description"]

        async def zab_controls() -> None:
            filesystems = await self.zfs.filesystems
            if isinstance(self.job_data.get("filesystems", {}), dict):
                self.fs = self.job_data.get(
                    "filesystems",
                    {"all": {}, "values": {}, "parent": [], "children": [], "parentchildren": [], "exclude": []},
                )
            else:
                self.fs = {"all": {}, "values": {}, "parent": [], "children": [], "parentchildren": [], "exclude": []}
            if not self.fs["all"]:
                for fs in filesystems.data:
                    self.fs["all"][fs] = ""

            async def target_host_selected() -> None:
                if self.target_host.value != "":
                    if "ssh-target" in self.option_controls:
                        self.option_controls["ssh-target"]["control"].value = self.target_host.value
                    else:
                        add_option("ssh-target", self.target_host.value)
                    fs = await self._zfs[self.target_host.value].filesystems
                    self.target_paths.clear()
                    self.target_paths.append("")
                    self.target_paths.extend(list(fs.data))
                    self.target_path.update()
                    self.target_path.value = ""
                else:
                    if "ssh-target" in self.option_controls:
                        remove_option("ssh-target")
                    self.target_paths.clear()
                    self.target_paths.append("")
                    self.target_path.update()
                    self.target_path.value = ""

            async def target_path_selected() -> None:
                self.build_command()

            def build_command() -> None:
                base = ""
                for key, value in self.picked_options.items():
                    base = base + f" --{key}{f' {value}' if value != '' else ''}"
                target_path = f"{f' {self.target_path.value}' if self.target_path.value != '' else ''}"
                base = base + f" {self.auto_name.value.lower()}" + target_path
                self.command.value = base

            def all_fs_to_lists():
                self.fs["parentchildren"].clear()
                self.fs["parent"].clear()
                self.fs["children"].clear()
                self.fs["exclude"].clear()
                for fs, v in self.fs["all"].items():
                    if v == "":
                        self.fs["parentchildren"].append(fs)
                        self.fs["parent"].append(fs)
                        self.fs["children"].append(fs)
                        self.fs["exclude"].append(fs)
                    elif v == "true":
                        self.fs["parentchildren"].append(fs)
                    elif v == "parent":
                        self.fs["parent"].append(fs)
                    elif v == "child":
                        self.fs["children"].append(fs)
                    elif v == "false":
                        self.fs["exclude"].append(fs)

            def cull_fs_list(e: events.GenericEventArguments, value: str = "false") -> None:
                if e.sender != self.parentchildren:
                    self.parentchildren.disable()
                if e.sender != self.parent:
                    self.parent.disable()
                if e.sender != self.children:
                    self.children.disable()
                if e.sender != self.exclude:
                    self.exclude.disable()
                for fs, v in self.fs["all"].items():
                    if v == value:
                        self.fs["all"][fs] = ""
                for fs in e.sender.value:
                    self.fs["all"][fs] = value
                all_fs_to_lists()
                self.parentchildren.enable()
                self.parent.enable()
                self.children.enable()
                self.exclude.enable()
                self.parentchildren.update()
                self.parent.update()
                self.children.update()
                self.exclude.update()

            if name == "":
                self.default_options = {
                    "verbose": "",
                    "clear-mountpoint": "",
                    "ssh-source": "{host}",
                    "ssh-config": self.zfs.config_path,
                }
            else:
                self.default_options = self.job_data["options"]
            self.options = zab.options
            self.build_command = build_command
            filesystems = await self.zfs.filesystems
            target_host = [""]
            source_hosts = []
            target_host.extend(self._zfs_hosts)
            source_hosts.extend(self._zfs_hosts)
            with ui.row().classes("col") as row:
                row.tailwind.width("[860px]").justify_content("center")
                with ui.column() as col:
                    col.tailwind.height("full").width("[420px]")
                    self.target_host = el.DSelect(target_host, label="Target Host", on_change=target_host_selected)
                    self.target_paths = [""]
                    self.target_path = el.DSelect(self.target_paths, value="", label="Target Path", new_value_mode="add-unique", on_change=target_path_selected)
                    self.hosts = el.DSelect(source_hosts, label="Source Host(s)", multiple=True, with_input=True)
                    all_fs_to_lists()
                    with ui.scroll_area().classes("col"):
                        self.parentchildren = el.DSelect(
                            self.fs["parentchildren"],
                            label="Source Parent And Children",
                            with_input=True,
                            multiple=True,
                            on_change=lambda e: cull_fs_list(e, "true"),
                        )
                        self.parent = el.DSelect(
                            self.fs["parent"],
                            label="Source Parent Only",
                            with_input=True,
                            multiple=True,
                            on_change=lambda e: cull_fs_list(e, "parent"),
                        )
                        self.children = el.DSelect(
                            self.fs["children"],
                            label="Source Children Only",
                            with_input=True,
                            multiple=True,
                            on_change=lambda e: cull_fs_list(e, "child"),
                        )
                        self.exclude = el.DSelect(
                            self.fs["exclude"],
                            label="Exclude",
                            with_input=True,
                            multiple=True,
                            on_change=lambda e: cull_fs_list(e, "false"),
                        )
                with ui.column() as col:
                    col.tailwind.height("full").width("[420px]")
                    options_controls()
            if name != "":
                self.target_host.value = self.job_data.get("target_host", "")
                target_path = self.job_data.get("target_path", "")
                tries = 0
                while target_path not in self.target_path.options and tries < 20:
                    await asyncio.sleep(0.1)
                    tries = tries + 1
                self.target_path.value = target_path
                self.parentchildren.value = self.fs["values"].get("parentchildren", None)
                self.parent.value = self.fs["values"].get("parent", None)
                self.children.value = self.fs["values"].get("children", None)
                self.exclude.value = self.fs["values"].get("exclude", None)
                self.hosts.value = self.job_data.get("hosts", [self.host])
            else:
                self.hosts.value = [self.host]

        def options_controls():
            with ui.row() as row:
                row.tailwind(tw_rows)
                with ui.row() as row:
                    row.tailwind.align_items("center")
                    self.current_option = el.FSelect(list(self.options.keys()), label="Option", with_input=True, on_change=lambda e: option_changed(e))
                    with ui.button(icon="help"):
                        self.current_help = ui.tooltip("")
                ui.button(icon="add", on_click=lambda: add_option(self.current_option.value)).tailwind.margin("mr-8")
            self.options_scroll = ui.scroll_area().classes("col")
            self.options_scroll.tailwind.width("full")
            self.option_controls = {}
            for option, value in self.default_options.items():
                add_option(option, value)
            self.build_command()

        def add_trigger(trigger, value=""):
            if trigger is not None:
                mixed_triggers = False
                if self.schedule_mode.value == "And":
                    for picked_trigger in self.picked_triggers.values():
                        if trigger != picked_trigger["type"]:
                            mixed_triggers = True
                if mixed_triggers is False:
                    with self.triggers_scroll:
                        with ui.row() as trigger_row:
                            with ui.row() as row:
                                ts = str(datetime.now().timestamp())
                                if trigger == "Cron":
                                    trigger_validation = cron_validation
                                    if value == "":
                                        value = "*/30 * * * *"
                                elif trigger == "Interval":
                                    trigger_validation = interval_validation
                                    if value == "":
                                        value = "00:00:00:30:00"
                                self.picked_triggers[ts] = {"type": trigger, "value": value}
                                self.trigger_controls[ts] = {}
                                self.trigger_controls[ts]["row"] = trigger_row
                                row.tailwind.align_items("center")
                                trigger_row.tailwind(tw_rows)
                                self.trigger_controls[ts]["control"] = el.FInput(
                                    trigger,
                                    value=value,
                                    on_change=lambda e, ts=ts: set_trigger(ts, e.value),
                                    validation=trigger_validation,
                                )
                                self.schedule_em.append(self.trigger_controls[ts]["control"])
                                with ui.button(icon="help"):
                                    self.trigger_controls[ts]["tooltip"] = ui.tooltip("")
                                    set_trigger_tooltip(self.trigger_controls[ts])
                            ui.button(
                                icon="remove",
                                on_click=lambda _, ts=ts: remove_trigger(ts),
                            ).tailwind.margin("mr-8")
                else:
                    el.notify("Mixing trigger types in Anding Mode disabled.", type="negative")

        def remove_trigger(ts):
            self.schedule_em.remove(self.trigger_controls[ts]["control"])
            self.triggers_scroll.remove(self.trigger_controls[ts]["row"])
            del self.picked_triggers[ts]
            del self.trigger_controls[ts]

        def set_trigger(ts, value):
            self.picked_triggers[ts]["value"] = value
            set_trigger_tooltip(self.trigger_controls[ts])

        def set_trigger_tooltip(controls):
            if "control" in controls:
                if controls["control"]._props["label"] == "Cron":
                    try:
                        controls["tooltip"].text = get_description(controls["control"].value)
                    except Exception:
                        controls["tooltip"].text = "Invalid Cron Syntax"
                elif controls["control"]._props["label"] == "Interval":
                    controls["tooltip"].text = "WW:DD:HH:MM:SS"
                controls["tooltip"].update()

        def cron_validation(value):
            try:
                CronValidator.parse(value)
                return True
            except Exception:
                return False

        def interval_validation(value: str):
            intervals = value.split(":")
            for interval in intervals:
                if interval.isdecimal() is False:
                    return False
            if len(intervals) != 5:
                return False
            return True

        def trigger_controls():
            self.picked_triggers = {}
            if name == "":
                self.default_triggers = {"id": {"type": "Cron", "value": ""}}
            else:
                self.default_triggers = self.job_data["triggers"]
            with ui.row() as row:
                row.tailwind(tw_rows)
                self.current_trigger = el.FSelect(["Cron", "Interval"], value="Cron", label="Trigger", with_input=True)
                ui.button(icon="add", on_click=lambda: add_trigger(self.current_trigger.value)).tailwind.margin("mr-8")
            self.triggers_scroll = ui.scroll_area().classes("col")
            self.triggers_scroll.tailwind.width("full")
            self.trigger_controls = {}
            for value in self.default_triggers.values():
                add_trigger(value["type"], value["value"])

        def schedule_mode_change():
            self.schedule_em.clear()
            self.schedule_em.append(self.auto_name)
            triggers_col.clear()
            with triggers_col:
                trigger_controls()

        async def schedule_done():
            self.ss_spinner.visible = True
            options_col.clear()
            if self.app.value is not None:
                with options_col:
                    if self.app.value == "zfs_autobackup":
                        await zab_controls()
                    if self.app.value == "local":
                        local_controls()
                    if self.app.value == "remote":
                        remote_controls()
            self.ss_spinner.visible = False
            self.stepper.next()

        def local_controls():
            command_input = el.DInput("Command").bind_value_to(self.command, "value")
            if name != "":
                command_input.value = self.job_data["command"]

        def remote_controls():
            command_input = el.DInput("Command").bind_value_to(self.command, "value")
            self.hosts = el.DSelect(self._zfs_hosts, value=self.host, label="Hosts", with_input=True, multiple=True)
            self.save.bind_enabled_from(self.hosts, "value", backward=lambda x: len(x) > 0)
            if name != "":
                command_input.value = self.job_data["command"]
                self.hosts.value = self.job_data["hosts"]

        def string_to_interval(string: str):
            interval = string.split(":", 4)
            interval = interval + ["0"] * (5 - len(interval))
            return IntervalTrigger(weeks=int(interval[0]), days=int(interval[1]), hours=int(interval[2]), minutes=int(interval[3]), seconds=int(interval[4]))

        def build_triggers():
            combine = AndTrigger if self.schedule_mode.value == "And" else OrTrigger
            triggers = []
            for value in self.picked_triggers.values():
                if "Cron" == value["type"]:
                    triggers.append(CronTrigger().from_crontab(value["value"]))
                elif "Interval" == value["type"]:
                    triggers.append(string_to_interval(value["value"]))
            return combine(triggers)

        def validate_hosts(e):
            if len(e.sender.value) > 0:
                self.schedule_em.enable = True
            else:
                self.schedule_em.enable = False

        with ui.dialog() as automation_dialog, el.Card():
            with el.DBody(height="[90vh]", width="fit"):
                with ui.stepper() as self.stepper:
                    with ui.step("Schedule Setup"):
                        with el.WColumn().classes("col justify-between"):
                            with ui.row().classes("col") as row:
                                row.tailwind.width("[860px]").justify_content("center")
                                with ui.column() as col:
                                    col.tailwind.height("full").width("[420px]")
                                    self.auto_name = el.DInput(label="Name", value=" ", validation=validate_name)
                                    with el.WRow():
                                        self.pipe_success = el.DCheckbox("Pipe Success", value=self.job_data.get("pipe_success", False))
                                        self.pipe_error = el.DCheckbox("Pipe Error", value=self.job_data.get("pipe_error", False))
                                    self.schedule_em = el.ErrorAggregator(self.auto_name)
                                    if name != "":
                                        self.app = el.DInput(label="Application", value=self.job_data["app"]).props("readonly")
                                    else:
                                        self.app = el.DSelect(
                                            ["zfs_autobackup", "local", "remote"],
                                            value="zfs_autobackup",
                                            label="Application",
                                        )
                                    self.schedule_mode = el.DSelect(["Or", "And"], value="Or", label="Schedule Mode", on_change=schedule_mode_change)
                                    triggers_col = el.WColumn().classes("col")
                                    with triggers_col:
                                        trigger_controls()
                            with el.WRow():
                                self.ss_spinner = el.Spinner()
                                with ui.stepper_navigation() as nav:
                                    nav.tailwind.padding("pt-0")
                                    n = el.LgButton("NEXT", on_click=schedule_done)
                                    n.bind_enabled_from(self.schedule_em, "no_errors")
                                el.Spinner(master=self.ss_spinner)
                    with ui.step("Application Setup"):
                        with el.WColumn().classes("col justify-between"):
                            options_col = el.WColumn().classes("col")
                            with el.WColumn():
                                self.command = el.DInput(" ").props("readonly")
                                with el.WRow() as row:
                                    row.tailwind.height("[40px]")
                                    self.as_spinner = el.Spinner()
                                    self.save = el.DButton("SAVE", on_click=lambda: automation_dialog.submit("save"))
                                    el.Spinner(master=self.as_spinner)
            self.auto_name.value = name
            if name != "":
                self.auto_name.props("readonly")
                self.schedule_mode.value = self.job_data["schedule_mode"]
        result = await automation_dialog
        if result == "save":
            auto: Union[scheduler.Automation, scheduler.Zfs_Autobackup]
            auto_name = self.auto_name.value.lower()
            if hasattr(self, "hosts"):
                hosts = self.hosts.value
            else:
                hosts = [self.host]
            if self.app.value == "zfs_autobackup":
                for job in jobs:
                    j = job.id.split("@")[0]
                    if j == auto_name:
                        self.scheduler.scheduler.remove_job(job.id)
                for host in hosts:
                    auto_id = f"{auto_name}@{host}"
                    await self._remove_prop_from_all_fs(host=host, prop=auto_name)
                    await self._add_prop_to_fs(host=host, prop=auto_name, value="true", filesystems=self.parentchildren.value)
                    await self._add_prop_to_fs(host=host, prop=auto_name, value="parent", filesystems=self.parent.value)
                    await self._add_prop_to_fs(host=host, prop=auto_name, value="child", filesystems=self.children.value)
                    await self._add_prop_to_fs(host=host, prop=auto_name, value="false", filesystems=self.exclude.value)
                    self.fs["values"] = {}
                    self.fs["values"]["parentchildren"] = self.parentchildren.value
                    self.fs["values"]["parent"] = self.parent.value
                    self.fs["values"]["children"] = self.children.value
                    self.fs["values"]["exclude"] = self.exclude.value
                    auto = scheduler.Zfs_Autobackup(
                        id=auto_id,
                        hosts=hosts,
                        host=host,
                        command="python -m zfs_autobackup.ZfsAutobackup" + self.command.value,
                        schedule_mode=self.schedule_mode.value,
                        triggers=self.picked_triggers,
                        options=self.picked_options,
                        target_host=self.target_host.value,
                        target_path=self.target_path.value,
                        target_paths=self.target_path.options,
                        filesystems=self.fs,
                        pipe_success=self.pipe_success.value,
                        pipe_error=self.pipe_error.value,
                    )
                    self.scheduler.scheduler.add_job(
                        automation_job,
                        trigger=build_triggers(),
                        kwargs={"data": json.dumps(auto.to_dict())},
                        id=auto_id,
                        coalesce=True,
                        max_instances=1,
                        replace_existing=True,
                    )
            elif self.app.value == "remote":
                for job in jobs:
                    j = job.id.split("@")[0]
                    if j == auto_name:
                        self.scheduler.scheduler.remove_job(job.id)
                for host in hosts:
                    auto_id = f"{auto_name}@{host}"
                    auto = scheduler.Automation(
                        id=auto_id,
                        app=self.app.value,
                        hosts=hosts,
                        host=host,
                        command=self.command.value,
                        schedule_mode=self.schedule_mode.value,
                        triggers=self.picked_triggers,
                        pipe_success=self.pipe_success.value,
                        pipe_error=self.pipe_error.value,
                    )
                    self.scheduler.scheduler.add_job(
                        automation_job,
                        trigger=build_triggers(),
                        kwargs={"data": json.dumps(auto.to_dict())},
                        id=auto_id,
                        coalesce=True,
                        max_instances=1,
                        replace_existing=True,
                    )
            elif self.app.value == "local":
                auto_id = f"{auto_name}@{self.host}"
                auto = scheduler.Automation(
                    id=auto_id,
                    app=self.app.value,
                    hosts=hosts,
                    host=self.host,
                    command=self.command.value,
                    schedule_mode=self.schedule_mode.value,
                    triggers=self.picked_triggers,
                    pipe_success=self.pipe_success.value,
                    pipe_error=self.pipe_error.value,
                )
                self.scheduler.scheduler.add_job(
                    automation_job,
                    trigger=build_triggers(),
                    kwargs={"data": json.dumps(auto.to_dict())},
                    id=auto_id,
                    coalesce=True,
                    max_instances=1,
                    replace_existing=True,
                )
            el.notify(f"Automation {auto_name} stored successfully!", type="positive")
            self._update_automations()
        elif self.stepper.value == "Application Setup":
            pass
