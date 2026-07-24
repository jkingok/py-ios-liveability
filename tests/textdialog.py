from rubicon.objc import Block, ObjCClass, ObjCInstance
import threading
import toga

done = threading.Event()

UIAlertController = ObjCClass("UIAlertController")
UIAlertAction = ObjCClass("UIAlertAction")

def do_alert():
    # Preferred Styles: 0 = ActionSheet, 1 = Alert
    # Text fields not allowed in Sheets
    alert = UIAlertController.alertControllerWithTitle(
        "Enter Workspace Name",
        message="Please supply a title for your new workspace:",
        preferredStyle=1
    )

    # Add text input field
    alert.addTextFieldWithConfigurationHandler_(
        Block(
            lambda tf: setattr(tf, 'placeholder', "e.g., My Workspace"),
            None,
            ObjCInstance
        ) 
    )

    # Define action handler
    def on_done(action: ObjCInstance) -> None:
        done.set()

    def on_confirm(action: ObjCInstance) -> None:
        text_field = alert.textFields.firstObject
        print("User entered:", text_field.text)
        on_done(action)

    confirm_action = UIAlertAction.actionWithTitle("Create", style=0, handler=on_confirm)
    cancel_action = UIAlertAction.actionWithTitle("Cancel", style=1, handler=on_done)

    alert.addAction_(confirm_action)
    alert.addAction_(cancel_action)

    # Present modally
    toga.App.app.main_window._impl.native.rootViewController.presentViewController(alert, animated=True, completion=None)

toga.App.app.loop.call_soon(do_alert)
done.wait()
