from rubicon.objc import ObjCClass, ObjCInstance, Block
from rubicon.objc.runtime import objc_id
import threading
import toga

# Let's test the workflow of analysing an address
address = input("Search address")

# MapKit needs to be on the main thread
# However to keep our execution in the background going
waiter = threading.Event()

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
            print(f"Found {len(mapItems)} result(s):")

            # Loop through native search results
            for item in mapItems:
                print(f" - {item.name}: {item.placemark.title}")
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
print("Done.")
