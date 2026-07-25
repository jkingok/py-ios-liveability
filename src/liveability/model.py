"""
Application data models and state management singletons.

Provides `AddressModel`, `ServiceModel`, and `ComparisonModel` singletons that bind SQLite database
records to Toga GUI `ListSource` data providers and manage asynchronous proximity search queues.
"""

import datetime as dt
from itertools import product
from pathlib import Path
from rubicon.objc import ObjCClass
import toga
from toga.sources import ListSource

from . import data as d
from . import geography as g


class AddressModel:
    """
    Singleton data model for managing target property addresses.

    Binds saved address data to a Toga :class:`toga.sources.ListSource` for list views
    and manages map pins and center calculation.

    :param paths: Toga application paths instance.
    :type paths: toga.paths.Paths
    :param fns: Database functions manager instance.
    :type fns: liveability.functions.Functions
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, paths, fns):
        if self._initialized:
            return
        self.fns = fns
        self.cache_path = paths.cache
        self.items_list_source = ListSource(
            accessors=["title", "subtitle", "icon", "index"],
            data=[]
        )
        self.list_count_label = None
        self.map = None
        self.listeners = []
        self.reload_items()
        self._initialized = True

    def register(self, callback):
        """
        Registers a listener callback function to be invoked when address items are reloaded.

        :param callback: Function to call on model reload.
        :type callback: callable
        """
        self.listeners.append(callback)

    def reload_items(self, widget=None, row=None):
        """
        Reloads address records from the database into the Toga ListSource and updates attached UI elements.

        :param widget: Optional triggering widget.
        :param row: Optional triggering list row.
        """
        self.items_list_source.clear()
        for key, value in self.fns.map_addresses().items():
            self.items_list_source.append({
                "title": value.title,
                "subtitle": value.subtitle,
                "icon": toga.Image(f) if (f := self.cache_path / f"images/maps/{key}.png").exists() else None,
                "index": key
            })
            if self.list_count_label:
                self.list_count_label.text = self.item_count_text()
            if self.map:
                self.map.location = self.find_centre()
                self.map.pins.clear()
                for pin in [toga.MapPin(location=e, title=str(i + 1)) for i, e in enumerate(self.get_pins())]:
                    self.map.pins.add(pin)
            for l in self.listeners:
                l()

    def item_count_text(self) -> str:
        """
        Returns formatted text displaying total address location count.

        :returns: Formatted string (e.g. '3 location(s)').
        :rtype: str
        """
        return f"{len(self.items_list_source)} location(s)"

    def set_list_count_label(self, w: toga.Label) -> toga.Label:
        """
        Attaches a Toga Label widget to display address count.

        :param w: Label widget instance.
        :type w: toga.Label
        :returns: Attached label widget.
        :rtype: toga.Label
        """
        self.list_count_label = w
        w.text = self.item_count_text()
        return w

    def set_map(self, w: toga.MapView) -> toga.MapView:
        """
        Attaches a Toga MapView widget to display address pins and center location.

        :param w: MapView widget instance.
        :type w: toga.MapView
        :returns: Attached MapView widget.
        :rtype: toga.MapView
        """
        self.map = w
        w.location = self.find_centre()
        w.pins.clear()
        for pin in [toga.MapPin(location=e, title=str(i + 1)) for i, e in enumerate(self.get_pins())]:
            w.pins.add(pin)
        return w

    def get(self, key: str) -> d.Address | None:
        """
        Fetches an address object by unique identifier.

        :param key: Address identifier string.
        :type key: str
        :returns: Address instance or None.
        :rtype: d.Address | None
        """
        return self.fns.get_address_by_id(key)

    def save(self, key: str, values: dict):
        """
        Saves or updates an address record and reloads list items.

        :param key: Address identifier.
        :type key: str
        :param values: Dictionary of Address field attributes.
        :type values: dict
        """
        self.fns.save_address(key, d.Address(**values))
        self.reload_items()

    def delete(self, key: str):
        """
        Deletes an address record and reloads list items.

        :param key: Address identifier.
        :type key: str
        """
        self.fns.delete_address(key)
        self.reload_items()

    def find_centre(self) -> tuple[float, float] | None:
        """
        Calculates the geographical midpoint (bounding box center) across all stored addresses.

        :returns: Latitude and longitude tuple or None if no valid coordinates exist.
        :rtype: tuple[float, float] | None
        """
        l_la = None
        u_la = None
        l_lo = None
        u_lo = None
        for key, value in self.fns.map_addresses().items():
            la = value.latitude
            lo = value.longitude
            l_la = la if (not l_la) or (la < l_la) else l_la
            u_la = la if (not u_la) or (la > u_la) else u_la
            l_lo = lo if (not l_lo) or (lo < l_lo) else l_lo
            u_lo = lo if (not u_lo) or (lo > u_lo) else u_lo
        return ((l_la + u_la) / 2, (l_lo + u_lo) / 2) if (l_la and u_la and l_lo and u_lo) else None

    def get_pins(self) -> list[tuple[float, float]]:
        """
        Retrieves a list of coordinate tuples for map pins across all addresses.

        :returns: List of (latitude, longitude) tuples.
        :rtype: list[tuple[float, float]]
        """
        return [(value.latitude, value.longitude) for key, value in self.fns.map_addresses().items()]


class ServiceModel:
    """
    Singleton data model for managing service / amenity categories.

    Binds saved service definitions to a Toga :class:`toga.sources.ListSource`.

    :param paths: Toga application paths instance.
    :type paths: toga.paths.Paths
    :param fns: Database functions manager instance.
    :type fns: liveability.functions.Functions
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, paths, fns):
        if self._initialized:
            return
        self.fns = fns
        self.cache_path = paths.cache
        self.items_list_source = ListSource(
            accessors=["title", "subtitle", "icon", "index"],
            data=[]
        )
        self.list_count_label = None
        self.listeners = []
        self.reload_items()
        self._initialized = True

    def register(self, callback):
        """
        Registers a listener callback invoked when service items reload.

        :param callback: Callback function.
        :type callback: callable
        """
        self.listeners.append(callback)

    def reload_items(self, widget=None, row=None):
        """
        Reloads service records from the database into the ListSource and updates UI labels.
        """
        self.items_list_source.clear()
        for key, value in self.fns.map_services().items():
            self.items_list_source.append({
                "title": value.name,
                "subtitle": value.emoji,
                "icon": toga.Image(f) if (f := self.cache_path / f"images/icons/{key}.png").exists() else None,
                "index": key
            })
        if self.list_count_label:
            self.list_count_label.text = self.item_count_text()
        for l in self.listeners:
            l()

    def item_count_text(self) -> str:
        """
        Returns formatted text displaying total service count.

        :returns: Formatted string (e.g. '4 service(s)').
        :rtype: str
        """
        return f"{len(self.items_list_source)} service(s)"

    def set_list_count_label(self, w: toga.Label) -> toga.Label:
        """
        Attaches a Toga Label widget to display service count.

        :param w: Label widget instance.
        :type w: toga.Label
        :returns: Attached label widget.
        :rtype: toga.Label
        """
        self.list_count_label = w
        w.text = self.item_count_text()
        return w

    def get(self, key: str) -> d.Service | None:
        """
        Fetches a service object by identifier.

        :param key: Service identifier.
        :type key: str
        :returns: Service object or None.
        :rtype: d.Service | None
        """
        return self.fns.get_service_by_id(key)

    def save(self, key: str, values: dict):
        """
        Saves or updates a service record and reloads items.

        :param key: Service identifier.
        :type key: str
        :param values: Dictionary of Service attributes.
        :type values: dict
        """
        self.fns.save_service(key, d.Service(**values))
        self.reload_items()

    def delete(self, key: str):
        """
        Deletes a service record and reloads items.

        :param key: Service identifier.
        :type key: str
        """
        self.fns.delete_service(key)
        self.reload_items()


