from enum import Enum
from functools import lru_cache
from pathlib import Path
from peewee import SqliteDatabase, Proxy, Select, CompositeKey, CharField, Field, FloatField, ForeignKeyField, IntegerField, fn
from playhouse.signals import Model, post_save
from typing import Any, Callable

db_ref = Proxy()
mgr = None

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

    def __init__(self, enum_cls: type[Enum], value_attr: str = "code", *args: Any, **kwargs: Any) -> None:
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
    WALKING = (0, '🥾')
    CYCLING = (1, '🚲')
    TRANSITING = (2, '🚌')
    DRIVING = (3, '🚗')

    def __init__(self, code: int, label: str) -> None:
        self.code = code
        self.label = label

        # Initialize reverse maps on class if they don't exist yet
        if not hasattr(self.__class__, "_by_label"):
            self.__class__._by_label: dict[str, Self] = {}
            self.__class__._by_code: dict[int, Self] = {}

        # Populate O(1) mappings
        self.__class__._by_label[label] = self
        self.__class__._by_code[code] = self

    # --- O(1) Class Methods ---
    @classmethod
    def from_label(cls, label: str) -> Self:
        """O(1) lookup by human-readable string."""
        try:
            return cls._by_label[label]
        except KeyError:
            raise ValueError(f"No {cls.__name__} member with label '{label}'") from None

    @classmethod
    def from_code(cls, code: int) -> Self:
        """O(1) lookup by code."""
        try:
            return cls._by_code[code]
        except KeyError:
            raise ValueError(f"No {cls.__name__} member with code '{code}'") from None

    def __str__(self) -> str:
        return self.label

class Route(BaseModel):
    address = ForeignKeyField(Address, backref='routes', on_delete="CASCADE")
    service = ForeignKeyField(Service, backref='routes', on_delete="CASCADE")
    latitude = FloatField(null=True)
    longitude = FloatField(null=True)
    distance = FloatField(null=True) # metres
    time = IntegerField(null=True) # seconds
    mode = EnumField(TravelMode, value_attr="code", null=True)
    error = CharField(null=True)

    class Meta:
        primary_key = CompositeKey("address", "service")

    @property
    def icon(self) -> None:
        return None

    @property
    def title(self) -> str:
        return self.service.name

    @property
    def subtitle(self) -> str:
        return f"⚠ {self.error}" if self.error else f"By {self.mode} in {self.time}s for {self.distance}m"

class _Manager:
    def __init__(self, db_path: Path) -> None:
        self.db = SqliteDatabase(db_path)
        db_ref.initialize(self.db)
        self.db.connect()
        self.db.create_tables([Address, Service, Route])

@lru_cache(maxsize=1)
def init(db_path: Path | None = None) -> None:
    global mgr
    mgr = _Manager(db_path)

import toga
from toga.sources import ListSource, Row

class DBListSource(ListSource):
    """A Toga ListSource backed by Peewee with live count notifications."""

    def __init__(
        self, 
        model_or_query: type[Model] | Select, 
        accessors: list[str] | None = None,
        on_count_change: Callable[[int], None] | None = None
    ):
        if not accessors:
            accessors = ["title", "subtitle", "icon"]
        super().__init__(accessors=accessors)

        if isinstance(model_or_query, Select):
            self.query = model_or_query
            self.model_cls = model_or_query.model
        else:
            self.model_cls = model_or_query
            self.query = model_or_query.select()

        self.on_count_change = on_count_change
        self.reload_from_db()

    def get_count(self) -> int:
        """Efficiently fetches the total row count from SQLite via Peewee."""
        # Querying count() directly via SQL is faster than len(self) for huge datasets
        return self.query.count()

    def _notify_count(self) -> None:
        """Fires the callback to update UI elements like Toga Labels."""
        if self.on_count_change:
            # We can use get_count() or len(self) if all items are in memory
            self.on_count_change(self.get_count())

    def _create_row_from_instance(self, instance: Model) -> Row:
        # Extract values in the exact positional order of self._accessors
        values = [getattr(instance, f, None) for f in self._accessors]

        # Pass values POSITIONALLY into Row so Toga assigns them to accessors
        row = Row(*values)

        # Attach the underlying Peewee model instance for selection handling
        row._instance = instance
        return row

    def reload_from_db(self) -> None:
        self.clear()
        for instance in self.query:
            row = self._create_row_from_instance(instance)
            self.append(row)
        self._notify_count()

    def add_instance(self, instance: Model) -> Row:
        instance.save()
        row = self._create_row_from_instance(instance)
        self.append(row)
        self._notify_count()  # Trigger count update
        return row

    def remove_instance(self, row: Row) -> None:
        if hasattr(row, "_instance"):
            row._instance.delete_instance()
        self.remove(row)
        self._notify_count()  # Trigger count update
