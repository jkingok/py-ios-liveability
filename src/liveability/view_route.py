import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, BOLD, CENTER

class RouteInspectionView:
    def __init__(self, app_controller, property_name, amenity_item):
        self.app = app_controller
        self.property_name = property_name
        self.amenity = amenity_item
        self.box = toga.Box(style=Pack(direction=COLUMN, padding=12, background_color="#f7f9fa"))
        self.build_ui()

    def build_ui(self):
        # Back Nav Block
        nav_box = toga.Box(style=Pack(direction=ROW, padding_bottom=10))
        back_btn = toga.Button(
            "◀ Matrix", 
            on_press=lambda w: self.app.show_location_detail(self.property_name), 
            style=Pack(width=80)
        )
        nav_box.add(back_btn)
        self.box.add(nav_box)

        # Inspection Details Title Card
        title_card = toga.Box(style=Pack(direction=COLUMN, padding=10, background_color="#ffffff"))
        title_card.add(toga.Label(f"🗺 Trace: {self.amenity['name']}", style=Pack(font_weight=BOLD, font_size=13)))
        title_card.add(toga.Label(f"Origin: {self.property_name}", style=Pack(font_size=9, color="#707a8a", padding_top=4)))
        self.box.add(title_card)
        self.box.add(toga.Box(style=Pack(height=10)))

        # Visual Simulator Vector Canvas Frame
        # In production, this container box receives the compiled MapKit subviews
        map_placeholder = toga.Box(style=Pack(direction=COLUMN, padding=20, background_color="#e2e8f0", height=200, alignment=CENTER))
        map_placeholder.add(toga.Label("🗺 [ MapKit Render Canvas Placeholder ]", style=Pack(font_weight=BOLD, color="#4a5568")))
        map_placeholder.add(toga.Label(" Solid Green Outbound Trace Line Active", style=Pack(font_size=9, color="#2ec4b6", padding_top=6)))
        map_placeholder.add(toga.Label("--- Faded Dashed Inbound Return Trace Active", style=Pack(font_size=9, color="#707a8a")))
        self.box.add(map_placeholder)
        self.box.add(toga.Box(style=Pack(height=10)))

        # Action Footers
        info_lbl = toga.Label(
            f"Calculated walking travel envelope bounds: {self.amenity['time']} across {self.amenity['distance']}.",
            style=Pack(font_size=10, text_align="center", color="#011627")
        )
        self.box.add(info_lbl)
