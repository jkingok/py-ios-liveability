"""
Objective-C bridge interface for Apple CoreLocation, MapKit, and UIKit frameworks.

Uses Rubicon-ObjC to bind native iOS C-functions, Objective-C classes, and struct encodings
required for geocoding, spatial searches, travel directions, date formatting, and pasteboard access.
"""

import sys

if sys.platform == "ios":

    import ctypes
    from rubicon.objc import ObjCClass, ObjCInstance
    from rubicon.objc.runtime import load_library
    from rubicon.objc.types import ctype_for_encoding
    import toga as _

    _tl = sys.modules["toga_iOS.libs"]

    def constant(name):
        return ObjCInstance(ctypes.c_void_p.in_dll(ctypes.CDLL(None), name))

    #: C-struct representation for 2D geographic coordinates (`{CLLocationCoordinate2D=dd}`).
    CLLocationCoordinate2D = ctype_for_encoding(b"{CLLocationCoordinate2D=dd}")

    # Load the CoreLocation framework
    cl = load_library("CoreLocation")

    #: Objective-C proxy class for CoreLocation ``CLLocation``.
    CLLocation = ObjCClass("CLLocation")

    #: Native C function pointer to ``CLLocationCoordinate2DMake``.
    CLLocationCoordinate2DMake = cl.CLLocationCoordinate2DMake
    CLLocationCoordinate2DMake.argtypes = [ctypes.c_double, ctypes.c_double]
    CLLocationCoordinate2DMake.restype = CLLocationCoordinate2D

    # Load the MapKit framework
    mk = load_library("MapKit")

    #: C-struct representation for map coordinate regions (`{MKCoordinateRegion=...}`).
    # MKCoordinateRegion = ctype_for_encoding(
    #    b"{MKCoordinateRegion={CLLocationCoordinate2D=dd}{MKCoordinateSpan=dd}}"
    # )
    MKCoordinateRegion = _tl.MKCoordinateRegion

    #: Native C function pointer to ``MKCoordinateRegionMakeWithDistance``.
    MKCoordinateRegionMakeWithDistance = mk.MKCoordinateRegionMakeWithDistance
    MKCoordinateRegionMakeWithDistance.argtypes = [
        CLLocationCoordinate2D,
        ctypes.c_double,
        ctypes.c_double,
    ]
    MKCoordinateRegionMakeWithDistance.restype = MKCoordinateRegion

    #: Objective-C proxy class for MapKit ``MKDirections``.
    MKDirections = ObjCClass("MKDirections")

    #: Objective-C proxy class for MapKit ``MKDirectionsRequest``.
    MKDirectionsRequest = ObjCClass("MKDirectionsRequest")

    #: Objective-C proxy class for MapKit ``MKDistanceFormatter``.
    MKDistanceFormatter = ObjCClass("MKDistanceFormatter")

    #: Objective-C proxy class for MapKit ``MKGeocodingRequest``.
    MKGeocodingRequest = ObjCClass("MKGeocodingRequest")

    #: Objective-C proxy class for MapKit ``MKLocalSearchRequest``.
    MKLocalSearchRequest = ObjCClass("MKLocalSearchRequest")

    #: Objective-C proxy class for MapKit ``MKLocalSearch``.
    MKLocalSearch = ObjCClass("MKLocalSearch")

    #: Objective-C proxy class for MapKit ``MKMapItem``.
    MKMapItem = ObjCClass("MKMapItem")

    #: Objective-C proxy class for MapKit ``MKMapView``.
    MKMapView = ObjCClass("MKMapView")

    #: Objective-C proxy class for MapKit ``MKPolyline``.
    MKPolyline = ObjCClass("MKPolyline")

    #: Objective-C proxy class for MapKit ``MKPolylineRenderer``.
    MKPolylineRenderer = ObjCClass("MKPolylineRenderer")

    #: Objective-C proxy class for MapKit ``MKReverseGeocodingRequest``.
    MKReverseGeocodingRequest = ObjCClass("MKReverseGeocodingRequest")

    #: Objective-C proxy class for Foundation ``NSDateComponentsFormatter``.
    NSDateComponentsFormatter = ObjCClass("NSDateComponentsFormatter")

    #: Objective-C proxy class for UIKit ``UIColor``.
    UIColor = ObjCClass("UIColor")

    #: Objective-C proxy class for UIKit ``UIPasteboard``.
    UIPasteboard = ObjCClass("UIPasteboard")
