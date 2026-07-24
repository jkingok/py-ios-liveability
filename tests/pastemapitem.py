import asyncio
import requests
from rubicon.objc import ObjCClass, ObjCInstance
from rubicon.objc.runtime import load_library, objc_id
import threading
import toga
import urllib

done = threading.Event()

cl = load_library('CoreLocation')
mk = load_library('MapKit')

CLLocation = ObjCClass('CLLocation')
MKGeocodingRequest = ObjCClass('MKGeocodingRequest')
MKMapItem = ObjCClass('MKMapItem')
MKReverseGeocodingRequest = ObjCClass('MKReverseGeocodingRequest')
UIPasteboard = ObjCClass('UIPasteboard')

def add_address(url=None):
    def record_item(mi):
        print(str(i.identifierString if (i := mi.identifier) else mi.name), {"title": str(mi.name), "subtitle": str(mi.addressRepresentations.fullAddressIncludingRegion(False, singleLine=True)), "latitude": mi.location.coordinate.latitude, "longitude": mi.location.coordinate.longitude})

    def geocoded(r: objc_id, e: objc_id) -> None:
        if e:
            asyncio.create_task(toga.App.app.main_window.dialog(toga.ErrorDialog("Search Failure", ObjCInstance(e).localizedDescription)))
        else:
            l = list(ObjCInstance(r))
            if len(l) == 1:
                record_item(l[0])
            else:
                asyncio.create_task(toga.App.app.main_window.dialog(toga.ErrorDialog("Search Failure","Could not determine address")))
                record_item(MKMapItem.alloc().initWithLocation(loc))
            #global done
            done.set()

    if not url:
        print("nothing to search yet")
        if (pb := UIPasteboard.generalPasteboard).hasURLs and pb.URL and (u := pb.URL.absoluteString):
            print("got url")
            return add_address(str(u))
        elif pb.hasStrings and (s := pb.string):
            print("got str")
            return add_address(str(s))
        else:
            input("Search for an address")
            global done
            done.set()
            return None 
    elif url.startswith("http"):
        print(url)
        pu = urllib.parse.urlparse(url)
        if pu.netloc in ['maps.apple', 'maps.app.goo.gl']:
            # Needs expanding
            try:
                # Should be async
                response = requests.get(url, allow_redirects=True)
                return add_address(response.url)
            except Exception as e:
                print(f"Error resolving short URL: {e}")
                #global done
                done.set()
                return None
        elif pu.netloc == 'maps.apple.com':
            p = urllib.parse.parse_qs(pu.query)
            loc = CLLocation.alloc().initWithLatitude(float((ll := p['coordinate'][0].split(','))[0]), longitude=float(ll[1]))
            rgr = MKReverseGeocodingRequest.alloc().initWithLocation(loc)
            rgr.getMapItemsWithCompletionHandler(geocoded)
        else:
            asyncio.create_task(toga.App.app.main_window.dialog(toga.ErrorDialog("Search Failure", "Cannot extract location from URL"))) 
            #global done
            done.set()
    else:
        gr = MKGeocodingRequest.alloc().initWithAddressString(url)
        gr.getMapItemsWithCompletionHandler(geocoded)

toga.App.app.loop.call_soon(lambda: add_address())
done.wait()