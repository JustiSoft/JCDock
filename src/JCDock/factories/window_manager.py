from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication

from ..widgets.dock_container import DockContainer


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
        Validates and corrects a window's geometry to ensure it's visible across multi-monitor setups.
        Allows windows to span monitors while ensuring minimum visibility is maintained.
        
        Args:
            geometry: The proposed window geometry
            
        Returns:
            QRect: A corrected geometry that ensures the window is visible on desktop
        """
        validated_geometry = QRect(geometry)
        
        # Ensure minimum dimensions
        min_width = max(200, validated_geometry.width())
        min_height = max(150, validated_geometry.height())
        validated_geometry.setWidth(min_width)
        validated_geometry.setHeight(min_height)
        
        # Calculate total desktop bounds for multi-monitor support
        desktop_bounds = self._calculate_desktop_bounds()
        
        # Apply intelligent positioning to ensure visibility while allowing cross-monitor spanning
        self._ensure_minimum_visibility(validated_geometry, desktop_bounds)
        
        return validated_geometry
    
    def _calculate_desktop_bounds(self) -> QRect:
        """
        Calculate the bounding rectangle encompassing all available screen real estate.
        
        Returns:
            QRect: Combined geometry of all screens
        """
        total_bounds = QRect()
        
        screens = QApplication.screens()
        if not screens:
            primary = QApplication.primaryScreen()
            if primary:
                return primary.availableGeometry()
            return QRect(0, 0, 1920, 1080)  # Fallback
        
        for screen in screens:
            screen_geom = screen.availableGeometry()
            if total_bounds.isEmpty():
                total_bounds = QRect(screen_geom)
            else:
                total_bounds = total_bounds.united(screen_geom)
        
        return total_bounds
    
    def _ensure_minimum_visibility(self, geometry: QRect, desktop_bounds: QRect):
        """
        Ensure the window maintains minimum visibility on the desktop while allowing
        cross-monitor positioning. Only adjusts position if window would be completely hidden.
        
        Args:
            geometry: Window geometry to adjust (modified in-place)
            desktop_bounds: Total desktop area bounds
        """
        min_visible_pixels = 50  # Minimum pixels that must remain visible
        
        # Only adjust if window would be completely outside desktop bounds
        if geometry.right() < desktop_bounds.left():
            geometry.moveLeft(desktop_bounds.left() - geometry.width() + min_visible_pixels)
        elif geometry.left() > desktop_bounds.right():
            geometry.moveLeft(desktop_bounds.right() - min_visible_pixels)
            
        if geometry.bottom() < desktop_bounds.top():
            geometry.moveTop(desktop_bounds.top() - geometry.height() + min_visible_pixels)
        elif geometry.top() > desktop_bounds.bottom():
            geometry.moveTop(desktop_bounds.bottom() - min_visible_pixels)
        
        # Limit maximum size to prevent unreasonably large windows
        max_width = min(geometry.width(), desktop_bounds.width() + 200)  # Allow slight overhang
        max_height = min(geometry.height(), desktop_bounds.height() + 200)
        geometry.setWidth(max_width)
        geometry.setHeight(max_height)

    def create_new_floating_root(self):
        """
        Creates, registers, and shows a new floating root window that can
        act as a secondary main docking area.
        
        Returns:
            DockContainer: The newly created floating root window
        """
        new_root_window = DockContainer(
            manager=self.manager, 
            show_title_bar=True,
            is_main_window=False, 
            window_title="Floating Dock Root",
            auto_persistent_root=True
        )

        self.manager.register_dock_area(new_root_window)

        new_root_window.show()
        new_root_window.raise_()
        new_root_window.activateWindow()
        
        self.bring_to_front(new_root_window)
        
        return new_root_window