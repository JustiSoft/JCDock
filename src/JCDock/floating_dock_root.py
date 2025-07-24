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
        
        # Override the close button to actually close the window when user clicks it
        if self.title_bar and self.title_bar.close_button:
            self.title_bar.close_button.clicked.disconnect()
            self.title_bar.close_button.clicked.connect(self._handle_user_close)

    def set_title(self, new_title: str):
        """Override to prevent title changes - FloatingDockRoot keeps its original title."""
        pass
    
    def update_dynamic_title(self):
        """Override to prevent dynamic title updates - FloatingDockRoot keeps its original title."""
        pass
    
    def _handle_user_close(self):
        """Handle close button click by actually closing the window and all its contents."""
        if self.manager:
            # Get all widgets in this container before closing
            root_node = self.manager.model.roots.get(self)
            if root_node:
                # Emit close signals for all widgets that will be closed
                all_widgets_in_container = self.manager.model.get_all_widgets_from_node(root_node)
                for widget_node in all_widgets_in_container:
                    if hasattr(widget_node, 'persistent_id'):
                        self.manager.signals.widget_closed.emit(widget_node.persistent_id)
                
                # Remove this container from the model
                del self.manager.model.roots[self]
                
                # Remove from container tracking
                if self in self.manager.containers:
                    self.manager.containers.remove(self)
                
                # Emit layout change signal
                self.manager.signals.layout_changed.emit()
        
        # Actually close the window
        self.close()
    
    def closeEvent(self, event):
        """Handle window close events (Alt+F4, system close, etc.)."""
        if self.manager:
            # Get all widgets in this container before closing
            root_node = self.manager.model.roots.get(self)
            if root_node:
                # Emit close signals for all widgets that will be closed
                all_widgets_in_container = self.manager.model.get_all_widgets_from_node(root_node)
                for widget_node in all_widgets_in_container:
                    if hasattr(widget_node, 'persistent_id'):
                        self.manager.signals.widget_closed.emit(widget_node.persistent_id)
                
                # Remove this container from the model
                del self.manager.model.roots[self]
                
                # Remove from container tracking
                if self in self.manager.containers:
                    self.manager.containers.remove(self)
                
                # Emit layout change signal
                self.manager.signals.layout_changed.emit()
        
        # Accept the close event to allow the window to close
        event.accept()

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
                
            # Case 2: Window activated through Qt's native system
            elif event.type() == QEvent.Type.WindowActivate:
                if self.manager:
                    # Sync Z-order tracking with Qt's window activation
                    self.manager.sync_window_activation(self)
                    # Also ensure consistent stacking with other floating widgets
                    self.manager.raise_all_floating_widgets()
                return super().eventFilter(watched, event)


        # For all other events, use the parent's implementation.
        return super().eventFilter(watched, event)