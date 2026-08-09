"""
Core Toga user interface controller and layout builder.

Constructs the primary application navigation layout using an `OptionContainer` with three tabs:
"List" (address overview, interactive map, amenity evaluation), "Setup" (services configuration),
and "Help" (rendered Markdown documentation webview).
"""

import asyncio
import httpx
from markdown import markdown as md
from pathlib import Path
from rubicon.objc import ObjCInstance
from rubicon.objc.runtime import objc_id
import toga
import traceback
import urllib

from . import bridge as b

from . import db as d

from . import geography as g
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
        # self.app.functions = f.Functions(host_app.paths, self.app.settings)
        # self.app.addresses = m.AddressModel(host_app.paths, self.app.functions)
        # self.app.services = m.ServiceModel(host_app.paths, self.app.functions)
        # self.app.comparisons = m.ComparisonModel(host_app.paths, self.app.functions)
        self.data_path = self.app.paths.data
        self.this_path = Path(__file__).resolve().parent
        self.icon_path = self.this_path / "resources" / "icons"
        self.template_path = self.this_path / "resources" / "templates"
        d.init(self.data_path / f"{self.title}.db")  # set up DB
        self.app.routes = m.RouteGenerator()
        self.app.routes.on_progress_update = self.progress_update
        self.app.loop.call_soon(self.app.routes.trigger_full_recalculate)

    def _error(self, title, text):
        print(f"⚠ {title}: {text}")
        asyncio.create_task(
            self.app.main_window.dialog(toga.ErrorDialog(str(title), str(text)))
        )

    def _info(self, title, text):
        print(f"ℹ {title}: {text}")
        asyncio.create_task(
            self.app.main_window.dialog(toga.InfoDialog(str(title), str(text)))
        )

    def open_address_in_maps(self, row):
        """
        Opens the selected Address item from the List in Apple Maps.

        :param row: DetailedList row item object containing `.index` or address properties.
        """
        g.open_in_maps([(row._instance.latitude, row._instance.longitude, row.title)])

    async def add_address(self, text: str = None, url: str = None):
        """
        Geocodes a search string or resolves a Apple Maps URL to save a new target address.

        :param text: Address query text.
        :type text: str | None
        :param url: Apple Maps URL string.
        :type url: str | None
        """

        def record_item(mi):
            d.Address.create(
                title=str(mi.name),
                subtitle=str(
                    mi.addressRepresentations.fullAddressIncludingRegion(
                        False, singleLine=True
                    )
                ),
                latitude=mi.location.coordinate.latitude,
                longitude=mi.location.coordinate.longitude,
            )
            self._info("Address Added", str(mi.name))

        def geocoded(r: objc_id, e: objc_id) -> None:
            if e:
                self._error("Search Failure", ObjCInstance(e).localizedDescription)
            else:
                l = list(ObjCInstance(r))
                if len(l) == 1:
                    record_item(l[0])
                else:
                    self._error("Search Failure", "Could not determine address")
                    record_item(b.MKMapItem.alloc().initWithLocation(loc))

        if url:
            pu = urllib.parse.urlparse(url)
            if pu.netloc in ["maps.apple", "maps.app.goo.gl"]:
                try:
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        response = await client.get(url, allow_redirects=True)
                        response.raise_for_status()
                        await self.add_address(url=response.url)
                except Exception as e:
                    self._error("URL Error", f"Could not get short URL: {e}")
            elif pu.netloc == "maps.apple.com":
                p = urllib.parse.parse_qs(pu.query)
                loc = b.CLLocation.alloc().initWithLatitude(
                    float((ll := p["coordinate"][0].split(","))[0]),
                    longitude=float(ll[1]),
                )
                rgr = b.MKReverseGeocodingRequest.alloc().initWithLocation(loc)
                rgr.getMapItemsWithCompletionHandler(geocoded)
            else:
                self._error("Search Failure", "Cannot extract location from URL")
        else:
            gr = b.MKGeocodingRequest.alloc().initWithAddressString(text)
            gr.getMapItemsWithCompletionHandler(geocoded)

    async def add_by_name(self, title: str, name: str):
        """
        Callback handler for adding an address by natural language string name.

        :param title: Alert action title.
        :param name: Input address string.
        """
        await self.add_address(text=name)

    async def add_by_paste(self, title: str, name: str):
        """
        Callback handler for adding an address from system clipboard pasteboard contents.

        :param title: Alert action title.
        :param name: Clipboard text fallback.
        """
        if (
            (pb := b.UIPasteboard.generalPasteboard).hasURLs
            and pb.URL
            and (u := pb.URL.absoluteString)
        ):
            await self.add_address(url=str(u))
        elif pb.hasStrings and (s := pb.string):
            await self.add_address(text=str(s))

    def ask_for_address(self):
        """
        Displays a native iOS input dialog prompting the user for an address or paste action.
        """
        ws.Utils.ask_for_input(
            self.app,
            "Add Address",
            "Enter an address, search term or tap to Paste",
            [
                ("Add", lambda t, n: asyncio.create_task(self.add_by_name(t, n))),
                ("Paste", lambda t, n: asyncio.create_task(self.add_by_paste(t, n))),
                ("Cancel",),
            ],
            1,
        )

    def add_service(self, title: str, name: str, emoji: str):
        """
        Callback handler for adding a new service amenity category.

        :param title: Action title string.
        :param name: Service name string (e.g. 'Supermarket').
        :param emoji: Emoji symbol string (e.g. '🛒').
        """
        d.Service.create(name=name, emoji=emoji)

    def ask_for_service(self):
        """
        Displays a native iOS input dialog prompting the user for service name and emoji symbol.
        """
        ws.Utils.ask_for_input(
            self.app,
            "Service",
            "Enter an address, search term, and a symbol to use for it",
            [("Add", self.add_service), ("Cancel",)],
            2,
        )

    def get_content(self) -> toga.OptionContainer:
        try:
            """
            Constructs and returns the main Toga OptionContainer view layout with tabs ('List', 'Setup', 'Help').

            :returns: Constructed OptionContainer containing all application tabs and sub-views.
            :rtype: toga.OptionContainer
            """

            class ViewAddressBox(toga.Box):
                """
                Sub-view box for inspecting a specific address, its MapView, and calculated proximity amenities matrix.
                """

                def __init__(self, row, stack):
                    self.row = row
                    self.stack = stack
                    super().__init__(
                        direction="column",
                        children=[
                            ws.LabelledText(
                                "Title", value_text=row.title, readonly=True
                            ),
                            ws.LabelledText(
                                "Subtitle", value_text=row.subtitle, readonly=True
                            ),
                            ws.DynamicMapView(
                                d.DBListSource(
                                    d.Route.select().where(
                                        (d.Route.address == row._instance)
                                        & (d.Route.latitude != None)
                                        & (d.Route.longitude != None)
                                    )
                                ),
                                False,
                                [
                                    toga.MapPin(
                                        (
                                            row._instance.latitude,
                                            row._instance.longitude,
                                        ),
                                        title="🏠",
                                    )
                                ],
                                id="view_address_box_map",
                                flex=1,
                                location=(
                                    (
                                        row._instance.latitude,
                                        row._instance.longitude,
                                    )
                                ),
                                zoom=15,
                            ),
                            toga.DetailedList(
                                flex=1,
                                primary_action="View",
                                on_primary_action=lambda w, row: self.open_directions_in_maps(
                                    row
                                ),
                                on_refresh=lambda w: (
                                    d.Route.delete()
                                    .where(d.Route.address == row._instance)
                                    .execute(),
                                    self.app.loop.call_soon(
                                        self.app.routes.trigger_full_recalculate
                                    ),
                                ),
                                on_select=lambda w: setattr(
                                    self.app.widgets["view_address_box_map"],
                                    "location",
                                    (
                                        w.selection._instance.latitude,
                                        w.selection._instance.longitude,
                                    ),
                                ),
                                data=d.DBListSource(
                                    model_or_query=row._instance.routes
                                ),
                            ),
                            toga.Row(
                                children=[
                                    toga.Button(
                                        "Back",
                                        flex=1,
                                        on_press=lambda w: self.app.widgets[
                                            self.stack
                                        ].pop(),
                                    ),
                                ]
                            ),
                        ],
                        flex=1,
                    )

                def open_directions_in_maps(self, row):
                    """
                    Opens the selected matching Service item from the List's directions from the Address in Apple Maps.

                    :param fro: DetailedList row item object of the Address
                    :param to: DetailedList row item object of the matching Service
                    """
                    fro = row._instance.address
                    to = row._instance
                    ws.Utils.ask_for_input(
                        self.app,
                        "View Directions",
                        "Select direction of travel",
                        [
                            (
                                "Outbound",
                                lambda t: g.open_in_maps(
                                    [
                                        (fro.latitude, fro.longitude, fro.title),
                                        (to.latitude, to.longitude, to.title),
                                    ],
                                    str(to.mode),
                                ),
                            ),
                            (
                                "Inbound",
                                lambda t: g.open_in_maps(
                                    [
                                        (to.latitude, to.longitude, to.title),
                                        (fro.latitude, fro.longitude, fro.title),
                                    ],
                                    str(to.mode),
                                ),
                            ),
                            ("Cancel",),
                        ],
                    )

            class EditServiceBox(toga.Box):
                """
                Sub-view box for editing a service category name and emoji icon.
                """

                def __init__(self, row, stack):
                    self.row = row
                    self.stack = stack
                    super().__init__(
                        direction="column",
                        children=[
                            ws.LabelledText(
                                "Name",
                                id="edit_service_name",
                                value_text=row._instance.name,
                            ),
                            ws.LabelledText(
                                "Symbol",
                                id="edit_service_emoji",
                                value_text=row._instance.emoji,
                            ),
                            toga.Box(flex=1),
                            toga.Row(
                                children=[
                                    toga.Button(
                                        "Back",
                                        flex=1,
                                        on_press=lambda w: self.app.widgets[
                                            self.stack
                                        ].pop(),
                                    ),
                                    toga.Button(
                                        "Save",
                                        flex=1,
                                        on_press=lambda w: (
                                            setattr(
                                                self.row._instance,
                                                "name",
                                                self.app.widgets[
                                                    "edit_service_name"
                                                ].value,
                                            ),
                                            setattr(
                                                self.row._instance,
                                                "emoji",
                                                self.app.widgets[
                                                    "edit_service_emoji"
                                                ].value,
                                            ),
                                            self.row._instance.save(),
                                            self.app.widgets[self.stack].pop(),
                                        ),
                                    ),
                                ]
                            ),
                        ],
                        flex=1,
                    )

            return toga.OptionContainer(
                content=[
                    (
                        "List",
                        ws.StackContainer(
                            id="stack_list",
                            direction="column",
                            children=[
                                toga.Row(
                                    children=[
                                        ws.DynamicLabel(
                                            d.DBListSource(d.Address),
                                            lambda v: f"{v} address(es)",
                                            flex=1,
                                        ),
                                        toga.Button(
                                            "Add",
                                            on_press=lambda _: self.ask_for_address(),
                                        ),
                                    ]
                                ),
                                toga.DetailedList(
                                    flex=1,
                                    primary_action="View",
                                    on_primary_action=lambda w, row: self.open_address_in_maps(
                                        row
                                    ),
                                    secondary_action="Delete",
                                    on_secondary_action=lambda w, row: row._instance.delete_instance(),
                                    on_select=lambda w: self.app.widgets[
                                        "stack_list"
                                    ].push(ViewAddressBox(w.selection, "stack_list")),
                                    accessors=("title", "summary", "icon"),
                                    data=d.DBListSource.create_address_summary(),  # d.DBListSource(d.Address.get_summary_list(), ['title', 'subtitle', 'summary', 'icon'], related_models=[d.Route])
                                ),
                                ws.DynamicMapView(
                                    d.DBListSource(d.Address.select()),
                                    zoom=7,
                                    on_select=lambda w, pin: (
                                        self.app.widgets["stack_list"].push(
                                            ViewAddressBox(row, "stack_list")
                                        )
                                        if (row := w.row_of_pin(pin))
                                        else None
                                    ),
                                    flex=1,
                                ),
                                toga.Row(
                                    align_items="center",
                                    children=[
                                        ws.LabelledActivity(id="app_activity"),
                                        ws.LabelledProgress(id="app_progress", flex=1),
                                    ],
                                ),
                            ],
                        ),
                        self.icon_path / "list.png",
                    ),
                    (
                        "Setup",
                        ws.StackContainer(
                            id="stack_setup",
                            direction="column",
                            children=[
                                toga.Row(
                                    children=[
                                        ws.DynamicLabel(
                                            d.DBListSource(d.Service),
                                            lambda v: f"{v} service(s)",
                                            flex=1,
                                        ),
                                        toga.Button(
                                            "Add",
                                            on_press=lambda _: self.ask_for_service(),
                                        ),
                                    ]
                                ),
                                toga.DetailedList(
                                    flex=1,
                                    primary_action="View",
                                    on_primary_action=lambda w, row: asyncio.create_task(
                                        self.todo("View")
                                    ),
                                    secondary_action="Delete",
                                    on_secondary_action=lambda w, row: row._instance.delete_instance(),
                                    on_select=lambda w: self.app.widgets[
                                        "stack_setup"
                                    ].push(EditServiceBox(w.selection, "stack_setup")),
                                    data=d.DBListSource(d.Service),
                                ),
                                toga.Button(
                                    "Exit",
                                    visibility=(
                                        "visible"
                                        if hasattr(
                                            self.app.main_window, "content_stack"
                                        )
                                        and len(self.app.main_window.content_stack) > 0
                                        else "hidden"
                                    ),
                                    on_press=self.on_done_callback,
                                ),
                            ],
                        ),
                        self.icon_path / "settings-sliders.png",
                    ),
                    (
                        "Help",
                        toga.Row(
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
                                    flex=1,
                                )
                            ]
                        ),
                        self.icon_path / "interrogation.png",
                    ),
                ],
            )
        except Exception as e:
            traceback.print_exc()
            self._error("UI Error", f"{str(e)}, see log.")

    def progress_update(self, is_busy, done, total):
        if "app_activity" in self.app.widgets:
            self.app.widgets["app_activity"].update(
                "Busy" if is_busy else "Ready", is_busy
            )
        if "app_progress" in self.app.widgets:
            if done == total:
                self.app.widgets["app_progress"].stop()
            else:
                self.app.widgets["app_progress"].start(total)
                self.app.widgets["app_progress"].update(done)
