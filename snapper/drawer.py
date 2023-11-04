from nicegui import ui
from snapper import elements as el
from snapper.tabs import Tab
from snapper.interfaces import ssh
import logging

logger = logging.getLogger(__name__)


class Drawer(object):
    def __init__(self, main_column, on_click, hide_content) -> None:
        self._on_click = on_click
        self._hide_content = hide_content
        self._main_column = main_column
        self._header_row = None
        self._table = None
        self._name = ""
        self._hostname = ""
        self._username = ""
        self._password = ""
        self._buttons = {}
        self._selection_mode = None

    def build(self):
        with ui.left_drawer(top_corner=True, bordered=True).props("width=200").classes("q-pt-sm q-pb-xs"):
            with el.WColumn():
                self._header_row = el.WRow().classes("justify-between")
                self._header_row.tailwind().height("12")
                with self._header_row:
                    with ui.row():
                        el.IButton(icon="add", on_click=self._display_host_dialog)
                        self._buttons["remove"] = el.IButton(icon="remove", on_click=lambda: self._modify_host("remove"))
                        self._buttons["edit"] = el.IButton(icon="edit", on_click=lambda: self._modify_host("edit"))
                    ui.label(text="HOSTS").classes("text-secondary")
                self._table = (
                    ui.table(
                        [
                            {
                                "name": "name",
                                "label": "Name",
                                "field": "name",
                                "required": True,
                                "align": "center",
                                "sortable": True,
                            }
                        ],
                        [],
                        row_key="name",
                        pagination={"rowsPerPage": 0, "sortBy": "name"},
                        on_select=lambda e: self._selected(e),
                    )
                    .on("rowClick", self._clicked, [[], ["name"], None])
                    .props("hide-header hide-pagination hide-selected-banner dense flat bordered binary-state-sort")
                    .classes("w-full text-secondary")
                )
                self._table.visible = False
                for name in ssh.get_hosts("data"):
                    self._add_host_to_table(name)

    def _add_host_to_table(self, name):
        if len(name) > 0:
            for row in self._table.rows:
                if name == row["name"]:
                    return
            self._table.add_rows({"name": name})
            self._table.visible = True
            Tab.register_connection(name)

    async def _display_host_dialog(self, name=""):
        save = None

        async def send_key():
            s = ssh.Ssh(
                "data", host=host_input.value, hostname=hostname_input.value, username=username_input.value, password=password_input.value
            )
            result = await s.send_key()
            if result.stdout.strip() != "":
                el.notify(result.stdout.strip(), multi_line=True, type="positive")
            if result.stderr.strip() != "":
                el.notify(result.stderr.strip(), multi_line=True, type="negative")

        with ui.dialog() as host_dialog, el.Card():
            with el.DBody(height="[560px]", width="[360px]"):
                with el.WColumn():
                    host_input = el.DInput(label="Host", value=" ")
                    hostname_input = el.DInput(label="Hostname", value=" ")
                    username_input = el.DInput(label="Username", value=" ")
                    save_em = el.ErrorAggregator(host_input, hostname_input, username_input)
                    with el.Card() as c:
                        c.tailwind.width("full")
                        password_input = el.DInput(label="Password", value=" ").props("type=password")
                        send_em = el.ErrorAggregator(hostname_input, username_input, password_input)
                        el.DButton("SEND KEY", on_click=send_key).bind_enabled_from(send_em, "no_errors").tailwind.width("full")
                    with el.Card() as c:
                        c.tailwind.width("full")
                        with ui.scroll_area() as s:
                            s.tailwind.height("[160px]")
                            public_key = await ssh.get_public_key("data")
                            ui.label(public_key).classes("text-secondary break-all")
                el.DButton("SAVE", on_click=lambda: host_dialog.submit("save")).bind_enabled_from(save_em, "no_errors")
            host_input.value = name
            if name != "":
                s = ssh.Ssh(path="data", host=name)
                hostname_input.value = s.hostname
                username_input.value = s.username

        result = await host_dialog
        if result == "save":
            if name != "" and name != host_input.value:
                for row in self._table.rows:
                    if name == row["name"]:
                        self._table.remove_rows(row)
            ssh.Ssh(path="data", host=host_input.value, hostname=hostname_input.value, username=username_input.value)
            self._add_host_to_table(host_input.value)

    def _modify_host(self, mode):
        self._hide_content()
        self._selection_mode = mode
        if mode is None:
            self._table._props["selected"] = []
            self._table.props("selection=none")
            for icon, button in self._buttons.items():
                button.props(f"icon={icon}")
        elif self._buttons[mode]._props["icon"] == "close":
            self._selection_mode = None
            self._table._props["selected"] = []
            self._table.props("selection=none")
            for icon, button in self._buttons.items():
                button.props(f"icon={icon}")
        else:
            self._table.props("selection=single")
            for icon, button in self._buttons.items():
                if mode == icon:
                    button.props("icon=close")
                else:
                    button.props(f"icon={icon}")

    async def _selected(self, e):
        self._hide_content()
        if self._selection_mode == "edit":
            if len(e.selection) > 0:
                await self._display_host_dialog(name=e.selection[0]["name"])
        if self._selection_mode == "remove":
            if len(e.selection) > 0:
                for row in e.selection:
                    ssh.Ssh(path="data", host=row["name"]).remove()
                    self._table.remove_rows(row)
        self._modify_host(None)

    async def _clicked(self, e):
        if "name" in e.args[1]:
            host = e.args[1]["name"]
            if self._on_click is not None:
                await self._on_click(host)
