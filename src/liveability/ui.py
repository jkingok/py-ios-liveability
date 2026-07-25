"""
Core Toga user interface controller and layout builder.

Constructs the primary application navigation layout using an `OptionContainer` with three tabs:
"List" (address overview, interactive map, amenity evaluation), "Setup" (services configuration),
and "Help" (rendered Markdown documentation webview).
"""

import asyncio
import ctypes
import datetime as dt
from markdown import markdown as md
from pathlib import Path
import requests
from rubicon.objc import ObjCClass, ObjCInstance, Block
from rubicon.objc.runtime import load_library, objc_id
from rubicon.objc.types import ctype_for_encoding
import threading
import toga
import urllib

from . import bridge as b
from . import data as d
from . import functions as f
from . import model as m
from . import settings as s
from . import widgets as ws


class Prototype:
    """
    Main user interface prototype controller for Liveability.

    Initializes application settings, database functions, models, and layout views.

    :param host_app: Parent Toga application instance.
    :type host_app: toga.App
    :param on_done: Callback function invoked upon exiting or completing root navigation.
    :type on_done: callable
    """
    def __init__(self, host_app, on_done):
        self.app = host_app
        self.on_done_callback = on_done  # This is your ticket back to safety
        self.title = "Liveability"  # host_app.formal_name
        self.app.settings = s.Settings(host_app.paths)
        self.app.functions = f.Functions(host_app.paths, self.app.settings)
        self.app.addresses = m.AddressModel(host_app.paths, self.app.functions)
        self.app.services = m.ServiceModel(host_app.paths, self.app.functions)
        self.app.comparisons = m.ComparisonModel(host_app.paths, self.app.functions)
        self.data_path = self.app.paths.data
        self.this_path = Path(__file__).resolve().parent
        self.icon_path = self.this_path / "resources" / "icons"
        self.template_path = self.this_path / "resources" / "templates"

    async def todo(self, name: str):
        """
        Displays a placeholder info dialog for pending features.

        :param name: Feature name string.
        :type name: str
        """
        await self.app.main_window.dialog(toga.InfoDialog("TODO", name))

    def add_address(self, text: str = None, url: str = None):
        """
        Geocodes a search string or resolves a Apple Maps URL to save a new target address.

        :param text: Address query text.
        :type text: str | None
        :param url: Apple Maps URL string.
        :type url: str | None
        """
        def record_item(mi):
            self.app.addresses.save(
                str(i.identifierString if (i := mi.identifier) else mi.name),
                {
                    "title": str(mi.name),
                    "subtitle": str(mi.addressRepresentations.fullAddressIncludingRegion(False, singleLine=True)),
                    "latitude": mi.location.coordinate.latitude,
                    "longitude": mi.location.coordinate.longitude
                }
            )

        def geocoded(r: objc_id, e: objc_id) -> None:
            if e:
                asyncio.create_task(self.app.main_window.dialog(toga.ErrorDialog("Search Failure", ObjCInstance(e).localizedDescription)))
            else:
                l = list(ObjCInstance(r))
                if len(l) == 1:
                    record_item(l[0])
                else:
                    asyncio.create_task(self.app.main_window.dialog(toga.ErrorDialog("Search Failure", "Could not determine address")))
                    record_item(b.MKMapItem.alloc().initWithLocation(loc))

        if url:
            pu = urllib.parse.urlparse(url)
            if pu.netloc in ['maps.apple', 'maps.app.goo.gl']:
                try:
                    response = requests.get(url, allow_redirects=True)
                    self.add_address(url=response.url)
                except Exception as e:
                    print(f"Error resolving short URL: {e}")
            elif pu.netloc == 'maps.apple.com':
                p = urllib.parse.parse_qs(pu.query)
                loc = b.CLLocation.alloc().initWithLatitude(float((ll := p['coordinate'][0].split(','))[0]), longitude=float(ll[1]))
                rgr = b.MKReverseGeocodingRequest.alloc().initWithLocation(loc)
                rgr.getMapItemsWithCompletionHandler(geocoded)
            else:
                asyncio.create_task(self.app.main_window.dialog(toga.ErrorDialog("Search Failure", "Cannot extract location from URL")))
        else:
            gr = b.MKGeocodingRequest.alloc().initWithAddressString(text)
            gr.getMapItemsWithCompletionHandler(geocoded)

    def add_by_name(self, title: str, name: str):
        """
        Callback handler for adding an address by natural language string name.

        :param title: Alert action title.
        :param name: Input address string.
        """
        self.add_address(text=name)

    def add_by_paste(self, title: str, name: str):
        """
        Callback handler for adding an address from system clipboard pasteboard contents.

        :param title: Alert action title.
        :param name: Clipboard text fallback.
        """
        if (pb := b.UIPasteboard.generalPasteboard).hasURLs and pb.URL and (u := pb.URL.absoluteString):
            self.add_address(url=str(u))
        elif pb.hasStrings and (s := pb.string):
            self.add_address(text=str(s))

    def ask_for_address(self):
        """
        Displays a native iOS input dialog prompting the user for an address or paste action.
        """
        ws.Utils.ask_for_input(self.app, "Add Address", "Enter an address, search term or tap to Paste", [("Add", self.add_by_name), ("Paste", self.add_by_paste), ("Cancel",)], 1)

    def add_service(self, title: str, name: str, emoji: str):
        """
        Callback handler for adding a new service amenity category.

        :param title: Action title string.
        :param name: Service name string (e.g. 'Supermarket').
        :param emoji: Emoji symbol string (e.g. '🛒').
        """
        self.app.services.save(
            name,
            {
                "name": name,
                "emoji": emoji
            }
        )

    def ask_for_service(self):
        """
        Displays a native iOS input dialog prompting the user for service name and emoji symbol.
        """
        ws.Utils.ask_for_input(self.app, "Service", "Enter an address, search term, and a symbol to use for it", [("Add", self.add_service), ("Cancel",)], 2)

    def get_content(self) -> toga.OptionContainer:
        """
        Constructs and returns the main Toga OptionContainer view layout with tabs ('List', 'Setup', 'Help').

        :returns: Constructed OptionContainer containing all application tabs and sub-views.
        :rtype: toga.OptionContainer
        """
        class ViewAddressBox(toga.Box):
            """
            Sub-view box for inspecting a specific address, its MapView, and calculated proximity amenities matrix.
            """
            def __init__(self, stack=None, key=None, values=None, details=None):
                self.key = key or dt.datetime.now().isoformat()
                self.values = values or d.Address()
                super().__init__(
                    direction="column",
                    children=[
                        ws.LabelledText(
                            "Key",
                            value_text=self.key,
                            readonly=True
                        ),
                        toga.Divider(),
                        ws.LabelledText(
                            "Title",
                            value_text=self.values.title,
                            callback=lambda w: {
                                self.set_value("title", w.value)
                            }
                        ),
                        ws.LabelledText(
                            "Subtitle",
                            value_text=self.values.subtitle,
                            callback=lambda w: {
                                self.set_value("subtitle", w.value)
                            }
                        ),
                        toga.MapView(
                            flex=1,
                            location=(ll := (self.values.latitude, self.values.longitude)),
                            zoom=15,
                            pins=[toga.MapPin(ll, title="🏠"), *[toga.MapPin((v.latitude, v.longitude), title=v.title) for v in details if v.latitude and v.longitude]]
                        ),
                        toga.DetailedList(
                            flex=1,
                            primary_action="View",
                            on_primary_action=lambda w, row: asyncio.create_task(self.todo("View")),
                            data=details
                        ),
                        toga.Row(
                            children=[
                                toga.Button(
                                    "Back",
                                    flex=1,
                                    on_press=lambda w: self.app.widgets[self.stack].pop()
                                ),
                            ]
                        )
                    ],
                    flex=1
                )
                self.stack = stack

            def set_value(self, k: str, v):
                """Sets an attribute value on the address object."""
                setattr(self.values, k, v)

        class EditServiceBox(toga.Box):
            """
            Sub-view box for editing a service category name and emoji icon.
            """
            def __init__(self, stack=None, key=None, values=None):
                self.key = key or dt.datetime.now().isoformat()
                self.values = values or d.Service()
                super().__init__(
                    direction="column",
                    children=[
                        ws.LabelledText(
                            "Key",
                            value_text=self.key,
                            readonly=True
                        ),
                        toga.Divider(),
                        ws.LabelledText(
                            "Name",
                            value_text=self.values.name,
                            callback=lambda w: {
                                self.set_value("name", w.value)
                            }
                        ),
                        ws.LabelledText(
                            "Symbol",
                            value_text=self.values.emoji,
                            callback=lambda w: {
                                self.set_value("emoji", w.value)
                            }
                        ),
                        toga.Box(
                            flex=1
                        ),
                        toga.Row(
                            children=[
                                toga.Button(
                                    "Back",
                                    flex=1,
                                    on_press=lambda w: {
                                        self.app.widgets[self.stack].pop()
                                    }
                                ),
                                toga.Button(
                                    "Save",
                                    flex=1,
                                    on_press=lambda w: (
                                        self.app.services.save(self.key, self.values),
                                        self.app.widgets[self.stack].pop()
                                    )
                                )
                            ]
                        )
                    ],
                    flex=1
                )
                self.stack = stack

            def set_value(self, k: str, v):
                """Sets an attribute value on the service object."""
                setattr(self.values, k, v)

        return toga.OptionContainer(
            content=[
                ("List", ws.StackContainer(
                    id="stack_list",
                    direction="column",
                    children=[
                        toga.Row(
                            children=[
                                self.app.addresses.set_list_count_label(toga.Label("", flex=1)),
                                toga.Button(
                                    "Add",
                                    on_press=lambda _: self.ask_for_address()
                                )
                            ]
                        ),
                        toga.DetailedList(
                            flex=1,
                            on_refresh=lambda w: {
                                self.app.addresses.reload_items()
                            },
                            primary_action="View",
                            on_primary_action=lambda w, row: asyncio.create_task(self.todo("View")),
                            secondary_action="Delete",
                            on_secondary_action=lambda w, row: self.app.addresses.delete(row.index),
                            on_select=lambda w: self.app.widgets["stack_list"].push(ViewAddressBox("stack_list", i := w.selection.index, v := self.app.addresses.get(i), self.app.comparisons.get(v.title))),
                            data=self.app.addresses.items_list_source
                        ),
                        self.app.addresses.set_map(toga.MapView(
                            location=self.app.addresses.find_centre(),
                            zoom=7,
                            pins=[toga.MapPin(location=e, title=str(i + 1)) for i, e in enumerate(self.app.addresses.get_pins())],
                            on_select=lambda w, pin: self.app.widgets["stack_list"].push(ViewAddressBox("stack_list", i := self.app.addresses.items_list_source[int(pin.title) - 1].index, v := self.app.addresses.get(i), self.app.comparisons.get(v.title))),
                            flex=1
                        )),
                        toga.Row(
                            align_items="center",
                            children=[
                                self.app.comparisons.set_activity(ws.LabelledActivity(id="app_activity")),
                                self.app.comparisons.set_progress(ws.LabelledProgress(id="app_progress", flex=1))
                            ]
                        )
                    ]), self.icon_path / "list.png"),
                ("Setup", ws.StackContainer(
                    id="stack_setup",
                    direction="column",
                    children=[
                        toga.Row(
                            children=[
                                self.app.services.set_list_count_label(toga.Label("", flex=1)),
                                toga.Button(
                                    "Add",
                                    on_press=lambda _: self.ask_for_service()
                                )
                            ]
                        ),
                        toga.DetailedList(
                            flex=1,
                            on_refresh=lambda w: {
                                self.app.services.reload_items()
                            },
                            primary_action="View",
                            on_primary_action=lambda w, row: asyncio.create_task(self.todo("View")),
                            secondary_action="Delete",
                            on_secondary_action=lambda w, row: self.app.services.delete(row.index),
                            on_select=lambda w: {
                                self.app.widgets["stack_setup"].push(EditServiceBox("stack_setup", i := w.selection.index, self.app.services.get(i)))
                            },
                            data=self.app.services.items_list_source
                        ),
                        toga.Button(
                            "Exit",
                            visibility="visible" if hasattr(self.app.main_window, "content_stack") and len(self.app.main_window.content_stack) > 0 else "hidden",
                            on_press=self.on_done_callback
                        )
                    ]), self.icon_path / "settings-sliders.png"),
                ("Help", toga.Row(
                    children=[
                        toga.WebView(
                            content=f"""
        <html>
        <head>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; line-height: 1.6; padding: 20px; color: #333; }}
                code {{ background-color: #f6f8fa; padding: 2px 4px; border-radius: 3px; font-family: monospace; }}
                pre {{ background-color: #f6f8fa; padding: 16px; overflow: auto; border-radius: 6px; }}
                img {{ max-width: 100%; height: auto; }}
            </style>
        </head>
        <body>
                     {md(f.read_text() if (f := (self.template_path / "help.md")).exists() else "")}
        </body>
        </html>
""",
                            flex=1)]), self.icon_path / "interrogation.png")
            ],
        )
