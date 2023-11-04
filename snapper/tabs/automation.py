from typing import Any, Dict, List, Union
import asyncio
from datetime import datetime
import json
from apscheduler.triggers.combining import AndTrigger
from apscheduler.triggers.combining import OrTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from . import Tab
from nicegui import ui, Tailwind
from snapper import elements as el
from snapper.result import Result
from snapper.interfaces import cli
from snapper.interfaces import ssh
from snapper.interfaces import zfs
from snapper.apps import zab
from snapper import scheduler
from cron_validator import CronValidator
from cron_descriptor import get_description
import logging

logger = logging.getLogger(__name__)

job_handlers: Dict[str, Any] = {}


async def automation_job(**kwargs) -> None:
    if "data" in kwargs:
        jd = json.loads(kwargs["data"])
        tab = Tab(host=None, spinner=None)
        if jd["app"] == "local":
            d = scheduler.Automation(**jd)
            if d.id not in job_handlers:
                job_handlers[d.id] = cli.Cli()
            if job_handlers[d.id].is_busy is False:
                result = await job_handlers[d.id].execute(d.command)
                tab.host = d.hosts[0]
                tab.add_history(result=result)
            else:
                logger.warning("Job Skipped!")
        elif jd["app"] == "zfs_autobackup":
            d = scheduler.Zfs_Autobackup(**jd)
            if d.id not in job_handlers:
                job_handlers[d.id] = cli.Cli()
            if job_handlers[d.id].is_busy is False:
                result = await job_handlers[d.id].execute("python -m zfs_autobackup.ZfsAutobackup" + d.command)
                tab.host = d.hosts[0]
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
        self.filesystems: el.DSelect
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
            with el.WRow().classes("justify-between"):
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
                    "defaultColDef": {"flex": 1, "resizable": True, "sortable": True, "autoHeight": True, "wrapText": True},
                    "columnDefs": [
                        {
                            "headerName": "Name",
                            "field": "name",
                            "headerCheckboxSelection": True,
                            "headerCheckboxSelectionFilteredOnly": True,
                            "checkboxSelection": True,
                            "filter": "agTextColumnFilter",
                            "maxWidth": 110,
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
        async def run():
            for job in self.scheduler.scheduler.get_jobs():
                if job.id == job_data.args["data"]["name"]:
                    job.modify(next_run_time=datetime.now())

        def terminate():
            if job_data.args["data"]["name"] in job_handlers:
                job_handlers[job_data.args["data"]["name"]].terminate()

        with ui.dialog() as dialog, el.Card():
            with el.DBody(height="[90vh]", width="[90vw]"):
                with el.WColumn():
                    terminal = cli.Terminal(options={"rows": 30, "cols": 120, "convertEol": True})
                    if job_data.args["data"]["name"] in job_handlers:
                        job_handlers[job_data.args["data"]["name"]].register_terminal(terminal)
                with el.WRow() as row:
                    row.tailwind.height("[40px]")
                    spinner = el.Spinner()
                    el.LgButton("Run Now", on_click=run)
                    el.LgButton("Terminate", on_click=terminate)
                    el.LgButton("Exit", on_click=lambda: dialog.submit("exit"))
                    el.Spinner(master=spinner)
            spinner.bind_visibility_from(job_handlers[job_data.args["data"]["name"]], "is_busy")

        await dialog
        if job_data.args["data"]["name"] in job_handlers:
            job_handlers[job_data.args["data"]["name"]].release_terminal(terminal)

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
                if self.host in jd["hosts"]:
                    self._automations.append(
                        {
                            "name": job.id,
                            "command": jd["command"],
                            "next_run_date": next_run_date,
                            "next_run_time": next_run_time,
                            "status": "",
                        }
                    )
        self._grid.update()

    async def _remove_automation(self) -> None:
        rows = await self._grid.get_selected_rows()
        if len(rows) == 1:
            self.scheduler.scheduler.remove_job(rows[0]["name"])
            self._automations.remove(rows[0])
            self._grid.update()

    async def _run_automation(self) -> None:
        rows = await self._grid.get_selected_rows()
        if len(rows) == 1:
            for job in self.scheduler.scheduler.get_jobs():
                if job.id == rows[0]["name"]:
                    job.modify(next_run_time=datetime.now())

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
        rows = await self._grid.get_selected_rows()
        if len(rows) > 0:
            await self._create_automation(rows[0]["name"])

    async def _add_prop_to_fs(self, prop: str, module: str = "autobackup", filesystems: Union[List[str], None] = None) -> None:
        if filesystems is not None:
            full_prop = f"{module}:{prop}"
            filesystems_with_prop_result = await self.zfs.filesystems_with_prop(full_prop)
            filesystems_with_prop = list(filesystems_with_prop_result.data)
            for fs in filesystems:
                if fs in filesystems_with_prop:
                    filesystems_with_prop.remove(fs)
                else:
                    result = await self.zfs.add_filesystem_prop(filesystem=fs, prop=full_prop, value="parent")
                    self.add_history(result=result)
            for fs in filesystems_with_prop:
                result = await self.zfs.remove_filesystem_prop(filesystem=fs, prop=full_prop)
                self.add_history(result=result)

    async def _remove_prop_from_all_fs(self, prop: str, module: str = "autobackup") -> None:
        full_prop = f"{module}:{prop}"
        filesystems_with_prop_result = await self.zfs.filesystems_with_prop(full_prop)
        filesystems_with_prop = list(filesystems_with_prop_result.data)
        for fs in filesystems_with_prop:
            result = await self.zfs.remove_filesystem_prop(filesystem=fs, prop=full_prop)
            self.add_history(result=result)

    async def _create_automation(self, name: str = "") -> None:
        tw_rows = Tailwind().width("full").align_items("center").justify_content("between")
        self.options = {}
        self.picked_options = {}
        self.triggers = {}
        self.picked_triggers = {}
        self.job_data = {}
        if name != "":
            job = self.scheduler.scheduler.get_job(name)
            self.job_data.update(json.loads(job.kwargs["data"]))
        else:
            job = None
        jobs = self.scheduler.scheduler.get_jobs()
        self.job_names = []
        for job in jobs:
            self.job_names.append(job.id)

        def validate_name(n: str):
            if len(n) > 0 and n.islower() and (n not in self.job_names or name != ""):
                return True
            return False

        def add_option(option, value=""):
            if (
                option is not None
                and option != ""
                and option not in self.picked_options
                and not (self.options[option]["required"] is True and value == "")
            ):
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

        def set_option(option, value):
            self.picked_options[option] = value
            self.build_command()

        def option_changed(e):
            self.current_help.text = self.options[e.value]["description"]

        async def zab_controls():
            async def target_host_selected():
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

            async def target_path_selected():
                self.build_command()

            def build_command():
                base = ""
                for key, value in self.picked_options.items():
                    base = base + f" --{key}{f' {value}' if value != '' else ''}"
                target_path = f"{f' {self.target_path.value}' if self.target_path.value != '' else ''}"
                base = base + f" {self.auto_name.value.lower()}" + target_path
                self.command.value = base

            if name == "":
                self.default_options = {
                    "verbose": "",
                    "clear-mountpoint": "",
                    "ssh-source": self.zfs.host,
                    "ssh-config": self.zfs.config_path,
                }
            else:
                self.default_options = self.job_data["options"]
            self.options = zab.options
            self.build_command = build_command
            filesystems = await self.zfs.filesystems
            hosts = [""]
            hosts.extend(self._zfs_hosts)
            self.target_host = el.DSelect(hosts, label="Target Host", on_change=target_host_selected)
            self.target_paths = [""]
            self.target_path = el.DSelect(self.target_paths, value="", label="Target Path", on_change=target_path_selected)
            self.filesystems = el.DSelect(list(filesystems.data), label="Source Filesystems", with_input=True, multiple=True)
            self.save.bind_enabled_from(self.filesystems, "value", backward=lambda x: len(x) > 0)
            options_controls()
            if name != "":
                self.target_host.value = self.job_data.get("target_host", "")
                target_path = self.job_data.get("target_path", "")
                tries = 0
                while target_path not in self.target_path.options and tries < 20:
                    await asyncio.sleep(0.1)
                    tries = tries + 1
                self.target_path.value = target_path
                self.filesystems.value = self.job_data.get("filesystems", "")

        def options_controls():
            with ui.row() as row:
                row.tailwind(tw_rows)
                with ui.row() as row:
                    row.tailwind.align_items("center")
                    self.current_option = el.FSelect(
                        list(self.options.keys()), label="Option", with_input=True, on_change=lambda e: option_changed(e)
                    )
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
            return IntervalTrigger(
                weeks=int(interval[0]), days=int(interval[1]), hours=int(interval[2]), minutes=int(interval[3]), seconds=int(interval[4])
            )

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
            with el.DBody(height="[90vh]", width="[480px]"):
                with ui.stepper().props("flat").classes("full-size-stepper") as self.stepper:
                    with ui.step("Schedule Setup"):
                        with el.WColumn().classes("col justify-between"):
                            with el.WColumn().classes("col"):
                                self.auto_name = el.DInput(label="Name", value=" ", validation=validate_name)
                                self.schedule_em = el.ErrorAggregator(self.auto_name)
                                if name != "":
                                    self.app = el.DInput(label="Application", value=self.job_data["app"]).props("readonly")
                                else:
                                    self.app = el.DSelect(
                                        ["zfs_autobackup", "local", "remote"],
                                        value="zfs_autobackup",
                                        label="Application",
                                    )
                                self.schedule_mode = el.DSelect(
                                    ["Or", "And"], value="Or", label="Schedule Mode", on_change=schedule_mode_change
                                )
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
            if hasattr(self, "hosts"):
                hosts = self.hosts.value
            else:
                hosts = [self.host]
            if self.app.value == "zfs_autobackup":
                await self._add_prop_to_fs(prop=self.auto_name.value.lower(), filesystems=self.filesystems.value)
                auto = scheduler.Zfs_Autobackup(
                    id=self.auto_name.value.lower(),
                    hosts=hosts,
                    command=self.command.value,
                    schedule_mode=self.schedule_mode.value,
                    triggers=self.picked_triggers,
                    options=self.picked_options,
                    target_host=self.target_host.value,
                    target_path=self.target_path.value,
                    target_paths=self.target_path.options,
                    filesystems=self.filesystems.value,
                )
                if self.auto_name.value.lower() not in job_handlers:
                    job_handlers[self.auto_name.value.lower()] = cli.Cli()
            else:
                auto = scheduler.Automation(
                    id=self.auto_name.value.lower(),
                    app=self.app.value,
                    hosts=hosts,
                    command=self.command.value,
                    schedule_mode=self.schedule_mode.value,
                    triggers=self.picked_triggers,
                )
                if self.auto_name.value.lower() not in job_handlers:
                    job_handlers[self.auto_name.value.lower()] = cli.Cli()
            self.scheduler.scheduler.add_job(
                automation_job,
                trigger=build_triggers(),
                kwargs={"data": json.dumps(auto.to_dict())},
                id=self.auto_name.value.lower(),
                coalesce=True,
                max_instances=1,
                replace_existing=True,
            )
            el.notify(f"Automation {self.auto_name.value.lower()} stored successfully!", type="positive")
            self._update_automations()
        elif self.stepper.value == "Application Setup":
            pass
