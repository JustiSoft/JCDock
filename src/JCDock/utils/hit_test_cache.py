from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from PySide6.QtCore import QRect, QPoint
from PySide6.QtWidgets import QWidget, QTabWidget, QSplitter


@dataclass
class CachedDropTarget:
    """Cached information about a potential drop target.
    Uses cached geometry for better performance during drag operations.
    """
    widget: QWidget
    target_type: str
    parent_container: Optional[QWidget] = None
    tab_index: int = -1
    z_order: int = 0
    _hit_test_cache: Optional['HitTestCache'] = None
    
    def set_hit_test_cache(self, cache: 'HitTestCache'):
        """Set reference to hit test cache for geometry lookups."""
        self._hit_test_cache = cache
    
    @property
    def global_rect(self) -> QRect:
        """
        Gets the global rectangle using cached geometry when possible.
        Falls back to dynamic calculation if cache is not available.
        """
        if self.parent_container and hasattr(self.widget, 'content_container'):
            visible_part = self.widget.content_container
        else:
            visible_part = self.widget

        if not visible_part or not visible_part.isVisible():
            return QRect()

        # Try to use cached geometry first
        if self._hit_test_cache:
            cached_geometry = self._hit_test_cache.get_cached_geometry(visible_part)
            if cached_geometry:
                return cached_geometry

        # Fall back to dynamic calculation
        try:
            if hasattr(visible_part, 'isValid') and callable(getattr(visible_part, 'isValid')):
                if not visible_part.isValid():
                    return QRect()

            global_pos = visible_part.mapToGlobal(QPoint(0, 0))
            size = visible_part.size()
            if (global_pos.x() < -50000 or global_pos.y() < -50000 or
                global_pos.x() > 50000 or global_pos.y() > 50000 or
                size.width() <= 0 or size.height() <= 0):
                return QRect()

            return QRect(global_pos, size)
        except:
            return QRect()


@dataclass
class CachedTabBarInfo:
    """Cached information about tab bars for fast hit-testing.
    Note: tab_bar_rect is calculated dynamically to avoid stale coordinates.
    """
    tab_widget: QTabWidget
    container: QWidget
    
    @property
    def tab_bar_rect(self) -> QRect:
        """
        Dynamically calculates the tab bar rectangle to avoid stale coordinates.
        """
        if not self.tab_widget or not self.tab_widget.isVisible():
            return QRect()
        tab_bar = self.tab_widget.tabBar()
        if not tab_bar or not tab_bar.isVisible():
            return QRect()
        try:
            if hasattr(tab_bar, 'isValid') and callable(getattr(tab_bar, 'isValid')):
                if not tab_bar.isValid():
                    return QRect()
            
            global_pos = tab_bar.mapToGlobal(QPoint(0, 0))
            size = tab_bar.size()
            if (global_pos.x() < -50000 or global_pos.y() < -50000 or 
                global_pos.x() > 50000 or global_pos.y() > 50000 or
                size.width() <= 0 or size.height() <= 0):
                return QRect()
                
            return QRect(global_pos, size)
        except:
            return QRect()


