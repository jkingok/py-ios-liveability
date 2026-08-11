# Place Compare

This app helps you compare locations with respect to the availability of common services and the means of transport required to access them in a reasonable time.

This is a measure of the _liveability_ of various locations.

This can be used to:
- compare places to live in (share/rent/buy)
- compare places to work or study

We start on the **List** tab.

## List

This tab is the main view of the app. You will start with an empty list and map.

Tap **Add** to add an address. You will be prompted to enter an address (search term) or to tap **Paste** to accept a location from another app.

_Note that the support for pasting addresses is very limited._ **Apple Maps** via the "Share" button then "Copy" works (Internet connection required),
but **Google Maps** does not (this is an intentional decision of Google). It _may_ work if you use the "Plus Code" copy function of **Google Maps**.

Once an address is added it will appear in the list and the map with a pin.

Tapping an address in the list or map will open up the details view for that address.

First though you will need to set up some _Services_ on the **Setup** tab.

## Setup

This tab sets up the app for the _Services_ that it will assess each location against.

A list of generic search terms and symbols _(for the map, not implemented yet)_ is shown, along with an **Add** button.

Upon tapping the **Add** button a prompt is displayed to enter the search term (as will be searched in **Apple Maps**) and the symbol.

You can swipe on an _Service_ to **Delete** it, or tap it to edit it _(currently broken)_.

Upon changing either list, the missing searches are performed (new services or addresses).

## Details

Upon tapping an entry in the **List** tab you enter the **Address Details**. This shows the details and the distances and times and method of transport to the first match
for each service from the address.

You _may_ need to zoom out the map to find the service. Tapping on a service in the list will centre it in the map.

Swiping on the service in the list exposes the option to show the directions in **Apple Maps**. 

Tap **Back** to go back to the **List** view.

## Help

The **Help** tab shows this information.
