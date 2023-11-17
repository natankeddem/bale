import asyncio
from nicegui import app, Client, ui
from bale import elements as el
from bale.drawer import Drawer
from bale.content import Content
from bale.interfaces import cli
import logging

logger = logging.getLogger(__name__)


def build():
    @ui.page("/")
    async def index(client: Client) -> None:
        app.add_static_files("/static", "static")
        el.load_element_css()
        cli.load_terminal_css()
        ui.colors(
            primary=el.orange,
            secondary=el.orange,
            accent=el.orange,
            dark=el.dark,
            positive="#21BA45",
            negative="#C10015",
            info="#5C8984",
            warning="#F2C037",
        )
        column = ui.column()
        content = Content()
        drawer = Drawer(column, content.host_selected, content.hide)
        drawer.build()
        await content.build()
