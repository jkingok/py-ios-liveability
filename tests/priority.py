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
results = {}

def vet(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except Exception as e:
        toga.App.app.main_window.error_dialog("Script Exception", f"Error occurred: {str(e)}")
        raise e

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
                found_service = (mapItems[0].name, mapItems[0])

        waiter.set()

    # 3. Wrap it in a Rubicon Block
    # The first argument specifies the return type (None / void), 
    # and the list specifies the types of the incoming parameters (Objective-C objects)
    objc_block = Block(search_callback, None, objc_id, objc_id)

    # 4. Initialize the search and kick it off
    search = MKLocalSearch.alloc().initWithRequest(request)
    search.startWithCompletionHandler(objc_block)
    
# New priority-based algorithm:
# Performs less calculations
# Logic applies a maximum time limit
# First search for the walking ETA
# If it is within limit, stop
# Else calculate cycling ETA
# Else calculate driving ETA
# Defer calculating routes until requested for details

etas_waiting = 0
def perform_eta(mode):
    MKDirectionsRequest = ObjCClass('MKDirectionsRequest')
    MKDirections = ObjCClass('MKDirections')
    MKDistanceFormatter = ObjCClass('MKDistanceFormatter')
    NSDateComponentsFormatter = ObjCClass('NSDateComponentsFormatter')

    # Initialize Formatters for elegant localise-aware outputs
    dist_formatter = MKDistanceFormatter.alloc().init()
    dist_formatter.unitsStyle = 1 # Abbreviated (e.g., "km", "m")
    
    time_formatter = NSDateComponentsFormatter.alloc().init()
    time_formatter.unitsStyle = 1 # Abbreviated (e.g., "hr", "min")
    time_formatter.allowedUnits = (1 << 5) | (1 << 6) # Hour | Minute

    # Define our directions pairs: (Source, Destination, Label)
    global found_address
    global found_service
    
    # Start with a walking route
    request = MKDirectionsRequest.alloc().init()
    request.source = found_address[1]
    request.destination = found_service[1]
    request.transportType = mode # 1 = Driving, 2 = Walking
    request.requestsAlternateRoutes = False

    directions_calculator = MKDirections.alloc().initWithRequest(request)
        
    # Internal flags to manage the async network callback
    data_holder = {'done': False, 'eta': None, 'error': None}
        
    # Define the Objective-C completion block wrapper
    def completion_handler(response_id, error):
        if error:
            data_holder['error'] = ObjCInstance(error)
        elif response_id:
            response = ObjCInstance(response_id)
            global results
            results = {
                "distance": (int(response.distance / 1000), str(dist_formatter.stringFromDistance(response.distance))),
                "expected_time": (int(response.expectedTravelTime / 60), str(time_formatter.stringFromTimeInterval(response.expectedTravelTime)))
            }
        data_holder['done'] = True
        global etas_waiting
        etas_waiting -= 1
        if etas_waiting <= 0:
            waiter.set()

    # Call Apple servers asynchronously
    global etas_waiting
    etas_waiting = 1
    directions_calculator.calculateETAWithCompletionHandler(Block(lambda r, e: vet(completion_handler, r, e), None, objc_id, objc_id))

waiter.clear()
toga.App.app.loop.call_soon(lambda address=address: perform_map_search(address))
waiter.wait()
if found_address:
    service = input("Search service")

    waiter.clear()
    toga.App.app.loop.call_soon(lambda service=service: perform_map_search_near(service))
    waiter.wait()
    if found_service:
        waiter.clear()

        mode = "foot"
        toga.App.app.loop.call_soon(lambda:  vet(perform_eta, 2))
        waiter.wait()

        if results["expected_time"][0] >= 15:
            waiter.clear()

            mode = "car"
            toga.App.app.loop.call_soon(lambda: vet(perform_eta, 1))
            waiter.wait()

        print(f"From {found_address[0]} to {found_service[0]} is best by {mode} in {results["expected_time"][1]} and {results["distance"][1]}.")

print("Done.")
