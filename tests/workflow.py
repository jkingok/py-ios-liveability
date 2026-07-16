from rubicon.objc import ObjCClass, ObjCInstance, Block
from rubicon.objc.runtime import load_library, objc_id
import threading
import toga

import ctypes
from rubicon.objc import ObjCClass, load_library

# Define the coordinate structure
class CLLocationCoordinate2D(ctypes.Structure):
    _fields_ = [
        ("latitude", ctypes.c_double),
        ("longitude", ctypes.c_double)
    ]

# Define the coordinate span structure
class MKCoordinateSpan(ctypes.Structure):
    _fields_ = [
        ("latitudeDelta", ctypes.c_double),
        ("longitudeDelta", ctypes.c_double)
    ]

# Define the coordinate region structure
class MKCoordinateRegion(ctypes.Structure):
    _fields_ = [
        ("center", CLLocationCoordinate2D),
        ("span", MKCoordinateSpan)
    ]

# Load the MapKit framework
# On macOS, MapKit is located within the /System/Library/Frameworks directory
mk = load_library('/System/Library/Frameworks/MapKit.framework/MapKit')

# Locate the function
MKCoordinateRegionMakeWithDistance = mk.MKCoordinateRegionMakeWithDistance

# Define argument types: CLLocationCoordinate2D, double (lat meters), double (long meters)
MKCoordinateRegionMakeWithDistance.argtypes = [
    CLLocationCoordinate2D, 
    ctypes.c_double, 
    ctypes.c_double
]

# Define the return type (the struct we defined above)
MKCoordinateRegionMakeWithDistance.restype = MKCoordinateRegion

# Let's test the workflow of analysing an address
address = input("Search address")

# MapKit needs to be on the main thread
# However to keep our execution in the background going
waiter = threading.Event()

found_address = None
found_service = None

def perform_map_search(search_string):
    # Load the native MapKit classes
    MKLocalSearchRequest = ObjCClass('MKLocalSearchRequest')
    MKLocalSearch = ObjCClass('MKLocalSearch')

    # 1. Set up the request
    request = MKLocalSearchRequest.alloc().init()
    request.naturalLanguageQuery = search_string

    # Optional: You can bound it to Australia or a specific region if you have coordinates
    # request.region = ... 

    # 2. Define the target callback function
    def search_callback(response_ptr: objc_id, error_ptr: objc_id) -> None:
        if error_ptr:
            error = ObjCInstance(error_ptr)
            print(f"Search failed: {error.localizedDescription}")
        else:
            response = ObjCInstance(response_ptr)
            mapItems = list(response.mapItems)
            if len(mapItems) > 0:
                print(f"Found {len(mapItems)} result(s):")

                # Loop through native search results
                for item in mapItems:
                    print(f" - {item.name}: {item.addressRepresentations.fullAddressIncludingRegion(False, singleLine=True)} @ {item.location.coordinate}")
                found_address = (mapItems[0].name, mapItems[0])

        waiter.set()

    # 3. Wrap it in a Rubicon Block
    # The first argument specifies the return type (None / void), 
    # and the list specifies the types of the incoming parameters (Objective-C objects)
    objc_block = Block(search_callback, None, objc_id, objc_id)

    # 4. Initialize the search and kick it off
    search = MKLocalSearch.alloc().initWithRequest(request)
    search.startWithCompletionHandler(objc_block)

def perform_map_search_near(search_string):
    # Load the native MapKit classes
    MKLocalSearchRequest = ObjCClass('MKLocalSearchRequest')
    MKLocalSearch = ObjCClass('MKLocalSearch')

    # 1. Set up the request
    request = MKLocalSearchRequest.alloc().init()
    request.naturalLanguageQuery = search_string

    # Optional: You c	an bound it to Australia or a specific region if you have coordinates
    if found_address:
        request.region = MKCoordinateRegionMakeWithDistance(found_address[1].location.coordinate, 10000.0, 10000.0)

    # 2. Define the target callback function
    def search_callback(response_ptr: objc_id, error_ptr: objc_id) -> None:
        if error_ptr:
            error = ObjCInstance(error_ptr)
            print(f"Search failed: {error.localizedDescription}")
        else:
            response = ObjCInstance(response_ptr)
            mapItems = list(response.mapItems)
            if len(mapItems) > 0:
                print(f"Found {len(mapItems)} result(s):")

                # Loop through native search results
                for item in mapItems:
                    print(f" - {item.name}: {item.addressRepresentations.fullAddressIncludingRegion(False, singleLine=True)}")
                found_service = (item.name, item)

        waiter.set()

    # 3. Wrap it in a Rubicon Block
    # The first argument specifies the return type (None / void), 
    # and the list specifies the types of the incoming parameters (Objective-C objects)
    objc_block = Block(search_callback, None, objc_id, objc_id)

    # 4. Initialize the search and kick it off
    search = MKLocalSearch.alloc().initWithRequest(request)
    search.startWithCompletionHandler(objc_block)



waiter.clear()
toga.App.app.loop.call_soon(lambda address=address: perform_map_search(address))
waiter.wait()
if found_address:
	service = input("Search service")

	waiter.clear()
	toga.App.app.loop.call_soon(lambda service=service: perform_map_search_near(service))
	waiter.wait()

print("Done.")
