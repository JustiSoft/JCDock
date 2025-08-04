from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QPoint, QTimer, QMimeData, QRect
from PySide6.QtGui import QDrag, QPixmap, QPainter, QCursor, QPen, QBrush, QColor

from ..core.docking_state import DockingState
from ..model.dock_model import WidgetNode, TabGroupNode, SplitterNode
from ..widgets.dock_panel import DockPanel
from ..widgets.dock_container import DockContainer
from .drag_proxy import DragProxy


class DragDropController:
    """
    Handles all drag and drop operations for the docking system.
    Extracted from DockingManager to improve separation of concerns.
    """
    
    def __init__(self, manager):
        """
        Initialize with reference to DockingManager for coordination.
        
        Args:
            manager: Reference to the DockingManager instance
        """
        self.manager = manager
        self._overlay_update_timer = None
        self._pending_overlay_update = None
        self._drag_proxy = None

    def _debounced_overlay_update(self, required_overlays, final_target, final_location):
        """
        Debounced overlay update to prevent rapid creation/destruction cycles.
        Uses a timer to batch overlay updates during fast mouse movement.
        """
        from PySide6.QtCore import QTimer
        
        # Store the pending update
        self._pending_overlay_update = (required_overlays, final_target, final_location)
        
        # Cancel existing timer if running
        if self._overlay_update_timer:
            self._overlay_update_timer.stop()
            self._overlay_update_timer = None
        
        # Start new timer for debounced update
        self._overlay_update_timer = QTimer()
        self._overlay_update_timer.setSingleShot(True)
        self._overlay_update_timer.timeout.connect(self._apply_overlay_update)
        self._overlay_update_timer.start(16)  # ~60fps update rate
    
    def _apply_overlay_update(self):
        """
        Applies the pending overlay update after debounce timer expires.
        """
        if not self._pending_overlay_update:
            return
            
        required_overlays, final_target, final_location = self._pending_overlay_update
        self._pending_overlay_update = None
        
        # Apply the actual overlay updates
        current_overlays = set(self.manager.active_overlays)
        
        # Remove overlays no longer needed
        for w in (current_overlays - required_overlays):
            if not self.manager.is_deleted(w):
                w.hide_overlay()
            self.manager.active_overlays.remove(w)

        # Add new overlays needed
        for w in (required_overlays - current_overlays):
            try:
                if not self.manager.is_deleted(w):
                    if isinstance(w, DockContainer):
                        root_node = self.manager.model.roots.get(w)
                        is_empty = not (root_node and root_node.children)
                        is_main_dock_area = (w is self.manager.main_window if self.manager.main_window else False)
                        is_floating_root = (hasattr(w, 'is_main_window') and w.is_main_window) or self.manager._is_persistent_root(w)
                        if is_empty and (is_main_dock_area or is_floating_root):
                            w.show_overlay(preset='main_empty')
                        else:
                            w.show_overlay(preset='standard')
                    else:
                        w.show_overlay()
                    self.manager.active_overlays.append(w)
            except RuntimeError:
                if w in self.manager.active_overlays:
                    self.manager.active_overlays.remove(w)

        # Update preview overlays
        for overlay_widget in self.manager.active_overlays:
            if overlay_widget is final_target:
                overlay_widget.show_preview(final_location)
            else:
                overlay_widget.show_preview(None)

    def _create_drag_proxy(self, source_container):
        """
        Creates a drag proxy widget for the source container.
        
        Args:
            source_container: The container to create a proxy for
            
        Returns:
            DragProxy: The created proxy widget
        """
        if self._drag_proxy:
            self._cleanup_drag_proxy()
            
        self._drag_proxy = DragProxy(source_container)
        return self._drag_proxy
    
    def _update_drag_proxy_position(self, global_pos):
        """
        Updates the drag proxy position to follow the mouse.
        
        Args:
            global_pos: Current global mouse position
        """
        if self._drag_proxy:
            self._drag_proxy.update_position(global_pos)
    
    def _cleanup_drag_proxy(self):
        """
        Cleans up and destroys the current drag proxy.
        """
        if self._drag_proxy:
            self._drag_proxy.cleanup()
            self._drag_proxy.deleteLater()
            self._drag_proxy = None

    def _create_enhanced_drag_pixmap(self, tab_widget, tab_index, tab_rect):
        """
        Creates an enhanced drag pixmap with visual indicators for tab undocking.
        Shows the tab with a subtle window frame and shadow to indicate floating action.
        
        Args:
            tab_widget: The tab widget containing the tab
            tab_index: Index of the tab being dragged
            tab_rect: Rectangle of the tab
            
        Returns:
            QPixmap: Enhanced drag visual with floating window indicators
        """
        if tab_rect.isEmpty():
            return QPixmap()
            
        margin = 8
        enhanced_size = tab_rect.size()
        enhanced_size.setWidth(enhanced_size.width() + margin * 2)
        enhanced_size.setHeight(enhanced_size.height() + margin * 2)
        
        pixmap = QPixmap(enhanced_size)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        
        shadow_rect = QRect(margin + 2, margin + 2, tab_rect.width(), tab_rect.height())
        painter.fillRect(shadow_rect, QColor(0, 0, 0, 40))
        
        frame_rect = QRect(margin, margin, tab_rect.width(), tab_rect.height())
        frame_pen = QPen(QColor(100, 150, 200, 180), 2)
        painter.setPen(frame_pen)
        painter.drawRect(frame_rect)
        
        painter.setOpacity(0.8)
        tab_widget.tabBar().render(painter, QPoint(margin, margin), tab_rect)
        
        painter.setOpacity(1.0)
        indicator_size = 12
        indicator_rect = QRect(frame_rect.right() - indicator_size - 2, 
                             frame_rect.top() + 2, 
                             indicator_size, 
                             indicator_size)
        
        painter.setPen(QPen(QColor(60, 120, 180), 2))
        painter.setBrush(QBrush(QColor(240, 240, 240, 200)))
        painter.drawRect(indicator_rect)
        
        title_bar_rect = QRect(indicator_rect.x(), indicator_rect.y(), 
                              indicator_rect.width(), 3)
        painter.fillRect(title_bar_rect, QColor(60, 120, 180))
        
        painter.end()
        return pixmap

    def handle_live_move(self, source_container, event):
        """
        Core live move handler that shows overlays during window movement.
        
        Args:
            source_container: The container being moved
            event: The mouse move event
        """
        if self.manager._is_persistent_root(source_container):
            return
        
        if self.manager.is_rendering():
            return
            
        # Increment drag operation counter
        self.manager.performance_monitor.increment_counter('drag_operations')
            
        if self.manager.state != DockingState.DRAGGING_WINDOW:
            if hasattr(source_container, 'title_bar') and source_container.title_bar and source_container.title_bar.moving:
                self.manager._set_state(DockingState.DRAGGING_WINDOW)
                self.manager.hit_test_cache.set_drag_operation_state(True, source_container)
                
                # Just-in-time cache rebuild: ensure cache is valid before starting drag
                if not self.manager.hit_test_cache.is_cache_valid():
                    self.manager.hit_test_cache.build_cache(self.manager.window_stack, self.manager.containers)
                
                # Create and show drag proxy
                self._create_drag_proxy(source_container)
                if self._drag_proxy:
                    # Hide the original container during drag
                    source_container.setWindowOpacity(0.1)  # Nearly invisible
                    self._drag_proxy.show_proxy()
            else:
                return
        
        if not (hasattr(source_container, 'title_bar') and source_container.title_bar and source_container.title_bar.moving):
            return

        if hasattr(source_container, 'is_main_window') and source_container.is_main_window:
            self.manager.destroy_all_overlays()
            self.manager.last_dock_target = None
            return

        global_mouse_pos = event.globalPosition().toPoint()

        # Update drag proxy position
        self._update_drag_proxy_position(global_mouse_pos)

        tab_bar_info = self.manager.hit_test_cache.find_tab_bar_at_position(global_mouse_pos)
        if tab_bar_info:
            tab_bar = tab_bar_info.tab_widget.tabBar()
            local_pos = tab_bar.mapFromGlobal(global_mouse_pos)
            drop_index = tab_bar.get_drop_index(local_pos)

            if drop_index != -1:
                self.manager.destroy_all_overlays()
                tab_bar.set_drop_indicator_index(drop_index)
                self.manager.last_dock_target = (tab_bar_info.tab_widget, "insert", drop_index)
                
                if hasattr(source_container, 'set_drag_transparency'):
                    source_container.set_drag_transparency(0.4)
                return
            else:
                tab_bar.set_drop_indicator_index(-1)
                if hasattr(source_container, 'restore_normal_opacity'):
                    source_container.restore_normal_opacity()

        cached_target = self.manager.hit_test_cache.find_drop_target_at_position(global_mouse_pos, source_container)
        target_widget = cached_target.widget if cached_target else None

        required_overlays = set()
        if target_widget and target_widget is not source_container:
            target_name = getattr(target_widget, 'objectName', lambda: f"{type(target_widget).__name__}@{id(target_widget)}")()
            
            if isinstance(target_widget, DockContainer):
                source_has_simple_layout = self.manager.has_simple_layout(source_container)
                target_has_simple_layout = self.manager.has_simple_layout(target_widget)
                
                if not source_has_simple_layout or not target_has_simple_layout:
                    required_overlays.add(target_widget)
            else:
                required_overlays.add(target_widget)
            parent_container = getattr(target_widget, 'parent_container', None)
            if parent_container and parent_container is not source_container:
                target_has_complex_layout = not self.manager.has_simple_layout(parent_container)
                source_has_simple_layout = self.manager.has_simple_layout(source_container)
                
                if target_has_complex_layout or not source_has_simple_layout:
                    required_overlays.add(parent_container)

        # Determine final target and location
        final_target = None
        final_location = None
        if target_widget:
            location = target_widget.get_dock_location(global_mouse_pos)
            if location:
                final_target = target_widget
                final_location = location
            else:
                parent_container = getattr(target_widget, 'parent_container', None)
                if parent_container:
                    parent_location = parent_container.get_dock_location(global_mouse_pos)
                    if parent_location:
                        final_target = parent_container
                        final_location = parent_location

        # Use debounced overlay update to prevent flashing
        self.manager.performance_monitor.increment_counter('overlay_updates')
        self._debounced_overlay_update(required_overlays, final_target, final_location)

        self.manager.last_dock_target = (final_target, final_location) if (final_target and final_location) else None
        
        if not (tab_bar_info and tab_bar_info.tab_widget.tabBar().get_drop_index(tab_bar_info.tab_widget.tabBar().mapFromGlobal(global_mouse_pos)) != -1):
            if hasattr(source_container, 'restore_normal_opacity'):
                source_container.restore_normal_opacity()

    def finalize_dock_from_live_move(self, source_container, dock_target_info):
        """
        Completes the docking operation from live window movement.
        
        Args:
            source_container: The container that was being moved
            dock_target_info: Information about where to dock
        """
        try:
            # Clean up drag proxy and restore container visibility
            self._cleanup_drag_proxy()
            source_container.setWindowOpacity(1.0)  # Restore full opacity
            
            if hasattr(source_container, 'restore_normal_opacity'):
                source_container.restore_normal_opacity()
            
            if self.manager._is_persistent_root(source_container):
                print(f"WARNING: Attempted to move persistent root {source_container}. Operation blocked.")
                self.manager.destroy_all_overlays()
                return
            
            self.manager.destroy_all_overlays()
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()
            
            source_root_node = self.manager.model.roots.get(source_container)
            if not source_root_node:
                print(f"ERROR: No root node found for source container {source_container}")
                return
                
            if len(dock_target_info) == 3:
                self.manager._finalize_tab_insertion(source_container, source_root_node, dock_target_info)
            elif len(dock_target_info) == 2:
                self.manager._finalize_regular_docking(source_container, source_root_node, dock_target_info)
                    
        except Exception as e:
            print(f"Error during dock finalization: {e}")
            self.manager.destroy_all_overlays()

    def start_tab_drag_operation(self, widget_persistent_id: str):
        """
        Initiates a Qt-native drag operation for a tab with the given persistent ID.
        
        Args:
            widget_persistent_id: The persistent ID of the widget to drag
        """
        self.manager.destroy_all_overlays()
        
        self.manager.hit_test_cache.build_cache(self.manager.window_stack, self.manager.containers)
        
        widget_to_drag = self.manager.find_widget_by_id(widget_persistent_id)
        if not widget_to_drag:
            print(f"ERROR: Widget with ID '{widget_persistent_id}' not found")
            return

        tab_widget, tab_index = self._find_tab_widget_for_widget(widget_to_drag)
        if not tab_widget or tab_index == -1:
            print(f"ERROR: Could not find tab widget for widget '{widget_persistent_id}'")
            return

        original_tab_text = tab_widget.tabText(tab_index)
        original_tab_enabled = tab_widget.isTabEnabled(tab_index)
        original_tab_icon = tab_widget.tabIcon(tab_index)
        
        tab_widget.setTabEnabled(tab_index, False)
        tab_widget.setTabText(tab_index, f"[Dragging] {original_tab_text}")

        drag = QDrag(tab_widget)
        
        mime_data = QMimeData()
        mime_data.setData("application/x-jcdock-widget", widget_persistent_id.encode('utf-8'))
        drag.setMimeData(mime_data)

        tab_rect = tab_widget.tabBar().tabRect(tab_index)
        if not tab_rect.isEmpty():
            pixmap = self._create_enhanced_drag_pixmap(tab_widget, tab_index, tab_rect)
            
            drag.setPixmap(pixmap)
            margin = 8
            drag.setHotSpot(QPoint(tab_rect.width() // 2 + margin, tab_rect.height() // 2 + margin))

        self.manager._drag_source_id = widget_persistent_id
        
        self.manager._set_state(DockingState.DRAGGING_TAB)
        
        try:
            drop_action = drag.exec(Qt.MoveAction)
        finally:
            self.manager._set_state(DockingState.IDLE)
            self.manager._drag_source_id = None
            QApplication.processEvents()
            self.manager.hit_test_cache.invalidate()

        if drop_action == Qt.MoveAction:
            pass
        else:
            tab_widget.setTabEnabled(tab_index, original_tab_enabled)
            tab_widget.setTabText(tab_index, original_tab_text)
            tab_widget.setTabIcon(tab_index, original_tab_icon)

            if drop_action == Qt.IgnoreAction:
                cursor_pos = QCursor.pos()
                self._create_floating_window_from_drag(widget_to_drag, cursor_pos)

    def dock_widget_from_drag(self, widget_persistent_id: str, target_entity, dock_location: str):
        """
        Handles widget docking from drag operations.
        
        Args:
            widget_persistent_id: ID of the widget being dragged
            target_entity: Target for docking
            dock_location: Where to dock relative to target
            
        Returns:
            bool: True if successful, False otherwise
        """
        widget_to_move = self.manager.find_widget_by_id(widget_persistent_id)
        if not widget_to_move:
            print(f"ERROR: Widget with ID '{widget_persistent_id}' not found")
            return False

        source_removed = False
        host_tab_group, host_parent_node, root_window = self.manager.model.find_host_info(widget_to_move)
        
        if host_tab_group and host_parent_node:
            widget_node_to_remove = next((wn for wn in host_tab_group.children if wn.widget is widget_to_move), None)
            if widget_node_to_remove:
                host_tab_group.children.remove(widget_node_to_remove)
                source_removed = True
                
                if root_window and root_window in self.manager.model.roots:
                    self.manager._simplify_model(root_window)
                    if root_window in self.manager.model.roots:
                        self.manager._render_layout(root_window)
                    else:
                        root_window.update_dynamic_title()

        if source_removed:
            widget_node = WidgetNode(widget_to_move)
            tab_group_node = TabGroupNode(children=[widget_node])
            self.manager.model.roots[widget_to_move] = tab_group_node
            
            widget_to_move.parent_container = None

        try:
            self.manager.dock_widget(widget_to_move, target_entity, dock_location)
            return True
        except Exception as e:
            print(f"ERROR: Failed to dock widget during drag operation: {e}")
            if source_removed and widget_to_move in self.manager.model.roots:
                self.manager.model.unregister_widget(widget_to_move)
            return False

    def handle_qdrag_move(self, global_mouse_pos):
        """
        Centralized drag handling for QDrag operations.
        Uses the existing hit-testing system to show overlays on appropriate targets.
        
        Args:
            global_mouse_pos: Current global mouse position
        """
        tab_bar_info = self.manager.hit_test_cache.find_tab_bar_at_position(global_mouse_pos)
        if tab_bar_info:
            tab_bar = tab_bar_info.tab_widget.tabBar()
            local_pos = tab_bar.mapFromGlobal(global_mouse_pos)
            drop_index = tab_bar.get_drop_index(local_pos)

            if drop_index != -1:
                self.manager.destroy_all_overlays()
                tab_bar.set_drop_indicator_index(drop_index)
                self.manager.last_dock_target = (tab_bar_info.tab_widget, "insert", drop_index)
                return
            else:
                tab_bar.set_drop_indicator_index(-1)

        excluded_widget = None
        if self.manager._drag_source_id:
            excluded_widget = self.manager.find_widget_by_id(self.manager._drag_source_id)
        
        cached_target = self.manager.hit_test_cache.find_drop_target_at_position(global_mouse_pos, excluded_widget)
        target_widget = cached_target.widget if cached_target else None
        required_overlays = set()
        if target_widget and target_widget is not excluded_widget:
            target_name = getattr(target_widget, 'objectName', lambda: f"{type(target_widget).__name__}@{id(target_widget)}")()
            
            if isinstance(target_widget, DockContainer):
                source_has_simple_layout = self.manager.has_simple_layout(excluded_widget) if excluded_widget else False
                target_has_simple_layout = self.manager.has_simple_layout(target_widget)
                
                if not source_has_simple_layout or not target_has_simple_layout:
                    required_overlays.add(target_widget)
            else:
                required_overlays.add(target_widget)
            parent_container = getattr(target_widget, 'parent_container', None)
            if parent_container and parent_container is not excluded_widget:
                target_has_complex_layout = not self.manager.has_simple_layout(parent_container)
                source_has_simple_layout = self.manager.has_simple_layout(excluded_widget) if excluded_widget else False
                
                if target_has_complex_layout or not source_has_simple_layout:
                    required_overlays.add(parent_container)

        current_overlays = set(self.manager.active_overlays)
        
        for w in (current_overlays - required_overlays):
            if not self.manager.is_deleted(w):
                w.hide_overlay()
            self.manager.active_overlays.remove(w)

        for w in (required_overlays - current_overlays):
            if not self.manager.is_deleted(w):
                if hasattr(w, 'show_overlay'):
                    if isinstance(w, DockContainer):
                        w.show_overlay()
                    else:
                        w.show_overlay()
            self.manager.active_overlays.append(w)

        for w in required_overlays:
            if not self.manager.is_deleted(w):
                if hasattr(w, 'update_overlay_position'):
                    w.update_overlay_position(global_mouse_pos)

        if target_widget:
            self.manager.last_dock_target = (target_widget, "center", None)
        else:
            self.manager.last_dock_target = None

    def undock_single_widget_by_tear(self, widget_to_undock: DockPanel, global_mouse_pos: QPoint):
        """
        Handles tab tear-out operations to create floating windows.
        
        Args:
            widget_to_undock: The widget to undock
            global_mouse_pos: Current mouse position for window placement
        """
        # Use the unified undocking core from the manager
        from ..core.docking_manager import MousePositionStrategy
        
        positioning_strategy = MousePositionStrategy()
        context = {'global_mouse_pos': global_mouse_pos}
        
        newly_floated_window = self.manager._perform_undock_operation(widget_to_undock, positioning_strategy, context)
        
        if newly_floated_window:
            # Additional processing specific to drag operations
            self.manager.signals.layout_changed.emit()
        
        return newly_floated_window

    def _create_floating_window_from_drag(self, widget, cursor_pos):
        """
        Creates a new floating window at the cursor position during drag operations.
        Matches the original behavior by first removing the widget from its current container.
        
        Args:
            widget: The DockPanel to put in the floating window
            cursor_pos: Position for the new window
            
        Returns:
            DockContainer: The newly created floating window
        """
        if self.manager.is_widget_docked(widget):
            host_tab_group, parent_node, root_window = self.manager.model.find_host_info(widget)
            if host_tab_group:
                widget_node_to_remove = next((wn for wn in host_tab_group.children if wn.widget is widget), None)
                if widget_node_to_remove:
                    host_tab_group.children.remove(widget_node_to_remove)
                    
                    if root_window and root_window in self.manager.model.roots:
                        self.manager.layout_renderer.simplify_model(root_window)
                        if root_window in self.manager.model.roots:
                            self.manager.layout_renderer.render_layout(root_window)
                            root_window.update()
                            root_window.repaint()
                            from PySide6.QtWidgets import QApplication
                            QApplication.processEvents()
                        else:
                            root_window.update_dynamic_title()
        
        from PySide6.QtCore import QSize, QRect, QPoint
        widget_size = widget.content_container.size() if widget.content_container.size().isValid() else QSize(350, 250)
        title_height = 30
        
        window_pos = cursor_pos - QPoint(widget_size.width() // 2, title_height // 2)
        window_geometry = QRect(window_pos, widget_size + QSize(0, title_height))
        
        window_geometry = self.manager._validate_window_geometry(window_geometry)
        
        floating_window = self.manager._create_floating_window([widget], window_geometry)
        
        if floating_window:
            self.manager.signals.widget_undocked.emit(widget)
            self.manager.signals.layout_changed.emit()
            
            floating_window.show()
            floating_window.raise_()
            floating_window.activateWindow()
            
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()
            
            from PySide6.QtCore import QTimer
            QTimer.singleShot(100, self.manager._refresh_all_container_titles)
        
        return floating_window

    def _find_tab_widget_for_widget(self, widget):
        """
        Locates the QTabWidget containing a specific widget.
        
        Args:
            widget: The DockPanel to find
            
        Returns:
            tuple: (QTabWidget, tab_index) or (None, -1) if not found
        """
        for container in self.manager.containers:
            if self.manager.is_deleted(container):
                continue
            
            from PySide6.QtWidgets import QTabWidget
            tab_widgets = container.findChildren(QTabWidget)
            for tab_widget in tab_widgets:
                for i in range(tab_widget.count()):
                    if tab_widget.widget(i) is widget.content_container:
                        return tab_widget, i
        
        return None, -1

    def _finalize_regular_docking(self, source_container, source_root_node, dock_target_info):
        """
        Handles docking to create new splitter arrangements.
        
        Args:
            source_container: Container being moved
            source_root_node: Source layout node
            dock_target_info: Target information
        """
        target_widget, dock_location, extra_data = dock_target_info
        
        if hasattr(target_widget, 'parent_container') and target_widget.parent_container:
            target_container = target_widget.parent_container
        elif isinstance(target_widget, DockContainer):
            target_container = target_widget
        else:
            return

        if target_container not in self.manager.model.roots:
            return
            
        target_root_node = self.manager.model.roots[target_container]

        self.manager._dock_to_floating_widget_with_nodes(
            source_container, source_root_node, target_widget, dock_location)

    def _finalize_tab_insertion(self, source_container, source_root_node, dock_target_info):
        """
        Handles insertion into existing tab groups.
        
        Args:
            source_container: Container being moved
            source_root_node: Source layout node
            dock_target_info: Target information including insertion index
        """
        target_tab_widget, dock_location, insert_index = dock_target_info
        
        target_container = None
        for container in self.manager.containers:
            if hasattr(container, 'tearable_tab_widget') and container.tearable_tab_widget is target_tab_widget:
                target_container = container
                break
        
        if not target_container:
            return
            
        self._finalize_regular_docking(source_container, source_root_node, 
                                     (target_container, "center", None))