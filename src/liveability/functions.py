"""
SQLite database persistence layer for the Liveability application.

Provides schema creation, migration tracking, and CRUD operations for addresses and services.
"""

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
    """
    Singleton data access manager performing SQLite operations.

    :param paths: Toga application paths provider containing `.data` and `.cache`.
    :type paths: toga.paths.Paths
    :param settings: Application settings manager instance.
    :type settings: liveability.settings.Settings
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, paths, settings):
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
        """
        Initializes the SQLite database schema and schema version tracking tables.
        """
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
            v = r[0] if (r := cursor.fetchone()) else 0
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

            cursor = conn.execute("""
                SELECT version FROM schema_versions WHERE name = 'service'
            """)
            v = r[0] if (r := cursor.fetchone()) else 0
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS service (
                    identifier TEXT PRIMARY KEY,
                    name TEXT,
                    emoji TEXT
                ) STRICT;
                UPDATE schema_versions SET version = 1 WHERE name = 'service'
            """)

        print("Database ready.")

    def get_address_by_id(self, query_identifier: str) -> d.Address | None:
        """
        Retrieves an address record by unique identifier.

        :param query_identifier: Address record primary key.
        :type query_identifier: str
        :returns: Address dataclass or None if not found.
        :rtype: d.Address | None
        """
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.execute(
                "SELECT title, subtitle, latitude, longitude FROM address WHERE identifier = ?",
                (query_identifier,),
            )
            row = cursor.fetchone()
        return d.Address(*row) if row else None

    def save_address(self, query_identifier: str, a: d.Address) -> None:
        """
        Inserts or updates an address record in the database.

        :param query_identifier: Address record primary key.
        :type query_identifier: str
        :param a: Address object containing properties to save.
        :type a: d.Address
        """
        with sqlite3.connect(self.db_file) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO address VALUES (?, ?, ?, ?, ?)",
                (query_identifier, a.title, a.subtitle, a.latitude, a.longitude),
            )

    def delete_address(self, query_identifier: str) -> None:
        """
        Deletes an address record from the database by identifier.

        :param query_identifier: Address record primary key.
        :type query_identifier: str
        """
        with sqlite3.connect(self.db_file) as conn:
            conn.execute(
                "DELETE FROM address WHERE identifier = ?", (query_identifier,)
            )

    def map_addresses(self) -> dict[str, d.Address]:
        """
        Retrieves all address records as a dictionary mapping identifier to Address object.

        :returns: Dictionary of address records.
        :rtype: dict[str, d.Address]
        """
        cache = {}
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.execute(
                "SELECT identifier, title, subtitle, latitude, longitude FROM address"
            )
            for row in cursor.fetchall():
                cache[row[0]] = d.Address(*row[1:])
        return cache

    def load_addresses(self) -> list[d.Address]:
        """
        Retrieves all address records as a list of Address objects.

        :returns: List of saved addresses.
        :rtype: list[d.Address]
        """
        cache = []
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.execute(
                "SELECT title, subtitle, latitude, longitude FROM address"
            )
            for row in cursor.fetchall():
                cache.append(d.Address(*row))
        return cache

    def get_service_by_id(self, query_identifier: str) -> d.Service | None:
        """
        Retrieves a service record by unique identifier.

        :param query_identifier: Service record primary key.
        :type query_identifier: str
        :returns: Service dataclass or None if not found.
        :rtype: d.Service | None
        """
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.execute(
                "SELECT name, emoji FROM service WHERE identifier = ?",
                (query_identifier,),
            )
            row = cursor.fetchone()
        return d.Service(*row) if row else None

    def save_service(self, query_identifier: str, a: d.Service) -> None:
        """
        Inserts or updates a service record in the database.

        :param query_identifier: Service record primary key.
        :type query_identifier: str
        :param a: Service object containing properties to save.
        :type a: d.Service
        """
        with sqlite3.connect(self.db_file) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO service VALUES (?, ?, ?)",
                (query_identifier, a.name, a.emoji),
            )

    def delete_service(self, query_identifier: str) -> None:
        """
        Deletes a service record from the database by identifier.

        :param query_identifier: Service record primary key.
        :type query_identifier: str
        """
        with sqlite3.connect(self.db_file) as conn:
            conn.execute(
                "DELETE FROM service WHERE identifier = ?", (query_identifier,)
            )

    def map_services(self) -> dict[str, d.Service]:
        """
        Retrieves all service records as a dictionary mapping identifier to Service object.

        :returns: Dictionary of service records.
        :rtype: dict[str, d.Service]
        """
        cache = {}
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.execute("SELECT identifier, name, emoji FROM service")
            for row in cursor.fetchall():
                cache[row[0]] = d.Service(*row[1:])
        return cache

    def load_services(self) -> list[d.Service]:
        """
        Retrieves all service records as a list of Service objects.

        :returns: List of saved services.
        :rtype: list[d.Service]
        """
        cache = []
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.execute("SELECT name, emoji FROM service")
            for row in cursor.fetchall():
                cache.append(d.Service(*row))
        return cache
