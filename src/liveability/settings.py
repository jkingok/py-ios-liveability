"""
Application settings manager using TOML configuration files.

Manages loading, persisting, and default template fallback for application options
via pure-Python `tomlkit`.
"""

from pathlib import Path
import shutil
import tomlkit  # Pure-Python style-preserving library

CONFIG_NAME = "config.toml"


class Settings:
    """
    Singleton class managing application configuration settings.

    :param paths: Toga application paths provider containing `.config` path.
    :type paths: toga.paths.Paths
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, paths):
        if self._initialized:
            return
        self.config_path = paths.config
        self.config_file = self.config_path / CONFIG_NAME
        self.this_path = Path(__file__).resolve().parent
        self.config_defaults = self.this_path / "resources" / "templates" / CONFIG_NAME
        self.config_doc = None
        self.load()
        self._initialized = True

    def load(self):
        """
        Loads the TOML configuration document from disk.

        If the configuration file does not exist, copies the default template first.
        """
        if not self.config_file.exists():
            shutil.copy(self.config_defaults, self.config_file)
        with open(self.config_file, "r", encoding="utf-8") as f:
            self.config_doc = tomlkit.load(f)

    def save(self):
        """
        Persists the current in-memory TOML configuration document to disk.
        """
        self.config_file.write_text(tomlkit.dumps(self.config_doc))

    def get(self, k):
        """
        Retrieves a configuration value by key. Reloads from disk first to reflect external changes.

        :param k: Configuration key name.
        :type k: str
        :returns: Value corresponding to the key.
        """
        self.load()  # allow on-disk changes
        return self.config_doc[k]

    def set(self, k, v):
        """
        Updates a configuration key-value pair and persists it immediately to disk.

        :param k: Configuration key name.
        :type k: str
        :param v: Value to assign to the key.
        """
        self.config_doc[k] = v
        self.save()  # preserve immediately
