import datetime as dt
from itertools import product
from pathlib import Path
import toga
from toga.sources import ListSource

from . import data as d

class AddressModel:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            # Create the single instance and cache it on the class
            cls._instance = super().__new__(cls)
            # Initialize flags or containers that only ever happen ONCE
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, paths, fns):
        # __init__ runs EVERY time you call,
        # so guard it to ensure it only initializes once.
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
        self.listeners.append(callback)

    def reload_items(self, widget=None, row=None):
        self.items_list_source.clear()
        for key, value in self.fns.map_addresses().items():
            # Safely build a toga.Image if an icon path was specified and exists
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

    def item_count_text(self):
        return f"{len(self.items_list_source)} location(s)"
         
    def set_list_count_label(self, w):
        self.list_count_label = w
        w.text = self.item_count_text()
        return w

    def set_map(self, w):
        self.map = w
        w.location = self.find_centre()
        w.pins.clear()
        for pin in [toga.MapPin(location=e, title=str(i + 1)) for i, e in enumerate(self.get_pins())]:
            w.pins.add(pin)
        return w

    def get(self, key):
        return self.fns.get_address_by_id(key)  

    def save(self, key, values):
        self.fns.save_address(key, d.Address(**values))
        # TODO Be able to find and update correct item to avoid full reload
        self.reload_items()

    def delete(self, key):
        self.fns.delete_address(key)
        # TODO Be able to find and update correct item to avoid full reload
        self.reload_items()

    def find_centre(self):
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

    def get_pins(self):
        return [(value.latitude, value.longitude) for key, value in self.fns.map_addresses().items()]

class ServiceModel:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            # Create the single instance and cache it on the class
            cls._instance = super().__new__(cls)
            # Initialize flags or containers that only ever happen ONCE
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, paths, fns):
        # __init__ runs EVERY time you call,
        # so guard it to ensure it only initializes once.
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
        self.listeners.append(callback)

    def reload_items(self, widget=None, row=None):
        self.items_list_source.clear()
        for key, value in self.fns.map_services().items():
            # Safely build a toga.Image if an icon path was specified and exists
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

    def item_count_text(self):
        return f"{len(self.items_list_source)} service(s)"
 
    def set_list_count_label(self, w):
        self.list_count_label = w
        w.text = self.item_count_text()
        return w
 
    def get(self, key):
        return self.fns.get_service_by_id(key)  

    def save(self, key, values):
        self.fns.save_service(key, d.Service(**values))
        # TODO Be able to find and update correct item to avoid full reload
        self.reload_items()

    def delete(self, key):
        self.fns.delete_service(key)
        # TODO Be able to find and update correct item to avoid full reload
        self.reload_items()

class ComparisonModel:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            # Create the single instance and cache it on the class
            cls._instance = super().__new__(cls)
            # Initialize flags or containers that only ever happen ONCE
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, paths, fns):
        # __init__ runs EVERY time you call,
        # so guard it to ensure it only initializes once.
        if self._initialized:
            return
        self.fns = fns
        self.cache_path = paths.cache
        self.items_list_source = ListSource(
            accessors=["title", "subtitle", "icon", "index"],
            data=[]
        )
        self.activity = None
        self.progress = None
        self.comparisons = {}
        self.reload_items()
        AddressModel._instance.register(self.reload_items)
        ServiceModel._instance.register(self.reload_items)
        self._initialized = True

    def reload_items(self):
        # The amount of work to be done
        comparisons_total = int(len(AddressModel._instance.items_list_source) * len(ServiceModel._instance.items_list_source))
        if self.activity:
            self.activity.update("Busy", True)
        if self.progress:
            self.progress.start(comparisons_total)
        
        # Start scheduling work
        for a, s in product(AddressModel._instance.items_list_source, ServiceModel._instance.items_list_source):
            print(f"TODO {a.title} to {s.title}") 

    def set_activity(self, w):
        self.activity = w
        self.reload_items()
        return w

    def set_progress(self, w):
        self.progress = w
        self.reload_items()
        return w