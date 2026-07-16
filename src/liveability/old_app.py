import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, BOLD, CENTER

class LiveabilityIndexApp(toga.App):
    def startup(self):
        self.main_window = toga.MainWindow(title="Liveability Hub")
        self.target_address = "100 Harris St, Pyrmont NSW"
        
        # 1. Fixed Master App Frame Layout
        self.master_box = toga.Box(style=Pack(direction=COLUMN, padding=12, background_color="#f7f9fa"))
        
        # Fixed Segmented Top Bar
        nav_bar = toga.Box(style=Pack(direction=ROW, padding_bottom=15, alignment=CENTER))
        nav_bar.add(toga.Button("🏢 Portfolio", on_press=self.show_portfolio, style=Pack(flex=1, padding=2)))
        nav_bar.add(toga.Button("📍 Matrix", on_press=self.show_matrix, style=Pack(flex=1, padding=2)))
        nav_bar.add(toga.Button("🗺 Route", on_press=self.show_route, style=Pack(flex=1, padding=2)))
        #self.master_box.add(nav_bar)

        # 2. Dynamic Component Pane
        self.content_pane = toga.Box(style=Pack(direction=COLUMN))
        self.master_box.add(self.content_pane)

        # Draw the first tab on startup
        self.show_portfolio(None)

        self.main_window.content = self.master_box
        self.main_window.show()

    def safe_clear_pane(self):
        """Safely purges native iOS layout elements backward without crashing Pyto."""
        if hasattr(self.content_pane, 'children') and self.content_pane.children:
            for child in list(self.content_pane.children):
                self.content_pane.remove(child)

    # --- TAB RENDERING ENGINES ---

    def show_portfolio(self, widget):
        self.safe_clear_pane()
        
        self.content_pane.add(toga.Label("🏢 Assessed Target Portfolio", style=Pack(font_weight=BOLD, font_size=14, padding_bottom=10)))
        
        # Rich Property Card Layout Block
        card_row = toga.Box(style=Pack(direction=ROW, padding=10, background_color="#ffffff", alignment=CENTER))
        
        text_block = toga.Box(style=Pack(direction=COLUMN, flex=1))
        text_block.add(toga.Label(self.target_address, style=Pack(font_weight=BOLD, font_size=11)))
        text_block.add(toga.Label("Score: 88/100 · Commercial Core Network", style=Pack(font_size=9, color="#707a8a", padding_top=2)))
        
        # Clean Action Arrow Target Button
        action_btn = toga.Button("Inspect ▶", on_press=self.show_matrix, style=Pack(width=80))
        
        card_row.add(text_block)
        card_row.add(action_btn)
        self.content_pane.add(card_row)

    def show_matrix(self, widget):
        #self.safe_clear_pane()
        
        self.content_pane.add(toga.Label("📍 15-Minute Proximity Matrix", style=Pack(font_weight=BOLD, font_size=14, padding_bottom=10)))
        
        mock_amenities = [
            {"name": "Aldi Supermarket", "category": "Grocery", "time": "4 min", "dist": "320m"},
            {"name": "Pyrmont Point Park", "category": "Park/Rec", "time": "8 min", "dist": "650m"},
            {"name": "Quarry St Café", "category": "Dining", "time": "2 min", "dist": "180m"}
        ]
        
        for item in mock_amenities:
            # RESTORED: High-Density Layout Box Container Row
            r_box = toga.Box(style=Pack(direction=ROW, padding=6, background_color="#ffffff", alignment=CENTER))
            
            # Left Info Stack
            txt = toga.Box(style=Pack(direction=COLUMN, flex=1))
            txt.add(toga.Label(item["name"], style=Pack(font_weight=BOLD, font_size=10)))
            txt.add(toga.Label(item["category"], style=Pack(font_size=8, color="#707a8a")))
            
            # Middle Metrics Stack
            metrics = toga.Box(style=Pack(direction=ROW, width=100, alignment=CENTER))
            metrics.add(toga.Label(f"⏱ {item['time']}", style=Pack(font_size=9, padding_right=4)))
            metrics.add(toga.Label(f"📏 {item['dist']}", style=Pack(font_size=9)))
            
            # Right Clean Interaction Target Button
            view_btn = toga.Button("Map ▶", on_press=self.show_route, style=Pack(width=60))
            
            r_box.add(txt)
            r_box.add(metrics)
            r_box.add(view_btn)
            
            self.content_pane.add(r_box)
            self.content_pane.add(toga.Box(style=Pack(height=4)))

    def show_route(self, widget):
        self.safe_clear_pane()
        
        self.content_pane.add(toga.Label("🗺 Active Route Trace Visualizer", style=Pack(font_weight=BOLD, font_size=14, padding_bottom=10)))
        
        # Dedicated Visual Canvas Display Frame
        map_canvas = toga.Box(style=Pack(direction=COLUMN, padding=20, background_color="#e2e8f0", height=160, alignment=CENTER))
        map_canvas.add(toga.Label("[ CoreGraphics Vector Layer Frame ]", style=Pack(font_weight=BOLD, color="#4a5568", font_size=11)))
        map_canvas.add(toga.Label("Solid green outbound / Dashed gray return", style=Pack(font_size=8, color="#707a8a", padding_top=4)))
        self.content_pane.add(map_canvas)

def main():
    return LiveabilityIndexApp("com.urbanmetrics.liveability", "Liveability App")
