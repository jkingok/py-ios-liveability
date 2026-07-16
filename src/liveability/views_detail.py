import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, BOLD, CENTER

class LocationDetailView:
    def __init__(self, app_controller, property_name):
        self.app = app_controller
        self.property_name = property_name
        self.box = toga.Box(style=Pack(direction=COLUMN, padding=12, background_color="#f7f9fa"))
        self.build_ui()

    def build_ui(self):
        # Navigation Header
        nav_box = toga.Box(style=Pack(direction=ROW, padding_bottom=10, alignment=CENTER))
        back_btn = toga.Button("◀ Portfolio", on_press=lambda w: self.app.show_property_selection(), style=Pack(width=90))
        nav_box.add(back_btn)
        self.box.add(nav_box)

        # Main Property Meta
        header_box = toga.Box(style=Pack(direction=COLUMN, padding_bottom=12))
        header_box.add(toga.Label("📍 Proximity Analysis", style=Pack(font_weight=BOLD, font_size=14)))
        header_box.add(toga.Label(self.property_name, style=Pack(font_size=10, color="#707a8a")))
        self.box.add(header_box)

        # Prepopulated Cached Amenities Matrix
        mock_amenities = [
            {"name": "Aldi Supermarket", "category": "Grocery", "distance": "320m", "time": "4 min", "score": "Excellent", "color": "#2ec4b6"},
            {"name": "Pyrmont Point Park", "category": "Park/Recreation", "distance": "650m", "time": "8 min", "score": "Excellent", "color": "#2ec4b6"},
            {"name": "Quarry St Café", "category": "Dining", "distance": "180m", "time": "2 min", "score": "Excellent", "color": "#2ec4b6"}
        ]

        for item in mock_amenities:
            row_box = toga.Box(style=Pack(direction=ROW, padding=6, background_color="#ffffff", alignment=CENTER))
            
            text_block = toga.Box(style=Pack(direction=COLUMN, flex=1))
            text_block.add(toga.Label(item["name"], style=Pack(font_weight=BOLD, font_size=10)))
            text_block.add(toga.Label(item["category"], style=Pack(font_size=8, color="#707a8a")))
            
            metric_block = toga.Box(style=Pack(direction=ROW, width=100))
            metric_block.add(toga.Label(f"⏱ {item['time']}", style=Pack(font_size=9, padding_right=4)))
            metric_block.add(toga.Label(f"📏 {item['distance']}", style=Pack(font_size=9)))
            
            # Interactivity: Button triggers the dedicated routing inspector view
            route_btn = toga.Button(
                "Route", 
                on_press=lambda w, i=item: self.app.show_route_inspection(self.property_name, i),
                style=Pack(width=60)
            )
            
            row_box.add(text_block)
            row_box.add(metric_block)
            row_box.add(route_btn)
            self.box.add(row_box)
            self.box.add(toga.Box(style=Pack(height=2)))
