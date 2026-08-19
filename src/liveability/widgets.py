"""
Custom Toga UI widgets and native platform utility integration.

Provides compound labelled input widgets (`LabelledDate`, `LabelledNumber`, `LabelledSelection`,
`LabelledText`, `LabelledProgress`, `LabelledActivity`), navigation `StackContainer`, and native iOS
dialogs (`UIAlertController`, `UIActivityViewController`, keyboard dismissal via `IOSUtils`).
"""

import asyncio
import math
import sys
from pathlib import Path
from typing import Any

import toga
from toga.sources import ListSource, Row


class DynamicLabel(toga.Label):
    def __init__(self, source, formatter=None, **kwargs):
        self.source = source
        self.source.on_count_change = self.update
        self.formatter = formatter if formatter else str
        super().__init__("", **kwargs)
        self.update(self.source.get_count())

    def update(self, value):
        self.text = self.formatter(value)


class DynamicMapView(toga.MapView):
    """A Toga MapView that dynamically renders pins and centers on their centroid."""

    def __init__(
        self,
        data: ListSource | None = None,
        auto_center: bool = True,
        fixed_pins: list[toga.MapPin] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)

        self.auto_center = auto_center

        self.fixed_pins = fixed_pins if fixed_pins else []

        self._pin_map: dict[int, toga.MapPin] = {}
        self._pin_src = {}
        self._data: ListSource | None = data

        if data is not None:
            # self.source_change(data)
            for p in self.fixed_pins:
                self.pins.add(p)
            for idx, row in enumerate(data): # pyright: ignore [reportArgumentType]
                self.source_insert(idx, row)
            data.add_listener(self)

    # --- Centroid Calculation ---

    def _recalculate_centre(self) -> None:
        """Calculates the geographic centroid of all active pins and updates map center."""
        if not self.auto_center or not self._pin_map:
            return

        pins = list(self._pin_map.values())

        lats = [pin.location[0] for pin in pins]
        lons = [pin.location[1] for pin in pins]

        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)

        # Calculate center point
        mid_lat = (min_lat + max_lat) / 2.0
        mid_lon = (min_lon + max_lon) / 2.0

        # Estimate map zoom level based on max coordinate span
        max_span = max(max_lat - min_lat, max_lon - min_lon)
        if max_span > 0:
            # Toga zoom scale formula roughly maps longitude span to 0-20 scale
            calculated_zoom = int(max(0, min(20, math.log2(360 / max_span) - 1)))
        else:
            calculated_zoom = 15  # Fallback for single pin

        # Updating Toga properties triggers both Python state and MKMapView simultaneously
        self.location = (mid_lat, mid_lon)
        self.zoom = calculated_zoom

        # Or, zoom to fit all pins
        # if sys.platform == "ios":
        #    (mkmap := self._impl.native).showAnnotations(mkmap.annotations, animated=True)

    # --- Helper for Row -> Pin Conversion ---

    def _create_pin_from_row(self, row: Row) -> toga.MapPin | None:
        if row._instance.latitude and row._instance.longitude: # pyright: ignore [reportAttributeAccessIssue]
            lat = row._instance.latitude # pyright: ignore [reportAttributeAccessIssue]
            lon = row._instance.longitude # pyright: ignore [reportAttributeAccessIssue]

            return toga.MapPin(
                location=(lat, lon), title=row.title, subtitle=row.subtitle # pyright: ignore [reportAttributeAccessIssue]
            )
        else:
            return None

    def row_of_pin(self, pin):
        return self._pin_src[i] if (i := id(pin)) in self._pin_src else None

    # --- Toga Source Listener Hooks ---

    def source_clear(self) -> None:
        """Reset of source data."""
        self.pins.clear()
        self._pin_map.clear()
        for p in self.fixed_pins:
            self.pins.add(p)

    def source_insert(self, index: int, item) -> None:
        """Single item added."""
        pin = self._create_pin_from_row(item)
        if pin:
            self._pin_map[id(item)] = pin
            self._pin_src[id(pin)] = item
            self.pins.add(pin)

            self._recalculate_centre()

    def source_remove(self, index: int, item) -> None:
        """Single item removed."""
        row_key = id(item)
        if row_key in self._pin_map:
            pin = self._pin_map.pop(row_key)
            self._pin_set.pop(id(item))
            self.pins.remove(pin)

        self._recalculate_centre()

    def source_change(self, item) -> None:
        """Item updated in place (e.g. coordinates shifted)."""
        row_key = id(item)
        if row_key in self._pin_map:
            # Remove old pin representation
            old_pin = self._pin_map.pop(row_key)
            self._pin_set.pop(id(item))
            self.pins.remove(old_pin)

        # Insert updated pin representation
        new_pin = self._create_pin_from_row(item)
        if new_pin:
            self._pin_map[row_key] = new_pin
            self._pin_src[id(new_pin)] = item
            self.pins.add(new_pin)

            self._recalculate_centre()


