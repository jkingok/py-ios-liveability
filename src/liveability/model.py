"""
Application data models and state management singletons.

Provides `AddressModel`, `ServiceModel`, and `ComparisonModel` singletons that bind SQLite database
records to Toga GUI `ListSource` data providers and manage asynchronous proximity search queues.
"""

import traceback
from collections.abc import Callable
from queue import Queue

import toga
from peewee import DatabaseError
from playhouse.signals import post_save

from . import db as d
from . import geography as g


class RouteGenerator:
    """Manages background route calculation and UI progress notification."""

    def __init__(self) -> None:
        self._queue = Queue()
        self._listeners = []

        # UI Callback hooks: fn(is_busy, current_progress, total_tasks)
        self.on_progress_update: Callable[[bool, int, int], None] | None = None

        # Generate a unique ID for this instance (using id(self))
        address_uid = f"{d.Address.__name__}_{id(self)}"
        service_uid = f"{d.Service.__name__}_{id(self)}"

        # Connect using dispatch_uid to allow multiple DBListSource instances
        post_save.connect(
            self._on_address_save, sender=d.Address, name=f"{address_uid}_save"
        )
        post_save.connect(
            self._on_service_save, sender=d.Service, name=f"{service_uid}_save"
        )

    def register(self, handler):
        self._listeners.append(handler)

    def trigger_full_recalculate(self) -> None:
        """Queues all Address/Service pairs that don't yet have a Route."""
        addresses = list(d.Address.select())
        services = list(d.Service.select())

        for addr in addresses:
            for svc in services:
                # Only queue missing routes
                if (
                    not d.Route.select()
                    .where((d.Route.address == addr) & (d.Route.service == svc))
                    .exists()
                ):
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

    def _on_address_save(self, sender, instance, created: bool, **kwargs) -> None:
        if created:
            self.trigger_address_added(instance)

    def _on_service_save(self, sender, instance, created: bool, **kwargs) -> None:
        self.trigger_service_updated(instance)

    def _ensure_worker_running(self) -> None:
        if not self._queue.empty():
            self._notify_ui(is_busy=True)
            if toga.App.app:
                toga.App.app.loop.create_task(self._do_queue())

    async def _do_queue(self) -> None:
        """Background thread executing the route calculations."""
        if not self._queue.empty():
            address, service = self._queue.get()

            try:
                # Broadcast start of task to UI
                self._notify_ui(is_busy=True)

                # --- YOUR GEOSPATIAL LOGIC PLACEHOLDER ---
                d.Route.replace(
                    **await self._compute_and_save_route(address, service)
                ).execute()
                # ------------------------------------------
            except (RuntimeError, DatabaseError) as e:
                traceback.print_exc()
                d.Route.replace(
                    address=address, service=service, error=str(e)
                ).execute()
            finally:
                self._queue.task_done()
                self._notify_ui(is_busy=False)
                self._ensure_worker_running()

    def _notify_ui(self, is_busy: bool) -> None:
        """Dispatches progress metrics back to Toga's main GUI loop."""
        if self.on_progress_update:
            self.on_progress_update(
                is_busy,
                d.Route.select().count(),
                d.Address.select().count() * d.Service.select().count(),
            )
        for handler in self._listeners:
            handler()

    async def _compute_and_save_route(
        self, address: d.Address, service: d.Service
    ) -> dict:
        # Find the first matching service for the location
        _, destination = await g.perform_search_at(
            service.title, address.latitude, address.longitude
        )
        if destination:
            for m in "🥾🚲🚗":
                _, eta = await g.perform_eta(
                    (address.latitude, address.longitude), destination, m
                )
                if eta and (eta.expectedTravelTime < 11 * 60 or m == "🚗"):
                    _, eta2 = await g.perform_eta(
                        destination, (address.latitude, address.longitude), m
                    )
                    return {
                        "address": address,
                        "service": service,
                        "latitude": destination.location.coordinate.latitude,
                        "longitude": destination.location.coordinate.longitude,
                        "distance": eta.distance,
                        "time": eta.expectedTravelTime,
                        "distance_return": eta2.distance if eta2 else eta.distance,
                        "time_return": (
                            eta2.expectedTravelTime if eta2 else eta.expectedTravelTime
                        ),
                        "mode": d.TravelMode.from_label(m),
                        "error": None,
                    }
        return {"address": address, "service": service, "error": "No match"}
