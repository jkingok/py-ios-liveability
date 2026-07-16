import toga
from toga.style import Pack
from toga.style.pack import COLUMN, ROW, BOLD, CENTER

class MainPropertySelectionView:
    def __init__(self, app_controller):
        self.app = app_controller
        self.box = toga.Box(style=Pack(direction=COLUMN, padding=12, background_color="#f7f9fa"))
        self.build_ui()

    def build_ui(self):
        # Top Heading
        header = toga.Box(style=Pack(direction=COLUMN, padding_bottom=15))
        header.add(toga.Label("🏢 Assessed Target Portfolio", style=Pack(font_weight=BOLD, font_size=16)))
        self.box.add(header)
        
        # Simulated Local Portfolio Dataset
        mock_portfolio = [
            {"address": "100 Harris St, Pyrmont NSW", "score": "88/100", "desc": "Commercial Hub - Excellent Pedestrian Network"},
            {"address": "456 George St, Sydney NSW", "score": "94/100", "desc": "CBD Core - Supreme Transit Density"},
            {"address": "12 Ocean Ave, Bondi NSW", "score": "62/100", "desc": "Coastal Fringe - Poor Transit Connectivity"}
        ]
        
        for prop in mock_portfolio:
            card = toga.Box(style=Pack(direction=ROW, padding=10, background_color="#ffffff", alignment=CENTER))
            
            info_block = toga.Box(style=Pack(direction=COLUMN, flex=1))
            info_block.add(toga.Label(prop["address"], style=Pack(font_weight=BOLD, font_size=11)))
            info_block.add(toga.Label(prop["desc"], style=Pack(font_size=9, color="#707a8a", padding_top=2)))
            
            score_lbl = toga.Label(prop["score"], style=Pack(font_weight=BOLD, font_size=12, color="#2ec4b6", padding_right=10))
            
            # Action button to drill down into the details view
            inspect_btn = toga.Button(
                "Inspect", 
                on_press=lambda w, addr=prop["address"]: self.app.show_location_detail(addr),
                style=Pack(width=70)
            )
            
            card.add(info_block)
            card.add(score_lbl)
            card.add(inspect_btn)
            self.box.add(card)
            self.box.add(toga.Box(style=Pack(height=4)))