class LabelledDate(toga.Box):
    """
    Toga Box combining a text Label and DateInput widget.

    :param label_text: Text displayed on the label prefix.
    :type label_text: str
    :param value_text: Initial date value.
    :param callback: Event handler callback for date change.
    :type callback: callable
    :param id: Widget identifier.
    :type id: str
    """

    def __init__(self, label_text: str, value_text=None, callback=None, id=None):
        super().__init__(
            direction="row",
            align_items="center",
            children=[
                toga.Label(label_text + ": "),
                toga.DateInput(id=id, value=value_text, flex=1, on_change=callback),
            ],
        )


class LabelledNumber(toga.Box):
    """
    Toga Box combining a text Label and NumberInput widget.

    :param label_text: Label text prefix.
    :type label_text: str
    :param value_num: Initial numeric value.
    :type value_num: int | float
    :param callback: Event handler callback for change.
    :type callback: callable
    :param readonly: True to set input field read-only.
    :type readonly: bool
    :param id: Widget identifier.
    :type id: str
    """

    def __init__(
        self,
        label_text: str,
        value_num=0,
        callback=None,
        readonly: bool = False,
        id=None,
    ):
        super().__init__(
            direction="row",
            align_items="center",
            children=[
                toga.Label(label_text + ": "),
                toga.NumberInput(
                    id=id,
                    value=value_num,
                    flex=1,
                    on_change=callback,
                    readonly=readonly,
                ),
            ],
        )


class LabelledSelection(toga.Box):
    """
    Toga Box combining a text Label and Selection dropdown widget.

    :param label_text: Label text prefix.
    :type label_text: str
    :param value_text: Initially selected item value.
    :type value_text: str
    :param value_list: List of available selection items.
    :type value_list: list
    :param callback: Change event callback handler.
    :type callback: callable
    :param id: Widget identifier.
    :type id: str
    """

    def __init__(
        self, label_text: str, value_text="", value_list=None, callback=None, id=None
    ):
        if value_list is None:
            value_list = []
        super().__init__(
            direction="row",
            align_items="center",
            children=[
                toga.Label(label_text + ": "),
                toga.Selection(
                    id=id,
                    items=value_list,
                    value=value_text,
                    flex=1,
                    on_change=callback,
                ),
            ],
        )


