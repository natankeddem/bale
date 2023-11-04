from nicegui import app, ui
import re
from datetime import datetime
import asyncio
from bale import elements as el
import bale.logo as logo
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

    def build(self):
        self._header = ui.header(bordered=True).classes("bg-dark q-pt-sm q-pb-xs")
        self._header.visible = False
        with self._header:
            with ui.row().classes("w-full h-12 justify-between items-center"):
                self._tabs = ui.tabs()
                with self._tabs:
                    self._tab["manage"] = ui.tab(name="Manage").classes("text-secondary")
                    self._tab["automation"] = ui.tab(name="Automation").classes("text-secondary")
                    self._tab["history"] = ui.tab(name="History").classes("text-secondary")
                    self._tab["settings"] = ui.tab(name="Settings").classes("text-secondary")
                with ui.row().classes("items-center"):
                    self._spinner = el.Spinner()
                    self._host_display = ui.label().classes("text-secondary text-h4")
                    logo.show()
        self._tab_panels = (
            ui.tab_panels(self._tabs, value="Manage", on_change=lambda e: self._tab_changed(e), animated=False)
            .classes("w-full h-full")
            .bind_visibility_from(self._header)
        )

    async def _tab_changed(self, e):
        if e.value == "Manage":
            await self._manage.display_snapshots()
        if e.value == "History":
            self._history.update_history()

    def _build_tab_panels(self):
        with self._tab_panels:
            with ui.tab_panel(self._tab["manage"]).style("height: calc(100vh - 61px)"):
                self._manage = Manage(spinner=self._spinner, host=self._host)
            with ui.tab_panel(self._tab["automation"]).style("height: calc(100vh - 61px)"):
                self._automation = Automation(spinner=self._spinner, host=self._host)
            with ui.tab_panel(self._tab["history"]).style("height: calc(100vh - 61px)"):
                self._history = History(spinner=self._spinner, host=self._host)
            with ui.tab_panel(self._tab["settings"]).style("height: calc(100vh - 61px)"):
                ui.label("settings tab")

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
