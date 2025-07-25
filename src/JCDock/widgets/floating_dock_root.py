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
            title_bar_color=QColor("#8B4513")
        )
        self.setWindowTitle("Docking Application Layout")
        self.setGeometry(400, 400, 600, 500)
        self.installEventFilter(self)
        
        self._original_title = "Docking Application Layout"
        
        if self.title_bar:
            self.title_bar.title_label.setText("Docking Application Layout")
        
        self.set_persistent_root(True)
        
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
            root_node = self.manager.model.roots.get(self)
            if root_node:
                all_widgets_in_container = self.manager.model.get_all_widgets_from_node(root_node)
                for widget_node in all_widgets_in_container:
                    if hasattr(widget_node, 'persistent_id'):
                        self.manager.signals.widget_closed.emit(widget_node.persistent_id)
                
                del self.manager.model.roots[self]
                
                if self in self.manager.containers:
                    self.manager.containers.remove(self)
                
                self.manager.signals.layout_changed.emit()
        
        self.close()
    
    def closeEvent(self, event):
        """Handle window close events (Alt+F4, system close, etc.)."""
        if self.manager:
            root_node = self.manager.model.roots.get(self)
            if root_node:
                all_widgets_in_container = self.manager.model.get_all_widgets_from_node(root_node)
                for widget_node in all_widgets_in_container:
                    if hasattr(widget_node, 'persistent_id'):
                        self.manager.signals.widget_closed.emit(widget_node.persistent_id)
                
                del self.manager.model.roots[self]
                
                if self in self.manager.containers:
                    self.manager.containers.remove(self)
                
                self.manager.signals.layout_changed.emit()
        
        event.accept()

    def on_activation_request(self):
        """
        Overrides the parent method to add special behavior.
        """
        super().on_activation_request()

    def eventFilter(self, watched, event):
        """
        Handles activation events to ensure consistent stacking with the main window.
        """
        if watched is self:
            if event.type() == QEvent.Type.WindowActivate:
                if self.manager:
                    self.manager.sync_window_activation(self)
                return super().eventFilter(watched, event)

        return super().eventFilter(watched, event)