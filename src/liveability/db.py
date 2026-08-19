from collections.abc import Callable, Sequence
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Self

import toga
from peewee import (
    JOIN,
    AutoField,
    Case,
    CharField,
    Field,
    FloatField,
    ForeignKeyField,
    IntegerField,
    Proxy,
    Select,
    SqliteDatabase,
    fn,
)
from playhouse.signals import Model, post_delete, post_save
from toga.sources import ListSource, Row

from . import geography as g

db_ref = Proxy()
mgr = None


def count_to_emoji(count: int) -> str:
    if count == 10:
        return "🔟"
    digit_map = {
        "0": "0️⃣",
        "1": "1️⃣",
        "2": "2️⃣",
        "3": "3️⃣",
        "4": "4️⃣",
        "5": "5️⃣",
        "6": "6️⃣",
        "7": "7️⃣",
        "8": "8️⃣",
        "9": "9️⃣",
    }
    return "".join(digit_map[d] for d in str(count))


class BaseModel(Model):
    class Meta:
        database = db_ref


class Address(BaseModel):
    title = CharField()
    subtitle = CharField()
    latitude = FloatField()
    longitude = FloatField()

    @property
    def icon(self) -> None:
        return None

    @property
    def summary(self):
        """Formats the aggregated counts into a clean, readable one-liner."""
        if not getattr(self, "total_routes", 0):
            return "🛑 No routes"

        # Emoji mappings for non-zero counts
        mode_map = [
            (TravelMode.WALKING.label, getattr(self, "walking_count", 0)),
            (TravelMode.CYCLING.label, getattr(self, "cycling_count", 0)),
            (TravelMode.DRIVING.label, getattr(self, "driving_count", 0)),
            (TravelMode.TRANSITING.label, getattr(self, "transiting_count", 0)),
            ("⚠️", getattr(self, "error_count", 0)),
        ]

        parts = [
            f"{count_to_emoji(count)}{emoji}" for emoji, count in mode_map if count > 0
        ]
        return " ".join(parts) if parts else self.__data__.get("subtitle") or ""

    @classmethod
    def get_summary_list(cls):
        """Returns Address models with explicit mode and error counts attached."""
        return (
            cls.select(
                cls,
                fn.COUNT(Route.id).alias("total_routes"),
                fn.SUM(
                    Case(None, [(Route.mode == TravelMode.DRIVING.code, 1)], 0)
                ).alias("driving_count"),
                fn.SUM(
                    Case(None, [(Route.mode == TravelMode.TRANSITING.code, 1)], 0)
                ).alias("transiting_count"),
                fn.SUM(
                    Case(None, [(Route.mode == TravelMode.WALKING.code, 1)], 0)
                ).alias("walking_count"),
                fn.SUM(
                    Case(None, [(Route.mode == TravelMode.CYCLING.code, 1)], 0)
                ).alias("cycling_count"),
                # Flag rows where a Route exists but mode is NULL
                fn.SUM(
                    Case(
                        None,
                        [((Route.id.is_null(False) & Route.mode.is_null(True)), 1)],
                        0,
                    )
                ).alias("error_count"),
            )
            .join(Route, JOIN.LEFT_OUTER, on=(cls.id == Route.address)) # pyright: ignore [reportAttributeAccessIssue]
            .group_by(cls.id) # pyright: ignore [reportAttributeAccessIssue]
        )


class Service(BaseModel):
    name = CharField()
    emoji = CharField()

    @property
    def icon(self) -> None:
        return None

    @property
    def title(self) -> str:
        return self.name

    @property
    def subtitle(self) -> str:
        return self.emoji


class EnumField(Field):
    """Custom Peewee Field for storing Enums by an explicit attribute (e.g., 'code')."""

    # SQLite column type
    field_type = "INTEGER"

    def __init__(
        self, enum_cls: type[Enum], value_attr: str = "code", *args: Any, **kwargs: Any
    ) -> None:
        self.enum_cls = enum_cls
        self.value_attr = value_attr

        # Build a fast lookup mapping raw DB code -> Enum member
        self._value_map = {getattr(member, value_attr): member for member in enum_cls}
        super().__init__(*args, **kwargs)

    def db_value(self, value: Any) -> Any:
        """Extract the DB code when saving."""
        if value is None:
            return None
        if isinstance(value, self.enum_cls):
            return getattr(value, self.value_attr)
        return value

    def python_value(self, value: Any) -> Any:
        """Convert the raw DB integer back into the Enum instance when reading."""
        if value is None:
            return None
        return self._value_map.get(value)


