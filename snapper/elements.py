from typing import Any, Callable, Dict, List, Literal, Optional, Union
from nicegui import ui, app, Tailwind
from nicegui.elements.spinner import SpinnerTypes
from nicegui.tailwind_types.height import Height
from nicegui.tailwind_types.width import Width
from nicegui.elements.mixins.validation_element import ValidationElement
from nicegui.events import GenericEventArguments, handle_event
from snapper.interfaces import cli
import logging

logger = logging.getLogger(__name__)

orange = "#f59e0b"
dark = "#171717"
ui.card.default_style("max-width: none")
ui.card.default_props("flat bordered")
ui.input.default_props("outlined dense hide-bottom-space")
ui.button.default_props("outline dense")
ui.select.default_props("outlined dense dense-options")
ui.checkbox.default_props("dense")


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
        validators = all(validation(element.value) for element in self.elements for validation in element.validation.values())
        return self.enable and validators


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
        options: List | Dict,
        *,
        label: str | None = None,
        value: Any = None,
        on_change: Callable[..., Any] | None = None,
        with_input: bool = False,
        multiple: bool = False,
        clearable: bool = False,
    ) -> None:
        super().__init__(
            options, label=label, value=value, on_change=on_change, with_input=with_input, multiple=multiple, clearable=clearable
        )
        self.tailwind.width("full").max_height("[40px]")


class FSelect(ui.select):
    def __init__(
        self,
        options: List | Dict,
        *,
        label: str | None = None,
        value: Any = None,
        on_change: Callable[..., Any] | None = None,
        with_input: bool = False,
        multiple: bool = False,
        clearable: bool = False,
    ) -> None:
        super().__init__(
            options, label=label, value=value, on_change=on_change, with_input=with_input, multiple=multiple, clearable=clearable
        )
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
        self.tailwind.width("full").text_color("secondary")


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
