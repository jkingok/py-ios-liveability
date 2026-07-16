import ctypes
from rubicon.objc import ObjCClass, ObjCInstance, Block
from rubicon.objc.runtime import load_library, objc_id
from rubicon.objc.types import ctype_for_encoding
import threading
import toga

# Force Rubicon to parse and register the encoding into its cache
CLLocationCoordinate2D = ctype_for_encoding(b'{CLLocationCoordinate2D=dd}')
MKCoordinateRegion = ctype_for_encoding(b'{MKCoordinateRegion={CLLocationCoordinate2D=dd}{MKCoordinateSpan=dd}}')

# Load the MapKit framework
# On macOS/iOS, MapKit is located within the /System/Library/Frameworks directory
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
                global found_address
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

    # Optional: You can bound it to Australia or a specific region if you have coordinates
    global found_address
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
                global found_service
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
