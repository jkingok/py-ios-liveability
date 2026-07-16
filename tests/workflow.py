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

directions_waiting = 0 

def perform_route():
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
    directions = [
        (found_address[1], found_service[1], 1, "Outbound by Car"),
        (found_service[1], found_address[1], 1, "Inbound by Car"),
        (found_address[1], found_service[1], 2, "Outbound on Foot"),
        (found_service[1], found_address[1], 2, "Inbound on Foot")
    ]
    global directions_waiting
    directions_waiting = len(directions)
    
    for source, dest, mode, direction_label in directions:
        request = MKDirectionsRequest.alloc().init()
        request.source = source
        request.destination = dest
        request.transportType = mode # 1 = Driving, 2 = Walking
        request.requestsAlternateRoutes = False

        directions_calculator = MKDirections.alloc().initWithRequest(request)
        
        # Internal flags to manage the async network callback
        data_holder = {'done': False, 'route': None, 'error': None}
        
        # Define the Objective-C completion block wrapper
        def completion_handler(name, response, error):
            if error:
                data_holder['error'] = ObjCInstance(error)
            elif response and len(rs := list(ObjCInstance(response).routes)) > 0:
                data_holder['route'] = (r := rs[0])
                global results
                results[name] = {
                    "distance": str(dist_formatter.stringFromDistance(r.distance)),
                    "expected_time": str(time_formatter.stringFromTimeInterval(r.expectedTravelTime))
                }
            data_holder['done'] = True
            global directions_waiting
            directions_waiting -= 1
            if directions_waiting == 0:
                waiter.set()

        # Call Apple servers asynchronously
        directions_calculator.calculateDirectionsWithCompletionHandler(Block(lambda r, e, n=direction_label: completion_handler(n, r, e), None, objc_id, objc_id))

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
		toga.App.app.loop.call_soon(perform_route)
		waiter.wait()

		for k, v in results.items():
			print(f"{k}: {v["distance"]}, {v["expected_time"]}")
print("Done.")
