from markdown import markdown as md
from pathlib import Path
import requests
from rubicon.objc import ObjCClass
import toga
import urllib

from . import data as d
from . import functions as f
from . import model as m
from . import settings as s
from . import widgets as ws

UIPasteboard = ObjCClass('UIPasteboard')

class Prototype:
    def __init__(self, host_app, on_done):
        self.app = host_app
        self.on_done_callback = on_done  # This is your ticket back to safety
        self.title = "Liveability" # host_app.formal_name
        self.app.settings = s.Settings(host_app.paths)
        self.app.functions = f.Functions(host_app.paths, self.app.settings)
        self.app.addresses = m.AddressModel(host_app.paths, self.app.functions)
        self.data_path = self.app.paths.data
        self.this_path = Path(__file__).resolve().parent
        self.icon_path = self.this_path / "resources" / "icons"
        self.template_path = self.this_path / "resources" / "templates"	

    async def todo(self, name):
        await self.app.main_window.dialog(toga.InfoDialog("TODO", name))
        
    def add_address(self, url=None):
        if not url:
            if (pb := UIPasteboard.generalPasteboard).hasURLs:
                return self.add_address(str(pb.URL.absoluteString))
        else:
            print(url)
            pu = urllib.parse.urlparse(url)
            if pu.netloc == 'maps.apple':
                # Needs expanding
                try:
                    # Should be async
                    response = requests.get(url, allow_redirects=True)
                    return self.add_address(response.url)
                except Exception as e:
                    print(f"Error resolving short URL: {e}")
            elif pu.netloc == 'maps.apple.com':
                p = urllib.parse.parse_qs(pu.query)
                self.app.addresses.save(p['name'][0], {"title": p['name'][0], "subtitle": p['coordinate'][0]})
 
    def get_content(self):
        class EditAddressBox(toga.Box):
            def __init__(self, stack=None, key=None, values=None):
                self.key = key or dt.datetime.now().isoformat()
                self.values = values or d.Address()
                super().__init__(
                    direction="column",
                    children=[
                        ws.LabelledText(
                            "Key",
                            #id="edit_key",
                            value_text=self.key,
                            readonly=True
                        ),
                        toga.Divider(),
                        ws.LabelledText(
                            "Title",
                            #id="edit_title"
                            value_text=self.values.title,
                            callback=lambda w: {
                                self.set_value("title", w.value)
                            }
                        ),
                        ws.LabelledText(
                            "Subtitle",
                            #id="edit_subtitle"
                            value_text=self.values.subtitle,
                            callback=lambda w: {
                                self.set_value("subtitle", w.value)
                            } 
                        ),
                        toga.Box(
                            flex=1
                        ), 
                        toga.Row(
                            children=[
                                toga.Button(
                                    "Back",
                                    flex=1,
                                    on_press=lambda w: {
                                        self.app.widgets[self.stack].pop()
                                    } 
                                ),
                                toga.Button(
                                    "Save",
                                    flex=1,
                                    on_press=lambda w: (
                                        self.app.addresses.save(self.key, self.values),
                                        self.app.widgets[self.stack].pop()
                                    )
                                )
                            ]
                        )  
                    ],
                    flex=1
                )
                self.stack = stack
                
            def set_value(self, k, v):
                setattr(self.values, k, v)

        return toga.OptionContainer(
            content=[
                ("List", ws.StackContainer(
                    id="stack_list",
                    direction="column",
                    children = [
                        toga.Row(
                            children=[
                                self.app.addresses.set_list_count_label(toga.Label("", flex=1)),
                                toga.Button(
                                    "Add",
                                    on_press=lambda _: self.add_address()
                                )
                            ]
                        ),   
                        toga.DetailedList(
                            flex=1,
                            on_refresh=lambda w: {
                                self.app.addresses.reload_items()
                            },
                            primary_action="View",
                            on_primary_action=lambda w, row: asyncio.create_task(self.todo("View")),
                            secondary_action="Delete",
                            on_secondary_action=lambda w, row: self.app.addresses.delete(row.index),
                            on_select=lambda w: {
                                self.app.widgets["stack_list"].push(EditAddressBox("stack_list", i := w.selection.index, self.app.addresses.get(i)))
                            },
                            data=self.app.addresses.items_list_source
                        ) 
                    ]), self.icon_path / "list.png"),
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
