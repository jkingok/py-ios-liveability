"""
MapKit spatial search, directions ETA calculation, and map launch module.

Performs asynchronous spatial queries via Apple MapKit (`MKLocalSearch`), calculates
travel time estimates (`MKDirectionsRequest`), and launches target locations in Apple Maps (`MKMapItem`).
"""

import asyncio
from rubicon.objc import Block, ObjCClass, ObjCInstance
from rubicon.objc.runtime import objc_id
import toga

from . import bridge as b

def open_in_maps(items: list[tuple[float, float, str]], mode=None) -> bool:
    """
    Creates an Objective-C MKMapItem from geographic coordinates, title, and address string,
    and opens it in Apple Maps via MapKit.

    :param items: Location(s) in latitude and longitude in decimal degrees then string title
    :type items: list[tuple[float, float, str]]
    :param mode: Mode of transportation if directions (pair of items)
    :returns: True if MapKit accepted the launch request.
    :rtype: bool
    """
    def MKMapItemMake(latitude, longitude, name):
        mi = b.MKMapItem.alloc().initWithLocation(b.CLLocation.alloc().initWithLatitude(latitude, longitude=longitude), address=None)
        mi.name = name
        return mi
    lo = {}
    match len(items):
        case 0:
            return False
        case 1:
            mi = MKMapItemMake(*items[0])
            return mi.openInMapsWithLaunchOptions(lo)
        case 2: 
            k = str(b.constant("MKLaunchOptionsDirectionsModeKey"))
            v = b.constant("MKLaunchOptionsDirectionsModeDefault") 
            match mode:
                case '🚗':
                    v = b.constant("MKLaunchOptionsDirectionsModeDriving")
                case '🚌':
                    v = b.constant("MKLaunchOptionsDirectionsModeTransit")
                case '🚲':
                    v = b.constant("MKLaunchOptionsDirectionsModeCycling")
                case '🥾':
                    v = b.constant("MKLaunchOptionsDirectionsModeWalking")
            lo[k] = v
    return b.MKMapItem.openMapsWithItems([ MKMapItemMake(*item) for item in items ], launchOptions=lo)

def generic_completion(response_ptr, error_ptr, future):
    if future.done():
        return
  
    if error_ptr:
        error = ObjCInstance(error_ptr)
        toga.App.app.loop.call_soon_threadsafe(
            future.set_exception, RuntimeError(str(error.localizedDescription))
        )
    else:
        response = ObjCInstance(response_ptr)
        toga.App.app.loop.call_soon_threadsafe(
            future.set_result, response
        )

def format_eta(mode: str, time: float, distance: float) -> None:
    # Initialize Formatters for elegant localise-aware outputs
    dist_formatter = b.MKDistanceFormatter.alloc().init()
    dist_formatter.unitsStyle = 1  # Abbreviated (e.g., "km", "m")

    time_formatter = b.NSDateComponentsFormatter.alloc().init()
    time_formatter.unitsStyle = 1  # Abbreviated (e.g., "hr", "min")
    time_formatter.allowedUnits = (1 << 5) | (1 << 6)  # Hour | Minute

    minutes = str(time_formatter.stringFromTimeInterval(time))
    metres = str(dist_formatter.stringFromDistance(distance))

    return f"By {mode} in {minutes} and {metres}"

async def perform_search_at(search_string: str, latitude: float, longitude: float) -> tuple[str, ObjCInstance | None]:
    """
    Executes an asynchronous MapKit local search around specified coordinates.

    :param search_string: Natural language query (e.g., 'Supermarket', 'Park').
    :type search_string: str
    :param latitude: Center latitude for search region in decimal degrees.
    :type latitude: float
    :param longitude: Center longitude for search region in decimal degrees.
    :type longitude: float
    """
    # 1. Set up the request
    request = b.MKLocalSearchRequest.alloc().init()
    request.naturalLanguageQuery = search_string

    request.region = b.MKCoordinateRegionMakeWithDistance(b.CLLocationCoordinate2DMake(latitude, longitude), 10000.0, 10000.0)

    # 2. Initialize the search and kick it off
    future = toga.App.app.loop.create_future()
    b.MKLocalSearch.alloc().initWithRequest(request).startWithCompletionHandler(
        Block(lambda r, e, f=future: generic_completion(r, e, f), None, objc_id, objc_id)
    )
    mapItems = list((await future).mapItems)
    if len(mapItems) == 0:
        return ("Search returned no results", None)
    print(f"Found {len(mapItems)} result(s), first is {mapItems[0].name}: {mapItems[0].addressRepresentations.fullAddressIncludingRegion(False, singleLine=True) if mapItems[0].addressRepresentations else "?"}")
    return (mapItems[0].name, mapItems[0])

async def perform_eta(fro: ObjCInstance | tuple[float, float], to: ObjCInstance, mode: str) -> tuple[str, ObjCInstance]:
    """
    Calculates estimated travel time and distance between two points using Apple MapKit directions.

    :param fro: Origin point as `(latitude, longitude)` tuple or native Objective-C `MKMapItem`.
    :type fro: tuple[float, float] | ObjCClass('MKMapItem')
    :param to: Destination point as native `MKMapItem`.
    :type to: ObjCClass('MKMapItem')
    :param mode: Transport mode emoji ('🥾' for walking, '🚲' for cycling, '🚌' for transit, '🚗' for driving).
    :type mode: str
    """
    # Start with a walking route
    mode_nums = {'🚲': 8, '🚌': 4, '🥾': 2, '🚗': 1}
    request = b.MKDirectionsRequest.alloc().init()
    if not isinstance(fro, ObjCClass('MKMapItem')):
        c = b.CLLocation.alloc().initWithLatitude(fro[0], longitude=fro[1])
        request.source = b.MKMapItem.alloc().initWithLocation(c, address=None)
    else:
        request.source = fro
    if not isinstance(to, ObjCClass('MKMapItem')):
        raise ValueError(to)
    request.destination = to
    request.transportType = mode_nums[mode]  # 1 = Driving, 2 = Walking
    request.requestsAlternateRoutes = False

    # Call Apple servers asynchronously
    directions_calculator = b.MKDirections.alloc().initWithRequest(request)
    future = toga.App.app.loop.create_future()
    directions_calculator.calculateETAWithCompletionHandler(
        Block(lambda r, e, f=future: generic_completion(r, e, f), None, objc_id, objc_id)
    )
    response = await future

    return (format_eta(mode, response.expectedTravelTime, response.distance), response)
