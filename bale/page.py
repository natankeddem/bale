from nicegui import app, ui
from bale import elements as el
from bale.drawer import Drawer
from bale.content import Content
from bale.interfaces import cli
import logging

logger = logging.getLogger(__name__)


def build():
    @ui.page("/")
    def page():
        app.add_static_files("/static", "static")
        ui.add_head_html(
            """
<style>
    .full-size-stepper,
    .full-size-stepper .q-stepper__content,
    .full-size-stepper .q-stepper__step-content,
    .full-size-stepper .q-stepper__step-inner {
        height: 100%;
        width: 100%;
        display: flex;
        flex-direction: column;
    }
    .multi-line-notification {
        white-space: pre-line;
    }
</style>
"""
        )
        cli.load_terminal_css()
        ui.colors(
            primary=el.orange,
            secondary=el.orange,
            accent="#d946ef",
            dark=el.dark,
            positive="#21ba45",
            negative="#c10015",
            info="#31ccec",
            warning="#f2c037",
        )
        column = ui.column()
        content = Content()
        drawer = Drawer(column, content.host_selected, content.hide)
        drawer.build()
        content.build()
