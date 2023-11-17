import asyncio
from nicegui import ui
from bale import elements as el
import bale.logo as logo
from bale.tabs import Tab
from bale.tabs.manage import Manage
from bale.tabs.history import History
from bale.tabs.automation import Automation
import logging

logger = logging.getLogger(__name__)


class Content:
    def __init__(self) -> None:
        self._header = None
        self._tabs = None
        self._tab = {}
        self._spinner = None
        self._host = None
        self._tab_panels = None
        self._grid = None
        self._tab_panel = {}
        self._host = None
        self._tasks = []
        self._manage = None
        self._automation = None
        self._history = None

    async def build(self):
        self._header = ui.header(bordered=True).classes("bg-dark q-pt-sm q-pb-xs")
        self._header.tailwind.border_color(f"[{el.orange}]").min_width("[920px]")
        self._header.visible = False
        with self._header:
            with ui.row().classes("w-full h-12 justify-between items-center"):
                self._tabs = ui.tabs()
                with self._tabs:
                    self._tab["manage"] = ui.tab(name="Manage").classes("text-secondary")
                    self._tab["automation"] = ui.tab(name="Automation").classes("text-secondary")
                    self._tab["history"] = ui.tab(name="History").classes("text-secondary")
                with ui.row().classes("items-center"):
                    self._spinner = el.Spinner()
                    self._host_display = ui.label().classes("text-secondary text-h4")
                    logo.show()
        self._tab_panels = (
            ui.tab_panels(self._tabs, value="Manage", on_change=lambda e: self._tab_changed(e), animated=False).classes("w-full h-full").bind_visibility_from(self._header)
        )
        default = Tab(spinner=None).common.get("default", "")
        if default != "":
            await self.host_selected(default)

    async def _tab_changed(self, e):
        if e.value == "Manage":
            await self._manage.display_snapshots()
        if e.value == "History":
            self._history.update_history()

    def _build_tab_panels(self):
        with self._tab_panels:
            with el.ContentTabPanel(self._tab["manage"]):
                self._manage = Manage(spinner=self._spinner, host=self._host)
            with el.ContentTabPanel(self._tab["automation"]):
                self._automation = Automation(spinner=self._spinner, host=self._host)
            with el.ContentTabPanel(self._tab["history"]):
                self._history = History(spinner=self._spinner, host=self._host)

    async def host_selected(self, name):
        self._host = name
        self._host_display.text = name
        self.hide()
        self._build_tab_panels()
        self._header.visible = True
        await self._manage.display_snapshots()

    def hide(self):
        self._header.visible = False
        self._tab_panels.clear()
