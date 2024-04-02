from typing import Any, Callable, Dict, List, Literal, Optional, Union
from nicegui import ui, app, Tailwind  # type: ignore
from nicegui.elements.spinner import SpinnerTypes  # type: ignore
from nicegui.elements.tabs import Tab  # type: ignore
from nicegui.tailwind_types.height import Height  # type: ignore
from nicegui.tailwind_types.width import Width  # type: ignore
from nicegui.elements.mixins.validation_element import ValidationElement  # type: ignore
from nicegui.events import GenericEventArguments, handle_event  # type: ignore
from bale.interfaces import cli
import logging

logger = logging.getLogger(__name__)

orange = "#E97451"
dark = "#0E1210"


def load_element_css():
    ui.add_head_html(
        f"""
    <style>
        .bale-colors,
        .q-table--dark, 
        .q-table--dark .q-table__bottom,
        .q-table--dark td,
        .q-table--dark th,
        .q-table--dark thead,
        .q-table--dark tr,
        .q-table__card--dark,
        body.body--dark .q-drawer, 
        body.body--dark .q-footer, 
        body.body--dark .q-header {{
            color: {orange} !important;
            border-color: {orange} !important;
        }}
        .full-size-stepper,
        .full-size-stepper .q-stepper__content,
        .full-size-stepper .q-stepper__step-content,
        .full-size-stepper .q-stepper__step-inner {{
            height: 100%;
            width: 100%;
            display: flex;
            flex-direction: column;
            align-items: center;
        }}
        .multi-line-notification {{
            white-space: pre-line;
        }}
        .q-drawer--bordered{{
            border-color: {orange} !important;
        }}
    </style>
    """
    )
    ui.add_head_html('<link href="static/jse-theme-dark.css" rel="stylesheet">')


class ErrorAggregator:
    def __init__(self, *elements: ValidationElement) -> None:
        self.elements: list[ValidationElement] = list(elements)
        self.enable: bool = True

    def clear(self):
        self.elements.clear()

    def append(self, element: ValidationElement):
        self.elements.append(element)

    def remove(self, element: ValidationElement):
        self.elements.remove(element)

    @property
    def no_errors(self) -> bool:
        if len(self.elements) > 0:
            validators = all(validation(element.value) for element in self.elements for validation in element.validation.values())
            return self.enable and validators
        else:
            return True


class WColumn(ui.column):
    def __init__(self) -> None:
        super().__init__()
        self.tailwind.width("full").align_items("center")


class DBody(ui.column):
    def __init__(self, height: Height = "[480px]", width: Width = "[240px]") -> None:
        super().__init__()
        self.tailwind.align_items("center").justify_content("between")
        self.tailwind.height(height).width(width)


class WRow(ui.row):
    def __init__(self) -> None:
        super().__init__()
        self.tailwind.width("full").align_items("center").justify_content("center")


class Card(ui.card):
    def __init__(self) -> None:
        super().__init__()
        self.tailwind.border_color(f"[{orange}]")


class DInput(ui.input):
    def __init__(
        self,
        label: str | None = None,
        *,
        placeholder: str | None = None,
        value: str = " ",
        password: bool = False,
        password_toggle_button: bool = False,
        on_change: Callable[..., Any] | None = None,
        autocomplete: List[str] | None = None,
        validation: Callable[..., Any] = bool,
    ) -> None:
        super().__init__(
            label,
            placeholder=placeholder,
            value=value,
            password=password,
            password_toggle_button=password_toggle_button,
            on_change=on_change,
            autocomplete=autocomplete,
            validation={"": validation},
        )
        self.tailwind.width("full")
        if value == " ":
            self.value = ""


class VInput(ui.input):
    def __init__(
        self,
        label: str | None = None,
        *,
        placeholder: str | None = None,
        value: str = " ",
        password: bool = False,
        password_toggle_button: bool = False,
        on_change: Callable[..., Any] | None = None,
        autocomplete: List[str] | None = None,
        invalid_characters: str = "",
        invalid_values: List[str] = [],
        max_length: int = 64,
        check: Callable[..., Any] | None = None,
    ) -> None:
        def checks(value: str) -> bool:
            if value is None or value == "" or len(value) > max_length:
                return False
            for invalid_character in invalid_characters:
                if invalid_character in value:
                    return False
            for invalid_value in invalid_values:
                if invalid_value == value:
                    return False
            if check is not None:
                check_status = check(value)
                if check_status is not None:
                    return check_status
            return True

        super().__init__(
            label,
            placeholder=placeholder,
            value=value,
            password=password,
            password_toggle_button=password_toggle_button,
            on_change=on_change,
            autocomplete=autocomplete,
            validation={"": lambda value: checks(value)},
        )
        self.tailwind.width("full")
        if value == " ":
            self.value = ""


