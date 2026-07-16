from markdown import markdown as md
from pathlib import Path
import toga

from . import settings as s

class Prototype:
    def __init__(self, host_app, on_done):
        self.app = host_app
        self.on_done_callback = on_done  # This is your ticket back to safety
        self.title = "Liveability" # host_app.formal_name
        self.app.settings = s.Settings(host_app.paths)
        self.data_path = self.app.paths.data
        self.this_path = Path(__file__).resolve().parent
        self.icon_path = self.this_path / "resources" / "icons"
        self.template_path = self.this_path / "resources" / "templates"	

    async def todo(self, name):
        await self.app.main_window.dialog(toga.InfoDialog("TODO", name))
        
    def get_content(self):
        return toga.OptionContainer(
            content=[
                ("App", toga.Label("The app goes here...")),
                ("Setup", toga.Column(
                    children=[
                        toga.Button(
                            "Exit",
                            visibility="visible" if hasattr(self.app.main_window, "content_stack") and len(self.app.main_window.content_stack) > 0 else "hidden",
                        on_press=self.on_done_callback
                        )
                    ]), self.icon_path / "settings-sliders.png"),
                ("Help", toga.Row(
                     children=[
                         toga.WebView(
                             content=f"""
        <html>
        <head>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; line-height: 1.6; padding: 20px; color: #333; }}
                code {{ background-color: #f6f8fa; padding: 2px 4px; border-radius: 3px; font-family: monospace; }}
                pre {{ background-color: #f6f8fa; padding: 16px; overflow: auto; border-radius: 6px; }}
                img {{ max-width: 100%; height: auto; }}
            </style>
        </head>
        <body>
                     {md(f.read_text() if (f := (self.template_path / "help.md")).exists() else "")}
        </body>
        </html>
""",
                             flex=1)]), self.icon_path / "interrogation.png")
            ],
        )
