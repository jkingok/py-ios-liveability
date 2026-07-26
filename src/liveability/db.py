from enum import Enum
from functools import lru_cache
from pathlib import Path
from peewee import SqliteDatabase, Model, Proxy, Select, CharField, Field, FloatField, ForeignKeyField, IntegerField, fn
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

class Service(BaseModel):
    name = CharField()
    emoji = CharField()

    @property
    def title() -> str:
        return self.name

    @property
    def subtitle() -> str:
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

    def __str__(self) -> str:
        return self.label

class Route(BaseModel):
    address = ForeignKeyField(Address, backref='routes')
    service = ForeignKeyField(Service)
    latitude = FloatField()
    longitude = FloatField()
    distance = FloatField() # metres
    time = IntegerField() # seconds
    mode = EnumField(TravelMode, value_attr="code")

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
            accessors = ["icon", "title", "subtitle"]
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

    def reload_from_db(self) -> None:
        self.clear()
        for instance in self.query:
            row_data = {f: getattr(instance, f) for f in self._accessors}
            row = Row(**row_data)
            row._instance = instance
            self.append(row)
        self._notify_count()

    def add_instance(self, instance: Model) -> Row:
        instance.save()
        row_data = {f: getattr(instance, f) for f in self._accessors}
        row = Row(**row_data)
        row._instance = instance
        self.append(row)
        self._notify_count()  # Trigger count update
        return row

    def remove_instance(self, row: Row) -> None:
        if hasattr(row, "_instance"):
            row._instance.delete_instance()
        self.remove(row)
        self._notify_count()  # Trigger count update
