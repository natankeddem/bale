from nicegui import app, ui
import logging

logger = logging.getLogger(__name__)


def load_defaults() -> None:
    ui.card.default_style("max-width: none")
    ui.card.default_props("flat bordered")
    ui.input.default_props("outlined dense hide-bottom-space")
    ui.button.default_props("outline dense")
    ui.select.default_props("outlined dense dense-options")
    ui.checkbox.default_props("dense")
    ui.stepper.default_props("flat")
    ui.stepper.default_classes("full-size-stepper")


def build():
    @ui.page("/")
    def page() -> None:
        app.add_static_files("/static", "static")
        load_defaults()
        from bale import elements as el
        from bale.drawer import Drawer
        from bale.content import Content
        from bale.interfaces import cli

        el.load_element_css()
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
