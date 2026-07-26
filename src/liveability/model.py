"""
Application data models and state management singletons.

Provides `AddressModel`, `ServiceModel`, and `ComparisonModel` singletons that bind SQLite database
records to Toga GUI `ListSource` data providers and manage asynchronous proximity search queues.
"""

import datetime as dt
from itertools import product
from pathlib import Path
from queue import Queue
from rubicon.objc import ObjCClass
import toga
from toga.sources import ListSource

from . import db as d
from . import geography as g

class RouteGenerator:
    """Manages background route calculation and UI progress notification."""

    def __init__(self) -> None:
        self._queue = Queue()

        # UI Callback hooks: fn(is_busy, current_progress, total_tasks)
        self.on_progress_update: Callable[[bool, int, int], None] | None = None

    def trigger_full_recalculate(self) -> None:
        """Queues all Address/Service pairs that don't yet have a Route."""
        addresses = list(d.Address.select())
        services = list(d.Service.select())

        for addr in addresses:
            for svc in services:
                # Only queue missing routes
                if not d.Route.select().where((d.Route.address == addr) & (d.Route.service == svc)).exists():
                    self._queue.put((addr, svc))
        self._ensure_worker_running()

    def trigger_address_added(self, address: d.Address) -> None:
        """Queues route calculation for a new address across ALL services."""
        services = list(d.Service.select())
        for svc in services:
            self._queue.put((address, svc))
        self._ensure_worker_running()

    def trigger_service_updated(self, service: d.Service) -> None:
        """Recomputes routes for ALL addresses against this updated service."""
        addresses = list(d.Address.select())
        
        # Delete stale routes for this service
        d.Route.delete().where(d.Route.service == service).execute()

        for addr in addresses:
            self._queue.put((addr, service))
        self._ensure_worker_running()

    def _ensure_worker_running(self) -> None:
        if not self._queue.empty():
            self._notify_ui(is_busy=True)
            toga.App.app.loop.call_soon(self._do_queue)

    def _do_queue(self) -> None:
        """Background thread executing the route calculations."""
        if not self._queue.empty():
            address, service = self._queue.get()

            # Broadcast start of task to UI
            self._notify_ui(is_busy=True)

            # --- YOUR GEOSPATIAL LOGIC PLACEHOLDER ---
            self._compute_and_save_route(address, service)
            # ------------------------------------------

            #self._queue.task_done()

            # Broadcast progress step
            self._notify_ui(is_busy=True)

        self._ensure_worker_running()

    def _notify_ui(self, is_busy: bool) -> None:
        """Dispatches progress metrics back to Toga's main GUI loop."""
        if self.on_progress_update:
            self.on_progress_update(
                is_busy,
                d.Route.select().count(),
                d.Address.select().count() * d.Service.select().count()
            )

    def _compute_and_save_route(self, address: Address, service: Service) -> None:
        def step1(result, value, a, s):
            if isinstance(value, ObjCClass('MKMapItem')):
                def step2(result, value, a, s, t, ms):
                    if isinstance(value, ObjCClass('MKETAResponse')):
                        m = ms[0]
                        ms = ms[1:] 
                        if value.expectedTravelTime >= 11 * 60 and len(ms) > 0:
                            g.perform_eta((a.latitude, a.longitude), t, ms[0], lambda r, v, a=a, s=s, t=t, ms=ms: step2(r, v, a, s, t, ms))
                        else:
                            d.Route.replace(
                                address=a,
                                service=s,
                                latitude=t.location.coordinate.latitude,
                                longitude=t.location.coordinate.longitude,
                                distance=value.distance,
                                time=value.expectedTravelTime,
                                mode=d.TravelMode.from_label(ms[0])
                            ).execute()
                            self._queue.task_done()
                            self._notify_ui(is_busy=False)
                            self._ensure_worker_running()
                    else:
                        d.Route.replace(
                            address=a,
                            service=s,
                            error=str(result)
                        )
                        self._queue.task_done()
                        self._notify_ui(is_busy=False)
                        self._ensure_worker_running()
                g.perform_eta((a.latitude, a.longitude), value, '🥾', lambda r, v, a=a, s=s, t=value, m='🥾🚲🚗': step2(r, v, a, s, t, m))
            else:
                d.Route.replace(
                    address=a,
                    service=s,
                    error=str(result)
                )
                self._queue.task_done()
                self._notify_ui(is_busy=False)
                self._ensure_worker_running()
        g.perform_search_at(service.title, address.latitude, address.longitude, lambda r, o=None, a=address, s=service: step1(r, o, a, s))