class FInput(ui.input):
    def __init__(
        self,
        label: str | None = None,
        *,
        placeholder: str | None = None,
        value: str = " ",
        password: bool = False,
        password_toggle_button: bool = False,
        on_change: Callable[..., Any] | None = None,
        autocomplete: List[str] | None = None,
        validation: Callable[..., Any] = bool,
        read_only: bool = False,
    ) -> None:
        super().__init__(
            label,
            placeholder=placeholder,
            value=value,
            password=password,
            password_toggle_button=password_toggle_button,
            on_change=on_change,
            autocomplete=autocomplete,
            validation={} if read_only else {"": validation},
        )
        self.tailwind.width("64")
        if value == " ":
            self.value = ""
        if read_only:
            self.props("readonly")


class DSelect(ui.select):
    def __init__(
        self,
        options: Union[List, Dict],
        *,
        label: Optional[str] = None,
        value: Any = None,
        on_change: Optional[Callable[..., Any]] = None,
        with_input: bool = False,
        new_value_mode: Optional[Literal["add", "add-unique", "toggle"]] = None,
        multiple: bool = False,
        clearable: bool = False,
    ) -> None:
        super().__init__(options, label=label, value=value, on_change=on_change, with_input=with_input, new_value_mode=new_value_mode, multiple=multiple, clearable=clearable)
        self.tailwind.width("full")
        if multiple is True:
            self.props("use-chips")


class FSelect(ui.select):
    def __init__(
        self,
        options: Union[List, Dict],
        *,
        label: Optional[str] = None,
        value: Any = None,
        on_change: Optional[Callable[..., Any]] = None,
        with_input: bool = False,
        new_value_mode: Optional[Literal["add", "add-unique", "toggle"]] = None,
        multiple: bool = False,
        clearable: bool = False,
    ) -> None:
        super().__init__(options, label=label, value=value, on_change=on_change, with_input=with_input, new_value_mode=new_value_mode, multiple=multiple, clearable=clearable)
        self.tailwind.width("64")


class DButton(ui.button):
    def __init__(
        self,
        text: str = "",
        *,
        on_click: Callable[..., Any] | None = None,
        color: Optional[str] = "primary",
        icon: str | None = None,
    ) -> None:
        super().__init__(text, on_click=on_click, color=color, icon=icon)
        self.props("size=md")
        self.tailwind.padding("px-2.5").padding("py-1")


class DCheckbox(ui.checkbox):
    def __init__(self, text: str = "", *, value: bool = False, on_change: Callable[..., Any] | None = None) -> None:
        super().__init__(text, value=value, on_change=on_change)
        self.tailwind.text_color("secondary")


class IButton(ui.button):
    def __init__(
        self,
        text: str = "",
        *,
        on_click: Callable[..., Any] | None = None,
        color: Optional[str] = "primary",
        icon: str | None = None,
    ) -> None:
        super().__init__(text, on_click=on_click, color=color, icon=icon)
        self.props("size=sm")


class SmButton(ui.button):
    def __init__(
        self,
        text: str = "",
        *,
        on_click: Callable[..., Any] | None = None,
        color: Optional[str] = "primary",
        icon: str | None = None,
    ) -> None:
        super().__init__(text, on_click=on_click, color=color, icon=icon)
        self.props("size=sm")
        self.tailwind.width("16")


class LgButton(ui.button):
    def __init__(
        self,
        text: str = "",
        *,
        on_click: Callable[..., Any] | None = None,
        color: Optional[str] = "primary",
        icon: str | None = None,
    ) -> None:
        super().__init__(text, on_click=on_click, color=color, icon=icon)
        self.props("size=md")


class Spinner(ui.spinner):
    def __init__(
        self,
        type: SpinnerTypes | None = "bars",
        *,
        size: str = "lg",
        color: str | None = "primary",
        thickness: float = 5,
        master: ui.spinner | None = None,
    ) -> None:
        super().__init__(type, size=size, color=color, thickness=thickness)
        self.visible = False
        if master is not None:
            self.bind_visibility_from(master, "visible")


def notify(
    message: Any,
    *,
    type: Optional[
        Literal[  # pylint: disable=redefined-builtin
            "positive",
            "negative",
            "warning",
            "info",
            "ongoing",
        ]
    ] = None,
    multi_line: bool = False,
) -> None:
    if multi_line:
        ui.notify(
            message=message,
            position="bottom-left",
            multi_line=True,
            close_button=True,
            classes="multi-line-notification",
            type=type,
            timeout=20000,
        )
    else:
        ui.notify(message=message, position="bottom-left", type=type)


class JsonEditor(ui.json_editor):
    def __init__(self, properties: Dict, *, on_select: Optional[Callable] = None, on_change: Optional[Callable] = None) -> None:
        super().__init__(properties, on_select=on_select, on_change=on_change)
        self.classes("jse-theme-dark")
        self.tailwind.height("[360px]").width("full")


class ContentTabPanel(ui.tab_panel):
    def __init__(self, name: Tab | str) -> None:
        super().__init__(name)
        self.style("height: calc(100vh - 131px)")
        self.tailwind.min_width("[920px]")
