"""
Core Toga user interface controller and layout builder.

Constructs the primary application navigation layout using an `OptionContainer` with three tabs:
"List" (address overview, interactive map, amenity evaluation), "Setup" (services configuration),
and "Help" (rendered Markdown documentation webview).
"""

import asyncio
import sys
import traceback
import urllib
from pathlib import Path

import httpx
import toga
from markdown import markdown as md

if sys.platform == "ios":
    from rubicon.objc import SEL, NSObject, ObjCInstance, objc_method, objc_property
    from rubicon.objc.runtime import objc_id

    class RouteMapDelegateProxy(NSObject):
        toga_delegate = objc_property(object, weak=True)

        @objc_method
        def mapView_rendererForOverlay_(
            self, mapView: ObjCInstance, overlay: ObjCInstance
        ) -> ObjCInstance:
            print(f"rendering overlay for {overlay.title}...")
            if overlay.isKindOfClass_(b.MKPolyline):
                renderer = b.MKPolylineRenderer.alloc().initWithPolyline_(overlay)

                # System Blue works on both UIColor (iOS) and NSColor (macOS)
                renderer.strokeColor = (
                    b.UIColor.systemBlueColor()
                    if "out" in str(overlay.title)
                    else b.UIColor.systemCyanColor()
                )
                renderer.lineWidth = 5.0
                return renderer

            if self.toga_delegate and self.toga_delegate.respondsToSelector_(
                SEL("mapView:rendererForOverlay:")
            ):
                return self.toga_delegate.mapView_rendererForOverlay_(mapView, overlay)

            return None

        @objc_method
        def respondsToSelector_(self, selector: SEL) -> bool:
            sel_str = selector.name
            if sel_str == b"mapView:rendererForOverlay:":
                return True
            if self.toga_delegate:
                return self.toga_delegate.respondsToSelector_(selector)
            return False

        @objc_method
        def forwardingTargetForSelector_(self, selector: SEL) -> ObjCInstance:
            return self.toga_delegate


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
        self.title = "Place Compare"  # host_app.formal_name
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
        self.routes = m.RouteGenerator()
        self.routes.on_progress_update = self.progress_update
        self.app.loop.call_soon(self.routes.trigger_full_recalculate)

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

    async def add_address(self, text: str | None = None, url: str | None = None):
        """
        Geocodes a search string or resolves a Apple Maps URL to save a new target address.

        :param text: Address query text.
        :type text: str | None
        :param url: Apple Maps URL string.
        :type url: str | None
        """
        if sys.platform == "ios":

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
                    map_items_list = list(ObjCInstance(r))
                    if len(map_items_list) == 1:
                        record_item(map_items_list[0])
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
                    except httpx.HTTPError as e:
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
        if sys.platform == "ios":
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

    def get_content(self) -> toga.Widget | None:
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

                def __init__(self, parent, row, stack):
                    self.proto = parent
                    self.row = row
                    self.stack = stack
                    self.map = ws.DynamicMapView(
                        d.DBListSource(
                            d.Route.select().where(
                                (d.Route.address == row._instance)
                                & (d.Route.latitude is not None)
                                & (d.Route.longitude is not None)
                            )
                        ),
                        True,
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
                    )

                    if sys.platform == "ios":
                        native_map = self.map._impl.native

                        # 1. Grab Toga's original self-delegated instance (TogaMapView)
                        original_toga_delegate = native_map.delegate

                        # 2. Instantiate our proxy and assign Toga's delegate to it
                        proxy = RouteMapDelegateProxy.alloc().init()
                        proxy.toga_delegate = original_toga_delegate

                        # 3. Retain a strong reference on the Python widget to prevent garbage collection
                        self.map._route_proxy = proxy

                        # 4. Point MKMapView delegate to our proxy
                        native_map.delegate = proxy

                    self.list = toga.DetailedList(
                        flex=1,
                        primary_action="View",
                        on_primary_action=lambda widget, row, **kwargs: self.open_directions_in_maps(
                            row
                        ),
                        on_select=self.select_from_list,
                        data=d.DBListSource(model_or_query=row._instance.routes),
                    )
                    super().__init__(
                        direction="column",
                        children=[
                            ws.LabelledText(
                                "Title", value_text=row.title, readonly=True
                            ),
                            ws.LabelledText(
                                "Subtitle", value_text=row.subtitle, readonly=True
                            ),
                            self.map,
                            self.list,
                            toga.Row(
                                children=[
                                    toga.Button(
                                        "Back",
                                        flex=1,
                                        on_press=lambda _: (
                                            self.app.widgets[self.stack].pop()
                                            if self.app
                                            else None
                                        ),
                                    ),
                                ]
                            ),
                        ],
                        flex=1,
                    )

                def refresh_address_routes(self, address):
                    d.Route.delete().where(d.Route.address == address).execute()
                    if self.app:
                        self.app.loop.call_soon(
                            self.proto.routes.trigger_full_recalculate
                        )

                def add_overlay(self, response, first):
                    if response and len(routes := list(response.routes)) > 0:
                        while first and (overlays := self.map._impl.native.overlays):
                            self.map._impl.native.removeOverlay_(overlays[0])
                        overlay = routes[0].polyline
                        overlay.title = "out" if first else "in"
                        print(f"adding overlay for {overlay.title}...")
                        self.map._impl.native.addOverlay_(overlay)

                def select_from_list(self, widget, **kwargs):
                    route = widget.selection._instance
                    if route.latitude and route.longitude:
                        self.map.location = (route.latitude, route.longitude)

                        asyncio.create_task(
                            g.perform_directions(
                                (route.address.latitude, route.address.longitude),
                                (route.latitude, route.longitude),
                                route.mode.label,
                                self.add_overlay,
                                True,
                            )
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
                                        on_press=lambda _: (
                                            self.app.widgets[self.stack].pop()
                                            if self.app
                                            else None
                                        ),
                                    ),
                                    toga.Button(
                                        "Save",
                                        flex=1,
                                        on_press=lambda w: (
                                            setattr(
                                                self.row._instance,
                                                "name",
                                                (
                                                    self.app.widgets[
                                                        "edit_service_name"
                                                    ].value
                                                    if self.app
                                                    else ""
                                                ),
                                            ),
                                            setattr(
                                                self.row._instance,
                                                "emoji",
                                                (
                                                    self.app.widgets[
                                                        "edit_service_emoji"
                                                    ].value
                                                    if self.app
                                                    else ""
                                                ),
                                            ),
                                            self.row._instance.save(),
                                            (
                                                self.app.widgets[self.stack].pop()
                                                if self.app
                                                else None
                                            ),
                                        ),
                                    ),
                                ]
                            ),
                        ],
                        flex=1,
                    )

            return ws.OptionContainerFactory(
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
                                    on_primary_action=lambda widget, row, **kwargs: self.open_address_in_maps(
                                        row
                                    ),
                                    secondary_action="Delete",
                                    on_secondary_action=lambda widget, row, **kwargs: row._instance.delete_instance(),
                                    on_select=lambda w: self.app.widgets[
                                        "stack_list"
                                    ].push(
                                        ViewAddressBox(self, w.selection, "stack_list")
                                    ),
                                    accessors=("title", "summary", "icon"),
                                    data=d.DBListSource.create_address_summary(),  # d.DBListSource(d.Address.get_summary_list(), ['title', 'subtitle', 'summary', 'icon'], related_models=[d.Route])
                                ),
                                ws.DynamicMapView(
                                    d.DBListSource(d.Address.select()),
                                    zoom=7,
                                    on_select=lambda w, pin: (
                                        self.app.widgets["stack_list"].push(
                                            ViewAddressBox(self, row, "stack_list")
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
                                    secondary_action="Delete",
                                    on_secondary_action=lambda widget, row, **kwargs: row._instance.delete_instance(),
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
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <!-- Configures iOS viewport: sets width, prevents horizontal scroll, and fits notch/home indicator areas -->
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">

  <!-- Informs the browser that the site supports both light and dark system themes -->
  <meta name="color-scheme" content="light dark">

  <title>Embedded Content</title>

  <style>
    /* CSS Variables using light-dark() to switch automatically based on system preference */
    :root {{
      color-scheme: light dark;
      --bg-color: light-dark(#ffffff, #121212);
      --text-color: light-dark(#1c1c1e, #f2f2f7);
      --card-bg: light-dark(#f2f2f7, #1c1c1e);
      --border-color: light-dark(#e5e5ea, #3a3a3c);
    }}

    /* Prevent accidental horizontal overflow */
    *, *::before, *::after {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      padding: 0;
      background-color: var(--bg-color);
      color: var(--text-color);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      line-height: 1.5;

      /* Ensures text wraps properly when zoomed */
      overflow-wrap: break-word;
      word-break: break-word;
    }}

    /* Images scale down to fit container width, preventing layout break on zoom */
    img, video, svg {{
      max-width: 100%;
      height: auto;
    }}
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
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self._error("UI Error", f"{e!s}, see log.")

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