class HitTestCache:
    """High-performance caching system for drag operation hit-testing.
    
    Dramatically reduces CPU usage during drag operations by caching
    widget geometries and drop target information.
    """
    
    def __init__(self):
        self._drop_targets: List[CachedDropTarget] = []
        self._tab_bars: List[CachedTabBarInfo] = []
        self._window_rects: Dict[QWidget, QRect] = {}
        self._cache_valid = False
        self._last_mouse_pos: Optional[QPoint] = None
        self._last_hit_result: Optional[Tuple[QWidget, str]] = None
        self._in_drag_operation = False
        self._dragging_container: Optional[QWidget] = None
        self._geometry_cache: Dict[QWidget, QRect] = {}  # Cache for widget geometries
        self._dirty_regions: set = set()  # Track dirty regions needing updates
        self._performance_monitor = None  # Will be set by DockingManager
        
    def invalidate(self, selective_widget: Optional[QWidget] = None):
        """
        Invalidates the cache, with optional selective invalidation.
        Call this when the layout changes.
        
        Args:
            selective_widget: If provided, only invalidate cache entries related to this widget
        """
        if selective_widget:
            # Selective invalidation - only clear entries related to specific widget
            self._selective_invalidate(selective_widget)
        else:
            # Full invalidation
            self._cache_valid = False
            self._drop_targets.clear()
            self._tab_bars.clear()
            self._window_rects.clear()
            self._last_mouse_pos = None
            self._last_hit_result = None
            self._in_drag_operation = False
            self._dragging_container = None
            self._geometry_cache.clear()
            self._dirty_regions.clear()
    
    def _selective_invalidate(self, widget: QWidget):
        """
        Selectively invalidate cache entries related to a specific widget.
        
        Args:
            widget: Widget to invalidate cache entries for
        """
        # Remove drop targets related to this widget
        self._drop_targets = [t for t in self._drop_targets 
                             if t.widget is not widget and t.parent_container is not widget]
        
        # Remove tab bars related to this widget  
        self._tab_bars = [tb for tb in self._tab_bars 
                         if tb.container is not widget and tb.tab_widget.parent() is not widget]
        
        # Remove window rects for this widget
        if widget in self._window_rects:
            del self._window_rects[widget]
        
        # Mark geometry as dirty for this widget
        self.mark_widget_dirty(widget)
        
        # Clear last hit result if it involves this widget
        if (self._last_hit_result and 
            len(self._last_hit_result) > 0 and 
            self._last_hit_result[0] is widget):
            self._last_mouse_pos = None
            self._last_hit_result = None
        
    def build_cache(self, window_stack: List[QWidget], dock_containers: List[QWidget]):
        """
        Builds the cache by analyzing all visible windows and containers.
        
        Args:
            window_stack: List of top-level windows (in stacking order, last = topmost)
            dock_containers: List of dock container widgets
        """
        if self._cache_valid:
            return
            
        self._drop_targets.clear()
        self._tab_bars.clear()
        self._window_rects.clear()
        
        for z_index, window in enumerate(window_stack):
            try:
                if window and window.isVisible():
                    # Ensure window has stable geometry before caching
                    if hasattr(window, 'isValid') and callable(getattr(window, 'isValid')):
                        if not window.isValid():
                            continue
                    
                    global_pos = window.mapToGlobal(QPoint(0, 0))
                    global_rect = QRect(global_pos, window.size())
                    
                    # Validate geometry is reasonable
                    if (global_pos.x() < -50000 or global_pos.y() < -50000 or 
                        global_pos.x() > 50000 or global_pos.y() > 50000 or
                        window.size().width() <= 0 or window.size().height() <= 0):
                        continue
                        
                    self._window_rects[window] = (global_rect, z_index)
            except RuntimeError:
                # Window was deleted, skip it
                continue
        
        for container in dock_containers:
            try:
                if container and container.isVisible():
                    container_z_order = -1  # Default to very low priority if not found in window_stack
                    for window, (rect, z_index) in self._window_rects.items():
                        if window is container:
                            container_z_order = z_index
                            break
                    
                    # Ensure main windows get proper priority even if not found in window_rects
                    if container_z_order == -1 and hasattr(container, 'is_main_window') and container.is_main_window:
                        # Find main window's actual position in window_stack
                        for idx, window in enumerate(window_stack):
                            if window is container:
                                container_z_order = idx
                                break
                    
                    self._cache_container_targets(container, container_z_order)
            except RuntimeError:
                # Container was deleted, skip it
                continue
        
        for z_index, window in enumerate(window_stack):
            try:
                if window and window.isVisible():
                    from ..widgets.dock_panel import DockPanel
                    if isinstance(window, DockPanel) and not window.parent_container:
                        target = CachedDropTarget(
                            widget=window,
                            target_type='widget',
                            z_order=z_index
                        )
                        target.set_hit_test_cache(self)
                        self._drop_targets.append(target)
            except RuntimeError:
                # Window was deleted, skip it
                continue
                
        self._cache_valid = True
        
    def _cache_container_targets(self, container, z_order=0):
        if container and container.isVisible():
            target = CachedDropTarget(
                widget=container,
                target_type='container',
                z_order=z_order
            )
            target.set_hit_test_cache(self)
            self._drop_targets.append(target)
        
        if hasattr(container, 'splitter') and container.splitter:
            self._cache_traversal_targets(container, container.splitter, z_order)
                
    def _cache_traversal_targets(self, container, current_widget, z_order=0):
        if not current_widget or not current_widget.isVisible():
            return

        # Skip caching targets from the container that's currently being dragged
        if self._dragging_container and container is self._dragging_container:
            return

        if isinstance(current_widget, QTabWidget):
            current_tab_content = current_widget.currentWidget()
            if current_tab_content:
                dockable_widget = current_tab_content.property("dockable_widget")
                if dockable_widget:
                    target = CachedDropTarget(
                        widget=dockable_widget,
                        target_type='widget',
                        parent_container=container,
                        z_order=z_order
                    )
                    target.set_hit_test_cache(self)
                    self._drop_targets.append(target)

            tab_bar = current_widget.tabBar()
            if tab_bar and tab_bar.isVisible():
                immediate_parent_container = current_widget.parentWidget()
                if immediate_parent_container:
                    self._tab_bars.append(CachedTabBarInfo(
                        tab_widget=current_widget,
                        container=immediate_parent_container
                    ))

        elif isinstance(current_widget, QSplitter):
            for i in range(current_widget.count()):
                child_widget = current_widget.widget(i)
                self._cache_traversal_targets(container, child_widget, z_order)
                
                        
    def find_window_at_position(self, global_pos: QPoint, excluded_widget=None) -> Optional[QWidget]:
        """
        Fast lookup of top-level window at position using cached rectangles.
        Respects z-order by checking windows from top to bottom.
        """
        candidates = []
        for window, (rect, z_index) in self._window_rects.items():
            if window is excluded_widget or not window.isVisible():
                continue
            if rect.contains(global_pos):
                candidates.append((window, z_index))
        
        if candidates:
            return max(candidates, key=lambda x: x[1])[0]
        return None
        
    def find_drop_target_at_position(self, global_pos: QPoint, excluded_widget=None) -> Optional[CachedDropTarget]:
        """
        Fast lookup of drop target at position using cached data.
        Returns the target with highest z-order, then most specific (smallest area).
        Excludes the specified widget to prevent self-docking.
        """
        if (self._last_mouse_pos and self._last_hit_result and 
            self._positions_close(global_pos, self._last_mouse_pos)):
            widget, target_type = self._last_hit_result
            if excluded_widget and widget is excluded_widget:
                pass
            else:
                for target in self._drop_targets:
                    if target.widget is widget and target.target_type == target_type:
                        return target
                    
        matching_targets = []
        for target in self._drop_targets:
            if target.global_rect.contains(global_pos):
                # Exclude the dragging widget itself
                if excluded_widget and target.widget is excluded_widget:
                    continue
                
                # Also exclude widgets that belong to the dragging container
                if excluded_widget and target.parent_container is excluded_widget:
                    continue
                
                # Check if this target is completely obscured by higher Z-order windows
                if self._is_target_obscured_at_position(target, global_pos, excluded_widget):
                    continue
                    
                matching_targets.append(target)
                
        if matching_targets:
            def target_priority(t):
                type_priority = {'widget': 2, 'tab_widget': 1, 'container': 0}[t.target_type]
                return (type_priority, t.z_order, -t.global_rect.width() * t.global_rect.height())
            
            best_target = max(matching_targets, key=target_priority)
            
            self._last_mouse_pos = global_pos
            self._last_hit_result = (best_target.widget, best_target.target_type)
            
            return best_target
            
        return None
    
    def _is_target_obscured_at_position(self, target, global_pos: QPoint, excluded_widget: Optional[QWidget] = None) -> bool:
        """
        Check if the given target is completely obscured by higher Z-order windows at the specific position.
        This prevents hidden containers from intercepting drag operations.
        
        Args:
            target: The target to check for obscurity
            global_pos: The position to check at
            excluded_widget: Widget being dragged that should be ignored when checking for obscurity
        """
        # Check if any higher Z-order window completely covers this position
        for window, (window_rect, window_z_order) in self._window_rects.items():
            # Skip windows with lower or equal Z-order (they're behind or at same level)
            if window_z_order <= target.z_order:
                continue
            
            # Skip the target window itself
            if window is target.widget:
                continue

            # CRITICAL FIX: The widget being dragged cannot obscure other widgets
            if window is excluded_widget:
                continue
                
            # If a higher Z-order window (that isn't being dragged) contains this position, the target is obscured
            if window_rect.contains(global_pos):
                return True
                
        return False
        
    def find_tab_bar_at_position(self, global_pos: QPoint) -> Optional[CachedTabBarInfo]:
        """
        Fast lookup of tab bar at position for tab insertion operations.
        """
        for tab_bar_info in self._tab_bars:
            if tab_bar_info.tab_bar_rect.contains(global_pos):
                return tab_bar_info
        return None
        
    def _positions_close(self, pos1: QPoint, pos2: QPoint, threshold: int = 3) -> bool:
        """
        Checks if two positions are close enough to reuse cached results.
        """
        dx = abs(pos1.x() - pos2.x())
        dy = abs(pos1.y() - pos2.y())
        return dx <= threshold and dy <= threshold
        
    def is_cache_valid(self) -> bool:
        """
        Returns whether the cache is currently valid.
        """
        return self._cache_valid
        
    def set_drag_operation_state(self, in_drag: bool, dragging_container: Optional[QWidget] = None):
        self._in_drag_operation = in_drag
        self._dragging_container = dragging_container if in_drag else None
        if not in_drag:
            self._last_mouse_pos = None
            self._last_hit_result = None
            
    def update_window_coordinates(self, window: QWidget) -> bool:
        if not self._cache_valid or not window:
            return False
            
        if not self._in_drag_operation:
            return False
            
        if window in self._window_rects:
            old_rect, z_index = self._window_rects[window]
            
            try:
                global_pos = window.mapToGlobal(QPoint(0, 0))
                new_rect = QRect(global_pos, window.size())
                
                if (global_pos.x() < -50000 or global_pos.y() < -50000 or 
                    global_pos.x() > 50000 or global_pos.y() > 50000 or
                    window.size().width() <= 0 or window.size().height() <= 0):
                    return False
                    
                self._window_rects[window] = (new_rect, z_index)
                
                if old_rect != new_rect:
                    self._last_mouse_pos = None
                    self._last_hit_result = None
                    
                return True
            except:
                return False
                
        return False
    
    def set_performance_monitor(self, monitor):
        """Set reference to performance monitor for cache statistics."""
        self._performance_monitor = monitor
    
    def get_cached_geometry(self, widget: QWidget) -> Optional[QRect]:
        """
        Get cached geometry for a widget, computing it if not cached.
        
        Args:
            widget: Widget to get geometry for
            
        Returns:
            QRect: Cached or computed geometry, None if widget is invalid
        """
        if not widget or widget in self._dirty_regions:
            if self._performance_monitor:
                self._performance_monitor.increment_counter('cache_misses')
            return None
            
        if widget in self._geometry_cache:
            if self._performance_monitor:
                self._performance_monitor.increment_counter('cache_hits')
            return self._geometry_cache[widget]
            
        # Compute and cache geometry
        try:
            global_pos = widget.mapToGlobal(QPoint(0, 0))
            size = widget.size()
            
            if (global_pos.x() < -50000 or global_pos.y() < -50000 or 
                global_pos.x() > 50000 or global_pos.y() > 50000 or
                size.width() <= 0 or size.height() <= 0):
                return None
                
            geometry = QRect(global_pos, size)
            self._geometry_cache[widget] = geometry
            return geometry
            
        except Exception:
            return None
    
    def mark_widget_dirty(self, widget: QWidget):
        """
        Mark a widget as having dirty geometry that needs recalculation.
        
        Args:
            widget: Widget to mark as dirty
        """
        if widget:
            self._dirty_regions.add(widget)
            # Remove from cache to force recalculation
            if widget in self._geometry_cache:
                del self._geometry_cache[widget]
    
    def update_cached_geometry(self, widget: QWidget) -> bool:
        """
        Update cached geometry for a specific widget during drag operations.
        
        Args:
            widget: Widget to update geometry for
            
        Returns:
            bool: True if geometry was updated, False otherwise
        """
        if not widget or not self._in_drag_operation:
            return False
            
        old_geometry = self._geometry_cache.get(widget)
        new_geometry = self.get_cached_geometry(widget)
        
        if new_geometry and old_geometry != new_geometry:
            self._geometry_cache[widget] = new_geometry
            # Remove from dirty regions since it's now updated
            if widget in self._dirty_regions:
                self._dirty_regions.remove(widget)
            return True
            
        return False
    
    def validate_window_geometries(self) -> bool:
        """
        Validate all cached window geometries and update if they've changed.
        This is useful after window manager repositioning.
        
        Returns:
            bool: True if any geometries were updated, False otherwise
        """
        if not self._cache_valid:
            return False
            
        geometries_updated = False
        windows_to_remove = []
        
        for window, (cached_rect, z_index) in list(self._window_rects.items()):
            try:
                if not window or not window.isVisible():
                    windows_to_remove.append(window)
                    continue
                    
                current_pos = window.mapToGlobal(QPoint(0, 0))
                current_rect = QRect(current_pos, window.size())
                
                # Check if geometry has changed significantly
                if (abs(current_rect.x() - cached_rect.x()) > 5 or 
                    abs(current_rect.y() - cached_rect.y()) > 5 or
                    abs(current_rect.width() - cached_rect.width()) > 5 or
                    abs(current_rect.height() - cached_rect.height()) > 5):
                    
                    self._window_rects[window] = (current_rect, z_index)
                    geometries_updated = True
                    
                    # Clear position cache to force recalculation
                    self._last_mouse_pos = None
                    self._last_hit_result = None
                    
            except RuntimeError:
                # Window was deleted
                windows_to_remove.append(window)
        
        # Remove invalid windows
        for window in windows_to_remove:
            if window in self._window_rects:
                del self._window_rects[window]
                geometries_updated = True
        
        return geometries_updated

    def get_geometry_cache_stats(self) -> dict:
        """
        Get statistics about the geometry cache for performance monitoring.
        
        Returns:
            dict: Cache statistics
        """
        return {
            'cached_geometries': len(self._geometry_cache),
            'dirty_regions': len(self._dirty_regions),
            'cache_hit_rate': len(self._geometry_cache) / max(1, len(self._geometry_cache) + len(self._dirty_regions))
        }