from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication

from ..widgets.floating_dock_root import FloatingDockRoot


class WindowManager:
    """
    Manages window stacking, geometry validation, and floating root creation.
    Handles the Z-order tracking and window positioning logic.
    """
    
    def __init__(self, manager):
        """
        Initialize the window manager.
        
        Args:
            manager: Reference to the DockingManager instance
        """
        self.manager = manager
    
    def bring_to_front(self, widget):
        """
        Brings a window to the top of our manual stack.
        
        Args:
            widget: The widget/window to bring to front
        """
        self.manager.window_stack = [w for w in self.manager.window_stack if w is not widget]
        self.manager.window_stack.append(widget)

    def sync_window_activation(self, activated_widget):
        """
        Synchronizes window_stack when a window is activated through Qt's native system.
        This ensures Z-order tracking stays consistent with actual window stacking.
        
        Args:
            activated_widget: The widget that was activated
        """
        if activated_widget in self.manager.window_stack:
            self.bring_to_front(activated_widget)
            self.manager.hit_test_cache.invalidate()

    def validate_window_geometry(self, geometry: QRect) -> QRect:
        """
        Validates and corrects a window's geometry to ensure it's visible on a screen.
        
        Args:
            geometry: The proposed window geometry
            
        Returns:
            QRect: A corrected geometry that ensures the window is visible on a screen
        """
        screen = QApplication.screenAt(geometry.topLeft())
        if not screen:
            screen = QApplication.primaryScreen()
        
        available_geometry = screen.availableGeometry()
        validated_geometry = QRect(geometry)
        
        # Ensure minimum dimensions
        min_width = max(200, validated_geometry.width())
        min_height = max(150, validated_geometry.height())
        validated_geometry.setWidth(min_width)
        validated_geometry.setHeight(min_height)
        
        # Constrain to screen bounds
        max_width = min(validated_geometry.width(), available_geometry.width())
        max_height = min(validated_geometry.height(), available_geometry.height())
        validated_geometry.setWidth(max_width)
        validated_geometry.setHeight(max_height)
        
        # Adjust position to keep window on screen
        if validated_geometry.right() > available_geometry.right():
            validated_geometry.moveRight(available_geometry.right())
        if validated_geometry.bottom() > available_geometry.bottom():
            validated_geometry.moveBottom(available_geometry.bottom())
        if validated_geometry.left() < available_geometry.left():
            validated_geometry.moveLeft(available_geometry.left())
        if validated_geometry.top() < available_geometry.top():
            validated_geometry.moveTop(available_geometry.top())
        
        return validated_geometry

    def create_new_floating_root(self):
        """
        Creates, registers, and shows a new floating root window that can
        act as a secondary main docking area.
        
        Returns:
            FloatingDockRoot: The newly created floating root window
        """
        new_root_window = FloatingDockRoot(manager=self.manager)

        self.manager.register_dock_area(new_root_window)

        new_root_window.show()
        new_root_window.raise_()
        new_root_window.activateWindow()
        
        self.bring_to_front(new_root_window)
        
        return new_root_window