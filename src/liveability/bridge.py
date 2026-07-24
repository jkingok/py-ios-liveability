import ctypes
from rubicon.objc import ObjCClass, ObjCInstance, Block
from rubicon.objc.runtime import load_library, objc_id
from rubicon.objc.types import ctype_for_encoding

# Force Rubicon to parse and register the encoding into its cache
CLLocationCoordinate2D = ctype_for_encoding(b'{CLLocationCoordinate2D=dd}')

# Load the CoreLocation framework
cl = load_library('CoreLocation')

CLLocation = ObjCClass('CLLocation')

CLLocationCoordinate2DMake = cl.CLLocationCoordinate2DMake
CLLocationCoordinate2DMake.argtypes = [ ctypes.c_double, ctypes.c_double ]
CLLocationCoordinate2DMake.restype = CLLocationCoordinate2D

# Load the MapKit framework
# On macOS/iOS, MapKit is located within the /System/Library/Frameworks directory
#mk = load_library('/System/Library/Frameworks/MapKit.framework/MapKit')
mk = load_library('MapKit')

MKCoordinateRegion = ctype_for_encoding(b'{MKCoordinateRegion={CLLocationCoordinate2D=dd}{MKCoordinateSpan=dd}}')

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

MKGeocodingRequest = ObjCClass('MKGeocodingRequest')

MKMapItem = ObjCClass('MKMapItem')

MKReverseGeocodingRequest = ObjCClass('MKReverseGeocodingRequest')

UIPasteboard = ObjCClass('UIPasteboard')