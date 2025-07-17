from PySide6.QtCore import QTimer, QEvent
from .dock_container import DockContainer

class FloatingDockRoot(DockContainer):
    """
    A specialized DockContainer that acts as a floating main window.
    It overrides the standard activation request to add its special behavior.
    """

    def __init__(self, manager, parent=None):
        super().__init__(
            parent=parent,
            manager=manager,
            create_shadow=True,
            show_title_bar=True
        )
        self.setWindowTitle("Floating Dock Area")
        self.setGeometry(400, 400, 600, 500)
        # The event filter is installed on the DockContainer itself.
        self.installEventFilter(self)

    def on_activation_request(self):
        """
        Overrides the parent method to add special behavior.
        """
        # Step 1: Call the parent's implementation first.
        # This handles the essential job of raising this window itself.
        super().on_activation_request()

        # Step 2: Add our special behavior.
        # Schedule all other floating widgets to be raised on top.
        if self.manager:
            QTimer.singleShot(0, self.manager.raise_all_floating_widgets)

    def eventFilter(self, watched, event):
        """
        Handles activation events to ensure consistent stacking with the main window.
        """
        if watched is self:
            # Case 1: The title bar or window frame is clicked.
            if event.type() == QEvent.Type.NonClientAreaMouseButtonPress:
                if self.manager:
                    self.manager.raise_all_floating_widgets()
                return super().eventFilter(watched, event)

            # Case 2: The window is activated by other means (e.g., clicking client area).
            if event.type() == QEvent.Type.WindowActivate:
                if self.manager:
                    # Use a timer to run this *after* the OS has raised the window.
                    QTimer.singleShot(0, self.manager.raise_all_floating_widgets)
                # Important: still call the parent's filter to handle shadow color changes.
                return super().eventFilter(watched, event)

        # For all other events, use the parent's implementation.
        return super().eventFilter(watched, event)