class LabelledText(toga.Box):
    """
    Toga Box combining a text Label and TextInput (or MultilineTextInput) widget.

    :param label_text: Label text prefix.
    :type label_text: str
    :param value_text: Initial text string value.
    :type value_text: str
    :param callback: Text change event callback handler.
    :type callback: callable
    :param confirm: Enter key confirm event callback handler.
    :type confirm: callable
    :param readonly: True to set text input read-only.
    :type readonly: bool
    :param multiline: True to render a multiline text input.
    :type multiline: bool
    :param id: Widget identifier.
    :type id: str
    """

    def __init__(
        self,
        label_text: str,
        value_text="",
        callback=None,
        confirm=None,
        readonly: bool = False,
        multiline: bool = False,
        id=None,
        **kwargs,
    ):
        super().__init__(
            direction="column" if multiline else "row",
            align_items="start" if multiline else "center",
            children=[
                toga.Label(label_text + ": "),
                (
                    toga.MultilineTextInput(
                        id=id,
                        value=value_text,
                        flex=1,
                        on_change=callback,
                        readonly=readonly,
                    )
                    if multiline
                    else toga.TextInput(
                        id=id,
                        value=value_text,
                        flex=1,
                        on_change=callback,
                        on_confirm=confirm,
                        readonly=readonly,
                    )
                ),
            ],
            **kwargs,
        )


class LabelledProgress(toga.Box):
    """
    Toga Box combining a ProgressBar and progress text status Label.
    """

    def __init__(self, **kwargs):
        self.bar = toga.ProgressBar(flex=1)
        self.text = toga.Label("")
        super().__init__(
            direction="row",
            align_items="center",
            children=[self.bar, self.text],
            **kwargs,
        )

    def start(self, limit: int = 0):
        """
        Starts the progress bar with a specified upper limit.

        :param limit: Maximum progress target value.
        :type limit: int
        """
        self.bar.max = limit if limit > 0 else None
        self.bar.start()
        self.update(0)

    def update(self, value: int | float):
        """
        Updates current progress value and updates status text label.

        :param value: Current progress value.
        :type value: int
        """
        if self.bar.max:
            if self.bar.max == 100:
                self.text.text = f"{int(value)}%"
            else:
                self.text.text = f"{int(value)}/{int(self.bar.max)}"
        else:
            self.text.text = ""
        self.bar.value = value

    def increment(self, step: int = 1):
        """
        Increments progress by a step amount.

        :param step: Step value to increment.
        :type step: int
        """
        self.update(self.bar.value + step)

    def stop(self):
        """
        Stops progress animation and sets progress bar to maximum value.
        """
        if self.bar.max:
            self.update(self.bar.max)
        self.bar.stop()

    def is_done(self) -> bool:
        """
        Checks whether the progress bar has reached maximum limit.

        :returns: True if progress is complete.
        :rtype: bool
        """
        return self.bar.value >= self.bar.max if self.bar.max else False


class LabelledActivity(toga.Box):
    """
    Toga Box combining an ActivityIndicator spinner and status text Label.
    """

    def __init__(self, **kwargs):
        self.activity = toga.ActivityIndicator()
        self.text = toga.Label("", flex=1)
        super().__init__(direction="row", children=[self.activity, self.text], **kwargs)

    def update(self, value: str = "", on: bool = True):
        """
        Updates text label and starts or stops activity animation.

        :param value: Status message text.
        :type value: str
        :param on: True to start activity spinner, False to stop.
        :type on: bool
        """
        self.activity.start() if on else self.activity.stop()
        self.text.text = value