class TravelMode(Enum):
    # (code, display_label)
    WALKING = (0, "🥾")
    CYCLING = (1, "🚲")
    TRANSITING = (2, "🚌")
    DRIVING = (3, "🚗")

    def __init__(self, code: int, label: str) -> None:
        self.code = code
        self.label = label

        # Initialize reverse maps on class if they don't exist yet
        if not hasattr(self.__class__, "_by_label"):
            self.__class__._by_label = {} #: dict[str, Self] = {} # pyright: ignore [reportAttributeAccessIssue]
            self.__class__._by_code = {} #: dict[int, Self] = {} # pyright: ignore [reportAttributeAccessIssue]

        # Populate O(1) mappings
        self.__class__._by_label[label] = self # pyright: ignore [reportAttributeAccessIssue]
        self.__class__._by_code[code] = self # pyright: ignore [reportAttributeAccessIssue]

    # --- O(1) Class Methods ---
    @classmethod
    def from_label(cls, label: str) -> Self:
        """O(1) lookup by human-readable string."""
        try:
            return cls._by_label[label] # pyright: ignore [reportAttributeAccessIssue]
        except KeyError:
            raise ValueError(f"No {cls.__name__} member with label '{label}'") from None

    @classmethod
    def from_code(cls, code: int) -> Self:
        """O(1) lookup by code."""
        try:
            return cls._by_code[code] # pyright: ignore [reportAttributeAccessIssue]
        except KeyError:
            raise ValueError(f"No {cls.__name__} member with code '{code}'") from None

    def __str__(self) -> str:
        return self.label


class Route(BaseModel):
    id = AutoField()
    address = ForeignKeyField(Address, backref="routes", on_delete="CASCADE")
    service = ForeignKeyField(Service, backref="routes", on_delete="CASCADE")
    latitude = FloatField(null=True)
    longitude = FloatField(null=True)
    distance = FloatField(null=True)  # metres
    time = IntegerField(null=True)  # seconds
    distance_return = FloatField(null=True)
    time_return = FloatField(null=True)
    mode = EnumField(TravelMode, value_attr="code", null=True)
    error = CharField(null=True)

    class Meta: # pyright: ignore [reportIncompatibleVariableOverride]
        indexes = ((("address", "service"), True),)

    @property
    def icon(self) -> None:
        return None

    @property
    def title(self) -> str:
        return self.service.name

    @property
    def subtitle(self) -> str:
        return (
            f"⚠ {self.error}"
            if self.error
            else g.format_eta(
                str(self.mode),
                self.time or 0.0,
                self.distance or 0.0,
                self.time_return,
                self.distance_return,
            )
        )


class _Manager:
    def __init__(self, db_path: Path) -> None:
        self.db = SqliteDatabase(str(db_path), pragmas={"foreign_keys": 1})
        db_ref.initialize(self.db)
        self.db.connect()
        self.db.create_tables([Address, Service, Route])
        # Delete routes where the referenced address no longer exists
        Route.delete().where(Route.address.not_in(Address.select(Address.id))).execute() # pyright: ignore [reportAttributeAccessIssue]
        Route.delete().where(Route.service.not_in(Service.select(Service.id))).execute() # pyright: ignore [reportAttributeAccessIssue]


@lru_cache(maxsize=1)
def init(db_path: Path | None = None) -> None:
    global mgr
    if db_path:
        mgr = _Manager(db_path)


