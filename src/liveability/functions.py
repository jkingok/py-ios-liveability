import base64
import collections
import csv
from dataclasses import dataclass
import io
import json
import logging
import os
from pathlib import Path
import re
import requests
import sqlite3
import toga
import urllib.parse

from . import data as d

DB_NAME = "liveability.db"

class Functions:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            # Create the single instance and cache it on the class
            cls._instance = super().__new__(cls)
            # Initialize flags or containers that only ever happen ONCE
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, paths, settings):
        # __init__ runs EVERY time you call,
        # so guard it to ensure it only initializes once.
        if self._initialized:
            return
        self.settings = settings
        self.cache_path = paths.cache
        self.data_path = paths.data
        self.this_path = Path(__file__).resolve().parent
        self.db_file = self.data_path / DB_NAME
        self.image_path = self.cache_path / "images"
        self.template_path = self.this_path / "resources" / "templates"
        self.init_db()
        self.image_path.mkdir(exist_ok=True)
        self._initialized = True

    def init_db(self) -> None:
        with sqlite3.connect(self.db_file) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_versions (
                    name TEXT PRIMARY KEY,
                    version INTEGER
                ) STRICT
            """)
            cursor = conn.execute("""
                SELECT version FROM schema_versions WHERE name = 'address'
            """)
            # Schema updates
            v = r[0] if (r := cursor.fetchone()) else 0 
            # TODO Alter columns smoothly if table already exists
            conn.executescript(""" 
                CREATE TABLE IF NOT EXISTS address (
                    identifier TEXT PRIMARY KEY,
                    title TEXT,
                    subtitle TEXT,
                    latitude REAL,
                    longitude REAL
                ) STRICT;
                UPDATE schema_versions SET version = 1 WHERE name = 'address'
            """)
        print("Database ready.")

    def get_address_by_id(self, query_identifier: str) -> d.Address | None:
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.execute(
                "SELECT title, subtitle, latitude, longitude FROM address WHERE identifier = ?",
                (query_identifier,)
            )
            row = cursor.fetchone()
        return d.Address(*row) if row else None

    def save_address(self, query_identifier: str, a: d.Address) -> None:
        with sqlite3.connect(self.db_file) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO address VALUES (?, ?, ?, ?, ?)",
                (query_identifier,  a.title, a.subtitle, a.latitude, a.longitude)
            )

    def delete_address(self, query_identifier: str) -> None:
        """Deletes an address from the database by its query_identifier."""
        # Normalise the key exactly how it was saved
        with sqlite3.connect(self.db_file) as conn:
            conn.execute(
                "DELETE FROM address WHERE identifier = ?",
                (query_identifier,)
            )

    def map_addresses(self) -> dict[str, d.Address]:
        cache = {}
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.execute("SELECT identifier, title, subtitle, latitude, longitude FROM address")
            for row in cursor.fetchall():
                cache[row[0]] = d.Address(*row[1:])
        return cache

    def load_addresses(self) -> list[d.Address]:
        cache = []
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.execute("SELECT title, subtitle, latitude, longitude FROM address")
            for row in cursor.fetchall(): 
                cache.append(d.Address(*row))
        return cache