class StackContainer(toga.Box):
    """
    Toga Box container supporting push/pop view navigation stack mechanics.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.stack = []

    def push(self, new_children):
        """
        Pushes current children onto stack and displays new child views.

        :param new_children: Widget or list of widgets to display.
        """
        self.stack.append(list(self.children))
        self.clear()
        self.add(new_children)

    def pop(self):
        """
        Pops and restores previous widget view hierarchy from stack.
        """
        if self.stack:
            new_children = self.stack.pop()
            self.clear()
            self.add(*new_children)


class GenericUtils:
    """
    Generic cross-platform utilities.
    """

    @staticmethod
    def info_task(w: toga.Widget, title: str, text: str):
        """
        Displays an InfoDialog asynchronously.

        :param w: Toga app host context.
        :param title: Dialog title string.
        :type title: str
        :param text: Dialog message content.
        :type text: str
        """
        if w.app and isinstance(w.app.main_window, toga.Window):
            asyncio.create_task(w.app.main_window.dialog(toga.InfoDialog(title, text)))


class PlatformUtils(GenericUtils):
    """
    Fallback implementation of platform-specific utilities for non-iOS platforms.
    """
    @staticmethod
    def close_keyboard(widget):
        pass

    @staticmethod
    def ask_for_input(widget, title: str, message: str, actions=None, texts: int = 0):
        pass

    @staticmethod
    def open_share_sheet(widget, html_file_path: str):
        pass


if sys.platform == "ios":
    from rubicon.objc import ObjCClass, ObjCInstance

    # Load the required Objective-C classes
    NSURL = ObjCClass("NSURL")
    NSMutableArray = ObjCClass("NSMutableArray")
    UIActivityViewController = ObjCClass("UIActivityViewController")
    UIAlertController = ObjCClass("UIAlertController")
    UIAlertAction = ObjCClass("UIAlertAction")

    class IOSUtils(PlatformUtils):
        """
        Native iOS implementation of platform utilities using Objective-C UIKit calls via Rubicon-ObjC.
        """

        def close_keyboard(widget):
            """
            Dismisses the soft keyboard by resigning first responder status on UIKit textfield.

            :param widget: Native Toga text field widget.
            """
            if sys.platform == "ios":
                if hasattr(widget, "_impl") and hasattr(widget._impl, "native"):
                    native_textfield = widget._impl.native
                    native_textfield.resignFirstResponder()
                    print("[UIKit] Keyboard dismissed via resignFirstResponder.")

        def ask_for_input(w, title: str, message: str, actions=None, texts: int = 0):
            """
            Presents a native iOS UIAlertController modal with action buttons and text input fields.

            :param w: Toga host widget or app context.
            :param title: Alert title string.
            :type title: str
            :param message: Alert description text.
            :type message: str
            :param actions: List of tuples `(button_title, callback_function)`.
            :type actions: list
            :param texts: Number of text input fields to attach.
            :type texts: int
            """
            if actions is None:
                actions = []
            alert = UIAlertController.alertControllerWithTitle(
                title, message=message, preferredStyle=1
            )

            for i in range(texts):
                alert.addTextFieldWithConfigurationHandler_(None)

            handlers = {
                action[0]: action[1]
                for action in actions
                if len(action) > 1 and action[1]
            }

            def on_done(action_ptr: ObjCInstance) -> None:
                if (title := str(ObjCInstance(action_ptr).title)) in handlers:
                    outputs = [str(tf.text) for tf in alert.textFields]
                    handlers[title](title, *outputs)

            for action in actions:
                alert.addAction(
                    UIAlertAction.actionWithTitle(action[0], style=0, handler=on_done)
                )

            w.main_window._impl.native.rootViewController.presentViewController(
                alert, animated=True, completion=None
            )

        def open_share_sheet(w, html_file_path: str):
            """
            Opens the iOS native UIActivityViewController share sheet for a target file.

            :param w: Active Toga widget initiating the share operation.
            :param html_file_path: File system path to the target file.
            :type html_file_path: str
            """
            absolute_path = str(Path(html_file_path).resolve())
            file_url = NSURL.fileURLWithPath_(absolute_path)

            share_items = NSMutableArray.alloc().init()
            share_items.addObject_(file_url)

            activity_vc = UIActivityViewController.alloc().initWithActivityItems(
                share_items, applicationActivities=None
            )

            presenting_vc = w.app.main_window._impl.native.rootViewController

            if activity_vc.popoverPresentationController:
                activity_vc.popoverPresentationController.sourceView = (
                    presenting_vc.view
                )
                activity_vc.popoverPresentationController.sourceRect = (
                    presenting_vc.view.bounds
                )

            presenting_vc.presentViewController(
                activity_vc, animated=True, completion=None
            )

    Utils = IOSUtils

else:
    Utils = PlatformUtils