class DBListSource(ListSource):
    """A Toga ListSource backed by Peewee with live count and relation updates."""

    @classmethod
    def create_address_summary(cls, on_count_change=None):
        return DBListSource(
            Address.get_summary_list(),
            ["title", "summary", "icon", "subtitle"],
            on_count_change,
            [Route],
            True,
        )

    def __init__(
        self,
        model_or_query: type[Model] | Select,
        accessors: list[str] | None = None,
        on_count_change: Callable[[int], None] | None = None,
        related_models: Sequence[type[Model]] | None = None,
        watch_routes: bool = False,
    ):
        if not accessors:
            accessors = ["title", "subtitle", "icon"]
        super().__init__(accessors=accessors)

        if isinstance(model_or_query, Select):
            self.query = model_or_query
            self.model_cls = model_or_query.model # pyright: ignore [reportAttributeAccessIssue]
        else:
            self.model_cls = model_or_query
            self.query = model_or_query.select()

        self.on_count_change = on_count_change
        self.related_models = related_models or []

        # Unique ID for signal dispatching
        dispatch_uid = f"{self.model_cls.__name__}_{id(self)}"

        # 1. Connect primary model signals
        post_save.connect(
            self._on_post_save, sender=self.model_cls, name=f"{dispatch_uid}_save"
        )
        post_delete.connect(
            self._on_post_delete, sender=self.model_cls, name=f"{dispatch_uid}_delete"
        )

        # 2. Connect secondary/joined model signals
        for idx, rel_model in enumerate(self.related_models):
            post_save.connect(
                self._on_related_change,
                sender=rel_model,
                name=f"{dispatch_uid}_rel_{rel_model.__name__}_{idx}_save",
            )
            post_delete.connect(
                self._on_related_change,
                sender=rel_model,
                name=f"{dispatch_uid}_rel_{rel_model.__name__}_{idx}_delete",
            )

        if watch_routes and toga.App.app and hasattr(toga.App.app, "routes"):
            toga.App.app.routes.register(self.reload_from_db) # pyright: ignore [reportAttributeAccessIssue]

        self.reload_from_db()

    def _on_related_change(self, sender, instance, created=False):
        """Handler triggered whenever a related model (e.g. Route) changes."""
        # Option A: Full reload to refresh aggregate subqueries/counts
        self.reload_from_db()

        # Option B (Targeted): If instance has FK back to primary model, reload targeted row
        # foreign_key_val = getattr(instance, 'address_id', None)
        # if foreign_key_val:
        #     self.refresh_row_by_id(foreign_key_val)

    def _extract_data(self, instance: Model) -> dict[str, str]:
        """Utility to convert instance attributes into dictionary for ListSource."""
        values = {
            f: (getattr(instance, f))  # if getattr(instance, f) is not None else "")
            for f in self._accessors
        } if self._accessors else {}
        values["_instance"] = instance
        return values

    def _find_row_by_instance(self, instance: Model) -> tuple[int, Row | None]:
        """Finds the index and Row object corresponding to a Peewee model instance."""
        pk = instance._pk # pyright: ignore [reportAttributeAccessIssue]
        for index, row in enumerate(self): # pyright: ignore [reportArgumentType]
            if hasattr(row, "_instance") and row._instance._pk == pk:
                return index, row
        return -1, None

    def _on_post_save(self, sender, instance, created: bool, **kwargs) -> None:
        row_data = self._extract_data(instance)

        if created:
            # 1. NEW ITEM: Append directly
            row = self.append(row_data)
            self._notify_count()
        else:
            # 2. UPDATED ITEM: Locate existing row and update attributes in place
            _, row = self._find_row_by_instance(instance)
            if row is not None:
                # Update attributes on the existing Toga Row
                for key, val in row_data.items():
                    setattr(row, key, val)

                # Keep internal model instance current
                row._instance = instance

                # Notify attached Toga listeners (like MapView or DetailedList) of row updates
                self._notify("change", item=row) # pyright: ignore [reportAttributeAccessIssue]

    def _on_post_delete(self, sender, instance, **kwargs) -> None:
        # 3. DELETED ITEM: Locate and remove only the deleted row
        _, row = self._find_row_by_instance(instance)
        if row is not None:
            self.remove(row)
            self._notify_count()

    def get_count(self) -> int:
        """Efficiently fetches the total row count from SQLite via Peewee."""
        # Querying count() directly via SQL is faster than len(self) for huge datasets
        return self.query.count()

    def _notify_count(self) -> None:
        """Fires the callback to update UI elements like Toga Labels."""
        if self.on_count_change:
            # We can use get_count() or len(self) if all items are in memory
            self.on_count_change(self.get_count())

    def reload_from_db(self) -> None:
        self.clear()
        for instance in self.query.clone().iterator():
            row_data = {
                f: (getattr(instance, f) if getattr(instance, f) is not None else "")
                for f in self._accessors
            } if self._accessors else {}
            row_data["_instance"] = instance
            # Bypassing explicit Row instantiation by appending dict directly
            self.append(row_data)
        self._notify_count()

    def add_instance(self, instance: Model) -> Row:
        instance.save()
        # post_save signal will handle reload_from_db() automatically
        return self[-1] if len(self) > 0 else Row()

    def remove_instance(self, row: Row) -> None:
        if hasattr(row, "_instance"):
            row._instance.delete_instance() # pyright: ignore [reportAttributeAccessIssue]
            # post_delete signal handles reload_from_db() automatically
