from PySide6.QtCore import QTimer, QEvent
from .dock_container import DockContainer

class FloatingDockRoot(DockContainer):
    """
    A specialized DockContainer that acts as a floating main window.
    It overrides the standard activation request to add its special behavior.
    """

    def __init__(self, manager, parent=None):
        from PySide6.QtGui import QColor
        super().__init__(
            parent=parent,
            manager=manager,
            create_shadow=True,
            show_title_bar=True,
            title_bar_color=QColor("#8B4513")  # Distinct brown color for FloatingDockRoot
        )
        self.setWindowTitle("Docking Application Layout")
        self.setGeometry(400, 400, 600, 500)
        # The event filter is installed on the DockContainer itself.
        self.installEventFilter(self)
        
        # Store the original title to prevent changes
        self._original_title = "Docking Application Layout"
        
        # Set the title bar text to match
        if self.title_bar:
            self.title_bar.title_label.setText("Docking Application Layout")
        
        # Mark this as a persistent root that should never be closed
        self.set_persistent_root(True)

    def set_title(self, new_title: str):
        """Override to prevent title changes - FloatingDockRoot keeps its original title."""
        pass
    
    def update_dynamic_title(self):
        """Override to prevent dynamic title updates - FloatingDockRoot keeps its original title."""
        pass

    def on_activation_request(self):
        """
        Overrides the parent method to add special behavior.
        """
        # Step 1: Call the parent's implementation first.
        # This handles the essential job of raising this window itself.
        super().on_activation_request()

        # Step 2: Add our special behavior.
        # Make activation immediate and synchronous to eliminate race conditions.
        if self.manager:
            self.manager.raise_all_floating_widgets()

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


        # For all other events, use the parent's implementation.
        return super().eventFilter(watched, event)