from typing import Optional, Tuple
from dataclasses import dataclass
from PySide6.QtCore import QRect, QPoint, QSize
from PySide6.QtWidgets import QWidget, QApplication


@dataclass
class ResizeConstraints:
    """Cached resize constraints for a container."""
    min_width: int
    min_height: int
    screen_geometry: QRect
    desktop_geometry: QRect
    shadow_margin: int = 0
    min_shadow_width: int = 0
    min_shadow_height: int = 0


class ResizeCache:
    """
    Caching system for resize operations to eliminate expensive screen geometry
    queries and constraint calculations during mouse move events.
    """
    
    def __init__(self):
        self._constraints: Optional[ResizeConstraints] = None
        self._cached_screen = None
        self._last_position: Optional[QPoint] = None
        self._cached_edge: Optional[str] = None
        self._edge_cache_threshold = 3  # pixels
        self._performance_monitor = None
        
    def set_performance_monitor(self, monitor):
        """Set reference to performance monitor for cache statistics."""
        self._performance_monitor = monitor
        
    def cache_resize_constraints(self, widget: QWidget, has_shadow: bool = False, 
                                blur_radius: int = 0) -> ResizeConstraints:
        """
        Cache all resize constraints at the start of a resize operation.
        This eliminates the need for expensive recalculations during mouse moves.
        
        Args:
            widget: The widget being resized
            has_shadow: Whether the widget has shadow effects
            blur_radius: Shadow blur radius for shadow constraints
            
        Returns:
            ResizeConstraints: Cached constraint data
        """
        if self._performance_monitor:
            timer_id = self._performance_monitor.start_timing('resize_constraint_caching')
        
        try:
            # Cache screen geometry (expensive operation)
            screen = QApplication.screenAt(widget.pos())
            if not screen:
                screen = QApplication.primaryScreen()
            self._cached_screen = screen
            screen_geom = screen.availableGeometry()
            
            # Calculate total desktop geometry across all screens
            desktop_geom = self._calculate_total_desktop_geometry()
            
            # Cache minimum size constraints
            min_width = max(widget.minimumWidth(), 100)
            min_height = max(widget.minimumHeight(), 100)
            
            # Cache shadow constraints if applicable
            shadow_margin = 0
            min_shadow_width = min_width
            min_shadow_height = min_height
            
            if has_shadow and blur_radius > 0:
                shadow_margin = 2 * blur_radius
                min_shadow_width = shadow_margin + 50
                min_shadow_height = shadow_margin + 50
                
                if min_width < min_shadow_width:
                    min_width = min_shadow_width
                if min_height < min_shadow_height:
                    min_height = min_shadow_height
            
            self._constraints = ResizeConstraints(
                min_width=min_width,
                min_height=min_height,
                screen_geometry=screen_geom,
                desktop_geometry=desktop_geom,
                shadow_margin=shadow_margin,
                min_shadow_width=min_shadow_width,
                min_shadow_height=min_shadow_height
            )
            
            if self._performance_monitor:
                self._performance_monitor.increment_counter('resize_constraints_cached')
                
            return self._constraints
            
        finally:
            if self._performance_monitor and 'timer_id' in locals():
                self._performance_monitor.end_timing(timer_id)
    
    def _calculate_total_desktop_geometry(self) -> QRect:
        """
        Calculate the bounding rectangle of all available screen geometries.
        This allows windows to resize across monitor boundaries naturally.
        
        Returns:
            QRect: Total desktop geometry encompassing all screens
        """
        total_rect = QRect()
        
        # Get all screens
        screens = QApplication.screens()
        if not screens:
            # Fallback to primary screen if no screens found
            primary = QApplication.primaryScreen()
            if primary:
                return primary.availableGeometry()
            return QRect(0, 0, 1920, 1080)  # Ultimate fallback
        
        # Calculate bounding rectangle of all screen geometries
        for screen in screens:
            screen_geom = screen.availableGeometry()
            if total_rect.isEmpty():
                total_rect = QRect(screen_geom)
            else:
                total_rect = total_rect.united(screen_geom)
        
        return total_rect
    
    def get_cached_constraints(self) -> Optional[ResizeConstraints]:
        """Get the currently cached resize constraints."""
        return self._constraints
    
    def validate_cached_screen(self, widget: QWidget) -> bool:
        """
        Validate that the cached screen is still correct for the widget.
        Only invalidates cache if widget center moved completely to a different screen.
        This prevents unnecessary cache invalidation during cross-monitor operations.
        
        Returns True if cache is valid, False if screen changed significantly.
        """
        if not self._cached_screen or not self._constraints:
            return False
            
        # Use widget center point for more stable screen detection
        widget_center = widget.geometry().center()
        current_screen = QApplication.screenAt(widget_center)
        if not current_screen:
            current_screen = QApplication.primaryScreen()
            
        # Only invalidate cache if widget center moved to a significantly different screen
        # This allows windows to span monitors during resize without cache thrashing
        if current_screen != self._cached_screen:
            # Check if the widget is still partially on the cached screen
            cached_screen_geom = self._cached_screen.availableGeometry()
            widget_geom = widget.geometry()
            
            # If widget still intersects with cached screen, keep cache valid
            if cached_screen_geom.intersects(widget_geom):
                return True
                
            # Widget completely moved to different screen, invalidate cache
            if self._performance_monitor:
                self._performance_monitor.increment_counter('screen_changes')
            return False
            
        return True
    
    def update_screen_cache(self, widget: QWidget):
        """Update cached screen geometry when widget moves to different screen."""
        if not self._constraints:
            return
            
        screen = QApplication.screenAt(widget.pos())
        if not screen:
            screen = QApplication.primaryScreen()
            
        self._cached_screen = screen
        self._constraints.screen_geometry = screen.availableGeometry()
        self._constraints.desktop_geometry = self._calculate_total_desktop_geometry()
        
        if self._performance_monitor:
            self._performance_monitor.increment_counter('screen_cache_updates')
    
    def cache_edge_detection(self, position: QPoint, edge: Optional[str]):
        """
        Cache edge detection result to avoid redundant calculations.
        
        Args:
            position: Mouse position where edge was detected
            edge: Detected edge (or None)
        """
        self._last_position = position
        self._cached_edge = edge
        
        if self._performance_monitor:
            self._performance_monitor.increment_counter('edge_detections_cached')
    
    def get_cached_edge(self, position: QPoint) -> Optional[str]:
        """
        Get cached edge detection if position is within threshold.
        
        Args:
            position: Current mouse position
            
        Returns:
            str: Cached edge if within threshold, None if cache miss
        """
        if not self._last_position or not self._cached_edge:
            if self._performance_monitor:
                self._performance_monitor.increment_counter('edge_cache_misses')
            return None
            
        # Check if position is within cache threshold
        dx = abs(position.x() - self._last_position.x())
        dy = abs(position.y() - self._last_position.y())
        
        if dx <= self._edge_cache_threshold and dy <= self._edge_cache_threshold:
            if self._performance_monitor:
                self._performance_monitor.increment_counter('edge_cache_hits')
            return self._cached_edge
        else:
            if self._performance_monitor:
                self._performance_monitor.increment_counter('edge_cache_misses')
            return None
    
    def apply_constraints_to_geometry(self, new_geom: QRect) -> QRect:
        """
        Apply cached constraints to a new geometry rectangle.
        This replaces the expensive inline constraint checking.
        
        Args:
            new_geom: Proposed new geometry
            
        Returns:
            QRect: Geometry with constraints applied
        """
        if not self._constraints:
            return new_geom
            
        constraints = self._constraints
        
        # Apply minimum size constraints
        if new_geom.width() < constraints.min_width:
            new_geom.setWidth(constraints.min_width)
        if new_geom.height() < constraints.min_height:
            new_geom.setHeight(constraints.min_height)
            
        # Apply desktop boundary constraints (allows cross-monitor resizing)
        desktop_geom = constraints.desktop_geometry
        
        # Only constrain if window would go completely outside desktop bounds
        # This allows windows to span multiple monitors naturally
        if new_geom.right() < desktop_geom.left():
            new_geom.moveLeft(desktop_geom.left() - new_geom.width() + 50)  # Keep 50px visible
        if new_geom.left() > desktop_geom.right():
            new_geom.moveLeft(desktop_geom.right() - 50)  # Keep 50px visible
        if new_geom.bottom() < desktop_geom.top():
            new_geom.moveTop(desktop_geom.top() - new_geom.height() + 50)  # Keep 50px visible
        if new_geom.top() > desktop_geom.bottom():
            new_geom.moveTop(desktop_geom.bottom() - 50)  # Keep 50px visible
            
        # Apply sanity checks
        if (new_geom.width() <= 0 or new_geom.height() <= 0 or
            new_geom.width() > 5000 or new_geom.height() > 5000):
            return QRect()  # Invalid geometry
            
        if self._performance_monitor:
            self._performance_monitor.increment_counter('constraint_applications')
            
        return new_geom
    
    def clear_cache(self):
        """Clear all cached data when resize operation ends."""
        self._constraints = None
        self._cached_screen = None
        self._last_position = None
        self._cached_edge = None
        
        if self._performance_monitor:
            self._performance_monitor.increment_counter('cache_clears')
    
    def get_cache_stats(self) -> dict:
        """Get statistics about cache usage for performance monitoring."""
        return {
            'has_constraints': self._constraints is not None,
            'has_screen_cache': self._cached_screen is not None,
            'has_edge_cache': self._last_position is not None,
            'edge_threshold': self._edge_cache_threshold
        }