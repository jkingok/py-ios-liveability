import asyncio
from pathlib import Path
import toga

class LabelledDate(toga.Box):
    def __init__(self, label_text, value_text=None, callback=None, id=None):
        super().__init__(
            direction="row",
            align_items="center",
            children=[
                toga.Label(
                    label_text + ": "
                ),
                toga.DateInput(
                    id=id,
                    value=value_text,
                    flex=1,
                    on_change=callback
                )
            ]
        )

class LabelledNumber(toga.Box):
    def __init__(self, label_text, value_num=0, callback=None, readonly=False, id=None):
        super().__init__(
            direction="row",
            align_items="center",
            children=[
                toga.Label(
                    label_text + ": "
                ),
                toga.NumberInput(
                    id=id,
                    value=value_num,
                    flex=1,
                    on_change=callback,
                    readonly=readonly
                )
            ]
        )

class LabelledSelection(toga.Box):
    def __init__(self, label_text, value_text="", value_list=[], callback=None, id=None):
        super().__init__(
            direction="row",
            align_items="center",
            children=[
                toga.Label(
                    label_text + ": "
                ),
                toga.Selection(
                    id=id,
                    items=value_list,
                    value=value_text,
                    flex=1,
                    on_change=callback
                )
            ]
        )

class LabelledText(toga.Box):
    def __init__(self, label_text, value_text="", callback=None, confirm=None, readonly=False, multiline=False, id=None, **kwargs):
        super().__init__(
            direction="column" if multiline else "row",
            align_items="start" if multiline else "center",
            children=[
                toga.Label(
                    label_text + ": "
                ),
                toga.MultilineTextInput(
                    id=id,
                    value=value_text,
                    flex=1,
                    on_change=callback,
                    readonly=readonly
                ) if multiline else
                toga.TextInput(
                    id=id,
                    value=value_text,
                    flex=1,
                    on_change=callback,
                    on_confirm=confirm,
                    readonly=readonly
                )
            ],
            **kwargs     
        )

class StackContainer(toga.Box):
   def __init__(self, **kwargs):
      super().__init__(**kwargs)
      self.stack = []
   
   def push(self, new_children):
      self.stack.append(list(self.children))
      self.clear()
      self.add(new_children)

   def pop(self):
      if self.stack:
         new_children = self.stack.pop()
         self.clear()
         self.add(*new_children)

class GenericUtils:
    def info_task(w, title, text):
        asyncio.create_task(w.app.main_window.dialog(toga.InfoDialog(title, text)))

class PlatformUtils(GenericUtils):
    def close_keyboard(widget):
        pass

    def ask_for_input(w, title, message, actions, texts=0):
        pass
  
    def open_share_sheet(w, html_file_path):
        pass

if toga.platform.current_platform == 'iOS':
    from rubicon.objc import ObjCClass, ObjCInstance

    # Load the required Objective-C classes
    NSURL = ObjCClass('NSURL')
    NSMutableArray = ObjCClass('NSMutableArray')
    UIActivityViewController = ObjCClass('UIActivityViewController')
    UIAlertController = ObjCClass("UIAlertController")
    UIAlertAction = ObjCClass("UIAlertAction")
    
    class IOSUtils(PlatformUtils):
        def close_keyboard(widget):
            """Triggered when the user presses 'Return' or 'Done' on the iPad keyboard."""
            # Dismiss the keyboard by resigning First Responder status
            try:
                # Check if we are running on iOS/iPadOS via the native implementation handle
                if hasattr(widget, '_impl') and hasattr(widget._impl, 'native'):
                    native_textfield = widget._impl.native
            
                    # Fire the native UIKit selector to lower the keyboard
                    native_textfield.resignFirstResponder()
                    print("[UIKit] Keyboard dismissed via resignFirstResponder.")
            except Exception as e:
                # Graceful fallback for macOS/Windows desktop development runners
                print(f"[Platform Fallback] Could not reach native interface: {e}")

        def ask_for_input(w, title, message, actions=[], texts=0):
            # Preferred Styles: 0 = ActionSheet, 1 = Alert
            # Text fields not allowed in Sheets
            alert = UIAlertController.alertControllerWithTitle(
                title,
                message=message,
                preferredStyle=1
            )

            # Add text input field
            for i in range(texts):
                alert.addTextFieldWithConfigurationHandler_(None)

            # Define action handler
            handlers = { action[0]: action[1] for action in actions if len(action) > 1 and action[1] }
            def on_done(action_ptr: ObjCInstance) -> None:
                if (title := str(ObjCInstance(action_ptr).title)) in handlers:
                    outputs = [ str(tf.text) for tf in alert.textFields ] 
                    handlers[title](title, *outputs)

            for action in actions:
                alert.addAction(UIAlertAction.actionWithTitle(action[0], style=0, handler=on_done))

            # Present modally
            w.main_window._impl.native.rootViewController.presentViewController(alert, animated=True, completion=None)

        def open_share_sheet(w, html_file_path: str):
            """
            Opens the iOS native share sheet for a specific HTML file.
        
            :param w: The active Toga widget instance initiating the share.
            :param html_file_path: Absolute string path to the local HTML file.
            """
            # 1. Ensure the file path exists and convert it into a native file URL
            absolute_path = str(Path(html_file_path).resolve())
            file_url = NSURL.fileURLWithPath_(absolute_path)
    
            # 2. Add the URL asset into an Objective-C array of items to share
            share_items = NSMutableArray.alloc().init()
            share_items.addObject_(file_url)
    
            # 3. Initialize the native UIActivityViewController
            # Pass None for custom applicationActivities to use standard system defaults
            activity_vc = UIActivityViewController.alloc().initWithActivityItems(
                share_items, 
                applicationActivities=None
            )
    
            # 4. Grab the native UIViewController backing your Toga Window
            presenting_vc = w.app.main_window._impl.native.rootViewController
    
            # 5. Handle iPad popover configurations safely to prevent crashes
            if activity_vc.popoverPresentationController:
                # Anchor the popover menu to the center or bounds of the current view frame
                activity_vc.popoverPresentationController.sourceView = presenting_vc.view
                activity_vc.popoverPresentationController.sourceRect = presenting_vc.view.bounds
                # Optional: restrict arrow directions if needed
                # activity_vc.popoverPresentationController.permittedArrowDirections = 0
        
            # 6. Present the share sheet asynchronously over the top of the interface
            presenting_vc.presentViewController(
                activity_vc, 
                animated=True, 
                completion=None
            )

    Utils = IOSUtils

else:
    Utils = PlatformUtils
