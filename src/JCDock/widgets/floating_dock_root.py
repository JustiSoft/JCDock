from PySide6.QtCore import QTimer, QEvent
from .dock_container import DockContainer
from ..utils.windows_shadow import apply_native_shadow

class FloatingDockRoot(DockContainer):
    """
    A specialized DockContainer that acts as a floating main window.
    It overrides the standard activation request to add its special behavior.
    """

    def __init__(self, manager, parent=None, is_main_window=False, title=None, 
                 title_bar_color=None, title_text_color=None):
        from PySide6.QtGui import QColor
        
        # Determine if we should show title bar based on title parameter
        show_title_bar = title is not None
        
        # Use provided colors or set more pleasing defaults
        if title_bar_color is None:
            title_bar_color = QColor("#2F4F4F")  # Dark teal - more pleasing than brown
        
        super().__init__(
            parent=parent,
            manager=manager,
            show_title_bar=show_title_bar,
            title_bar_color=title_bar_color,
            title_text_color=title_text_color
        )
        self.is_main_window = is_main_window
        
        # Set window title and title bar text
        window_title = title if title else "Docking Application Layout"
        self.setWindowTitle(window_title)
        self.setGeometry(400, 400, 600, 500)
        self.installEventFilter(self)
        
        self._original_title = window_title
        
        if self.title_bar and title:
            self.title_bar.title_label.setText(title)
        
        self.set_persistent_root(True)
        
        if self.title_bar and self.title_bar.close_button:
            self.title_bar.close_button.clicked.disconnect()
            self.title_bar.close_button.clicked.connect(self._handle_user_close)
        
        # Apply native Windows shadow after all setup is complete
        apply_native_shadow(self)
    
    def menuBar(self):
        """Provide QMainWindow-like menuBar() method for compatibility."""
        if hasattr(self, '_menu_bar'):
            return self._menu_bar
        return None

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
        
        if self.is_main_window:
            from PySide6.QtWidgets import QApplication
            QApplication.instance().quit()
        else:
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
        
        if self.is_main_window:
            from PySide6.QtWidgets import QApplication
            QApplication.instance().quit()
        
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