class ComparisonModel:
    """
    Singleton comparison engine model for matrix evaluation.

    Computes spatial proximity and travel ETAs across the Cartesian product of stored
    addresses and services using Apple MapKit APIs.

    :param paths: Toga application paths instance.
    :type paths: toga.paths.Paths
    :param fns: Database functions manager instance.
    :type fns: liveability.functions.Functions
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, paths, fns):
        if self._initialized:
            return
        self.fns = fns
        self.cache_path = paths.cache
        self.items_list_sources = {}
        self.activity = None
        self.progress = None
        self.comparisons = {}
        self.busy = False
        self.queue = set()
        self.reload_items()
        AddressModel._instance.register(self.reload_items)
        ServiceModel._instance.register(self.reload_items)
        self._initialized = True

    def reload_items(self):
        """
        Schedules MapKit search and travel directions queries for missing address x service pairs.
        """
        comparisons_total = int(len(AddressModel._instance.items_list_source) * len(ServiceModel._instance.items_list_source))
        comparisons_done = 0

        if self.progress:
            self.progress.start(comparisons_total)

        for a, s in product(AddressModel._instance.items_list_source, ServiceModel._instance.items_list_source):
            if a.title not in self.items_list_sources:
                self.items_list_sources[a.title] = ListSource(
                    accessors=["title", "subtitle", "icon", "index", "latitude", "longitude", "symbol"],
                    data=[]
                )
            if not self.items_list_sources[a.title].find({"title": s.title}, default=None) and (a.title, s.title) not in self.queue:
                print(f"TODO {a.title} to {s.title}")
                self.queue.add((a.title, s.title))
                a2 = AddressModel._instance.get(a.index)

                def step1(result, value, a, s):
                    if isinstance(value, ObjCClass('MKMapItem')):
                        def step2(result, value, a, s, t, ms):
                            if isinstance(value, ObjCClass('MKETAResponse')):
                                m = ms[0]
                                ms = ms[1:]
                                if value.expectedTravelTime >= 11 * 60 and len(ms) > 0:
                                    g.perform_eta((a[1].latitude, a[1].longitude), t, ms[0], lambda r, v, a=a, s=s, t=t, ms=ms: step2(r, v, a, s, t, ms))
                                else:
                                    self.items_list_sources[a[0].title].append({
                                        "title": s.title,
                                        "subtitle": str(result),
                                        "icon": None,
                                        "index": f"{a[0].title} to {s.title}",
                                        "latitude": t.location.coordinate.latitude,
                                        "longitude": t.location.coordinate.longitude
                                    })
                                    self.queue.remove((a[0].title, s.title))
                                    self.done_one()
                            else:
                                self.items_list_sources[a[0].title].append({
                                    "title": s.title,
                                    "subtitle": "⚠️ " + str(result),
                                    "icon": None,
                                    "index": f"{a[0].title} to {s.title}"
                                })
                                self.queue.remove((a[0].title, s.title))
                                self.done_one()

                        g.perform_eta((a[1].latitude, a[1].longitude), value, '🥾', lambda r, v, a=a, s=s, t=value, m='🥾🚲🚗': step2(r, v, a, s, t, m))
                    else:
                        self.items_list_sources[a[0].title].append({
                            "title": s.title,
                            "subtitle": "⚠️ " + str(result),
                            "icon": None,
                            "index": f"{a[0].title} to {s.title}"
                        })
                        self.queue.remove((a[0].title, s.title))
                        self.done_one()

                g.perform_search_at(s.title, a2.latitude, a2.longitude,
                                    lambda r, o=None, a=(a, a2), s=s: step1(r, o, a, s))

        if self.progress:
            self.progress.update(comparisons_done)
        if self.activity:
            self.activity.update("Busy" if (on := comparisons_total > comparisons_done) else "Ready", on)

    def set_activity(self, w):
        """
        Attaches a LabelledActivity widget to track busy state.

        :param w: Activity widget instance.
        """
        self.activity = w
        self.reload_items()
        return w

    def set_progress(self, w):
        """
        Attaches a LabelledProgress widget to track comparison evaluation progress.

        :param w: Progress widget instance.
        """
        self.progress = w
        self.reload_items()
        return w

    def done_one(self):
        """
        Increments evaluation progress when one address-service comparison completes.
        """
        if self.progress:
            self.progress.increment()
        if self.activity:
            self.activity.update("Ready" if (off := self.progress.is_done()) else "Busy", not off)

    def get(self, key: str) -> ListSource:
        """
        Retrieves the ListSource of calculated amenities for a specific address.

        :param key: Address title key string.
        :type key: str
        :returns: ListSource containing amenity distance and ETA results.
        :rtype: toga.sources.ListSource
        """
        return self.items_list_sources[key]
