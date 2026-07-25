"""
Data transfer objects and dataclasses for the Liveability application.

Provides structured data containers representing geographic addresses and target services/amenities.
"""

from dataclasses import dataclass

@dataclass
class Address:
    """
    Data model representing a physical address or property location.

    :param title: Descriptive title or location name.
    :type title: str
    :param subtitle: Formatted address string or secondary description.
    :type subtitle: str
    :param latitude: Geographic latitude in decimal degrees.
    :type latitude: float
    :param longitude: Geographic longitude in decimal degrees.
    :type longitude: float
    """
    title: str = ""
    subtitle: str = ""
    latitude: float = 0.0
    longitude: float = 0.0

@dataclass
class Service:
    """
    Data model representing a category of service or amenity to locate.

    :param name: Name of the service category (e.g. 'Supermarket', 'Park').
    :type name: str
    :param emoji: Emoji symbol representing the service (e.g. '🛒', '🌳').
    :type emoji: str
    """
    name: str = ""
    emoji: str = ""
