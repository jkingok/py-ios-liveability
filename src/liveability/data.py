from dataclasses import dataclass

@dataclass
class Address:
    title: str
    subtitle: str
    latitude: float
    longitude: float

@dataclass
class Service:
    name: str
    emoji: str 
