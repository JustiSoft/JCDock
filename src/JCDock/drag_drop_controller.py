from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QPoint, QTimer, QMimeData
from PySide6.QtGui import QDrag, QPixmap, QPainter, QCursor

from .docking_state import DockingState
from .dock_model import WidgetNode, TabGroupNode, SplitterNode
from .dock_panel import DockPanel
from .dock_container import DockContainer


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

    def handle_live_move(self, source_container, event):
        """
        Core live move handler that shows overlays during window movement.
        
        Args:
            source_container: The container being moved
            event: The mouse move event
        """
        # CRITICAL FIX: Prevent dragging persistent roots
        if self.manager._is_persistent_root(source_container):
            return  # Block all dragging of persistent roots
        
        # Safety checks - don't show overlays during critical operations
        if self.manager.is_rendering():
            return
            
        # Assert we're in the correct state - the state machine should guarantee this
        assert self.manager.state == DockingState.DRAGGING_WINDOW, f"handle_live_move called in wrong state: {self.manager.state}"
        assert hasattr(source_container, 'title_bar') and source_container.title_bar and source_container.title_bar.moving, "handle_live_move called without proper moving state"

        if isinstance(source_container, self.manager.FloatingDockRoot if hasattr(self.manager, 'FloatingDockRoot') else type(None)):
            self.manager.destroy_all_overlays()
            self.manager.last_dock_target = None
            return

        # Get the global mouse position from the event
        global_mouse_pos = event.globalPosition().toPoint()

        # Step 1: Check for tab bar insertion first (highest priority)
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

        # Step 2: Find the drop target using cached data
        # Call HitTestCache with source_container as excluded_widget
        cached_target = self.manager.hit_test_cache.find_drop_target_at_position(global_mouse_pos, source_container)
        target_widget = cached_target.widget if cached_target else None

        # Step 3: Update overlay visibility based on target
        required_overlays = set()
        if target_widget:
            target_name = getattr(target_widget, 'objectName', lambda: f"{type(target_widget).__name__}@{id(target_widget)}")()
            
            # Check if target_widget itself is a container that should be filtered out
            if isinstance(target_widget, DockContainer):
                source_has_simple_layout = self.manager.has_simple_layout(source_container)
                target_has_simple_layout = self.manager.has_simple_layout(target_widget)
                
                # Only add container target if either source or target has complex layout
                if not source_has_simple_layout or not target_has_simple_layout:
                    required_overlays.add(target_widget)
            else:
                required_overlays.add(target_widget)
            parent_container = getattr(target_widget, 'parent_container', None)
            if parent_container:
                # Only add container overlay for complex layouts
                # Don't show container overlay only when BOTH source AND target have simple layouts
                target_has_complex_layout = not self.manager.has_simple_layout(parent_container)
                source_has_simple_layout = self.manager.has_simple_layout(source_container)
                
                # Show container overlay if target is complex OR source is complex (but not if both are simple)
                if target_has_complex_layout or not source_has_simple_layout:
                    required_overlays.add(parent_container)

        current_overlays = set(self.manager.active_overlays)
        
        # Hide overlays no longer needed
        for w in (current_overlays - required_overlays):
            if not self.manager.is_deleted(w):
                w.hide_overlay()
            self.manager.active_overlays.remove(w)

        # Show overlays for new targets
        for w in (required_overlays - current_overlays):
            try:
                if not self.manager.is_deleted(w):
                    if isinstance(w, DockContainer):
                        root_node = self.manager.model.roots.get(w)
                        is_empty = not (root_node and root_node.children)
                        is_main_dock_area = (w is (self.manager.main_window.dock_area if self.manager.main_window else None))
                        # Import FloatingDockRoot dynamically to avoid circular import
                        from .floating_dock_root import FloatingDockRoot
                        is_floating_root = isinstance(w, FloatingDockRoot)
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

        # Step 4: Determine final docking location
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

        # Step 5: Update overlay previews
        for overlay_widget in self.manager.active_overlays:
            if overlay_widget is final_target:
                overlay_widget.show_preview(final_location)
            else:
                overlay_widget.show_preview(None)

        # Store the result in self.last_dock_target
        self.manager.last_dock_target = (final_target, final_location) if (final_target and final_location) else None

    def finalize_dock_from_live_move(self, source_container, dock_target_info):
        """
        Completes the docking operation from live window movement.
        
        Args:
            source_container: The container that was being moved
            dock_target_info: Information about where to dock
        """
        try:
            # CRITICAL FIX: Prevent moving persistent roots or containers that are part of persistent roots
            if self.manager._is_persistent_root(source_container):
                print(f"WARNING: Attempted to move persistent root {source_container}. Operation blocked.")
                self.manager.destroy_all_overlays()
                return
            
            # Clean up any remaining overlays first
            self.manager.destroy_all_overlays()
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()  # Force immediate overlay cleanup
            
            # Get the root_node from the source_container
            source_root_node = self.manager.model.roots.get(source_container)
            if not source_root_node:
                print(f"ERROR: No root node found for source container {source_container}")
                return
                
            # Handle different types of dock targets
            if len(dock_target_info) == 3:
                # Tab insertion: (tab_widget, "insert", drop_index)
                self.manager._finalize_tab_insertion(source_container, source_root_node, dock_target_info)
            elif len(dock_target_info) == 2:
                # Regular docking: (target_widget, location)
                self.manager._finalize_regular_docking(source_container, source_root_node, dock_target_info)
                    
        except Exception as e:
            print(f"Error during dock finalization: {e}")
            # Ensure overlays are cleaned up even if docking fails
            self.manager.destroy_all_overlays()

    def start_tab_drag_operation(self, widget_persistent_id: str):
        """
        Initiates a Qt-native drag operation for a tab with the given persistent ID.
        
        Args:
            widget_persistent_id: The persistent ID of the widget to drag
        """
        # Clean up any existing overlays before starting tab drag operation
        self.manager.destroy_all_overlays()
        
        # Build the cache at the very beginning to capture current UI layout
        self.manager.hit_test_cache.build_cache(self.manager.window_stack, self.manager.containers)
        
        widget_to_drag = self.manager.find_widget_by_id(widget_persistent_id)
        if not widget_to_drag:
            print(f"ERROR: Widget with ID '{widget_persistent_id}' not found")
            return

        # Find the tab widget and tab index for this widget
        tab_widget, tab_index = self._find_tab_widget_for_widget(widget_to_drag)
        if not tab_widget or tab_index == -1:
            print(f"ERROR: Could not find tab widget for widget '{widget_persistent_id}'")
            return

        # Store the original tab state
        original_tab_text = tab_widget.tabText(tab_index)
        original_tab_enabled = tab_widget.isTabEnabled(tab_index)
        
        # Temporarily hide/disable the tab
        tab_widget.setTabEnabled(tab_index, False)
        tab_widget.setTabText(tab_index, f"[Dragging] {original_tab_text}")

        # Create QDrag object
        drag = QDrag(tab_widget)
        
        # Create MIME data with the widget's persistent ID
        mime_data = QMimeData()
        mime_data.setData("application/x-jcdock-widget", widget_persistent_id.encode('utf-8'))
        drag.setMimeData(mime_data)

        # Create a pixmap of the tab for visual feedback
        tab_rect = tab_widget.tabBar().tabRect(tab_index)
        if not tab_rect.isEmpty():
            pixmap = QPixmap(tab_rect.size())
            pixmap.fill(Qt.transparent)
            
            painter = QPainter(pixmap)
            painter.setOpacity(0.7)  # Semi-transparent
            tab_widget.tabBar().render(painter, QPoint(0, 0), tab_rect)
            painter.end()
            
            drag.setPixmap(pixmap)
            drag.setHotSpot(QPoint(tab_rect.width() // 2, tab_rect.height() // 2))

        # Set the drag source ID for hit-testing exclusion
        self.manager._drag_source_id = widget_persistent_id
        
        # Set state to indicate native Qt drag operation is in progress
        self.manager._set_state(DockingState.DRAGGING_TAB)
        
        try:
            # Execute the drag operation (this blocks until drag is complete)
            # Only support Move action to prevent external application drops
            drop_action = drag.exec(Qt.MoveAction)
        finally:
            # Always return to idle state when drag operation ends
            self.manager._set_state(DockingState.IDLE)
            # Always reset the drag source ID when drag operation ends
            self.manager._drag_source_id = None
            # Force UI to stable state and invalidate cache since layout may have changed
            QApplication.processEvents()
            self.manager.hit_test_cache.invalidate()

        # Handle the result
        if drop_action == Qt.MoveAction:
            # Successful drop - the dropEvent handler will have processed the move
            pass
        else:
            # Drag was cancelled or dropped in invalid area
            # Restore the original tab state
            tab_widget.setTabEnabled(tab_index, original_tab_enabled)
            tab_widget.setTabText(tab_index, original_tab_text)

            # If dropped outside any valid drop target, create floating window
            if drop_action == Qt.IgnoreAction:
                # Get final cursor position for floating window
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

        # Find and remove the widget from its current location
        source_removed = False
        host_tab_group, host_parent_node, root_window = self.manager.model.find_host_info(widget_to_move)
        
        if host_tab_group and host_parent_node:
            # Remove the widget from its current tab group
            widget_node_to_remove = next((wn for wn in host_tab_group.children if wn.widget is widget_to_move), None)
            if widget_node_to_remove:
                host_tab_group.children.remove(widget_node_to_remove)
                source_removed = True
                
                # Simplify and re-render the source container
                if root_window and root_window in self.manager.model.roots:
                    self.manager._simplify_model(root_window)
                    if root_window in self.manager.model.roots:
                        self.manager._render_layout(root_window)
                    else:
                        # If container was removed from roots, still update its title
                        root_window.update_dynamic_title()

        # Now create a temporary floating state for the widget so dock_widget can find it
        if source_removed:
            # Create a temporary root entry for the widget
            widget_node = WidgetNode(widget_to_move)
            tab_group_node = TabGroupNode(children=[widget_node])
            self.manager.model.roots[widget_to_move] = tab_group_node
            
            # Reset parent container since it's now floating
            widget_to_move.parent_container = None

        # Now perform the docking operation
        try:
            self.manager.dock_widget(widget_to_move, target_entity, dock_location)
            return True
        except Exception as e:
            print(f"ERROR: Failed to dock widget during drag operation: {e}")
            # If docking failed and we removed it from source, try to restore it
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
        # Step 1: Check for tab bar insertion first (highest priority)
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

        # Step 2: Find the drop target using cached data
        # Get the source widget being dragged to exclude it from hit-testing
        excluded_widget = None
        if self.manager._drag_source_id:
            excluded_widget = self.manager.find_widget_by_id(self.manager._drag_source_id)
        
        cached_target = self.manager.hit_test_cache.find_drop_target_at_position(global_mouse_pos, excluded_widget)
        target_widget = cached_target.widget if cached_target else None

        # Step 3: Update overlay visibility based on target
        required_overlays = set()
        if target_widget:
            target_name = getattr(target_widget, 'objectName', lambda: f"{type(target_widget).__name__}@{id(target_widget)}")()
            
            # Check if target_widget itself is a container that should be filtered out
            if isinstance(target_widget, DockContainer):
                source_has_simple_layout = self.manager.has_simple_layout(excluded_widget) if excluded_widget else False
                target_has_simple_layout = self.manager.has_simple_layout(target_widget)
                
                # Only add container target if either source or target has complex layout
                if not source_has_simple_layout or not target_has_simple_layout:
                    required_overlays.add(target_widget)
            else:
                required_overlays.add(target_widget)
            parent_container = getattr(target_widget, 'parent_container', None)
            if parent_container:
                # Only add container overlay for complex layouts
                # Don't show container overlay only when BOTH source AND target have simple layouts
                target_has_complex_layout = not self.manager.has_simple_layout(parent_container)
                source_has_simple_layout = self.manager.has_simple_layout(excluded_widget) if excluded_widget else False
                
                # Show container overlay if target is complex OR source is complex (but not if both are simple)
                if target_has_complex_layout or not source_has_simple_layout:
                    required_overlays.add(parent_container)

        current_overlays = set(self.manager.active_overlays)
        
        # Hide overlays no longer needed
        for w in (current_overlays - required_overlays):
            if not self.manager.is_deleted(w):
                w.hide_overlay()
            self.manager.active_overlays.remove(w)

        # Show overlays that are now needed
        for w in (required_overlays - current_overlays):
            if not self.manager.is_deleted(w):
                if hasattr(w, 'show_overlay'):
                    if isinstance(w, DockContainer):
                        w.show_overlay()  # DockContainer.show_overlay() takes no position parameter
                    else:
                        w.show_overlay()  # DockPanel.show_overlay() takes no parameters
            self.manager.active_overlays.append(w)

        # Update positions of all active overlays
        for w in required_overlays:
            if not self.manager.is_deleted(w):
                if hasattr(w, 'update_overlay_position'):
                    w.update_overlay_position(global_mouse_pos)

        # Store the target for potential drop
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
        # Clean up any existing overlays
        self.manager.destroy_all_overlays()
        
        # Find the widget's current location
        host_tab_group, host_parent_node, root_window = self.manager.model.find_host_info(widget_to_undock)
        
        if not (host_tab_group and host_parent_node and root_window):
            print("ERROR: Could not find widget location for tear operation")
            return None

        # Remove the widget from its current tab group
        widget_node_to_remove = next((wn for wn in host_tab_group.children if wn.widget is widget_to_undock), None)
        if not widget_node_to_remove:
            print("ERROR: Could not find widget node in tab group")
            return None

        host_tab_group.children.remove(widget_node_to_remove)

        # Simplify the source model
        self.manager._simplify_model(root_window)
        
        # Re-render the source container if it still exists
        if root_window in self.manager.model.roots:
            self.manager._render_layout(root_window)

        # Create floating window for the undocked widget
        floating_window = self._create_floating_window_from_drag(widget_to_undock, global_mouse_pos)
        
        # Emit signals
        self.manager.signals.widget_undocked.emit(widget_to_undock)
        self.manager.signals.layout_changed.emit()
        
        return floating_window

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
        # First, remove the widget from its current location if it's docked
        if self.manager.is_widget_docked(widget):
            host_tab_group, parent_node, root_window = self.manager.model.find_host_info(widget)
            if host_tab_group:
                # Remove the widget from its current tab group
                widget_node_to_remove = next((wn for wn in host_tab_group.children if wn.widget is widget), None)
                if widget_node_to_remove:
                    host_tab_group.children.remove(widget_node_to_remove)
                    
                    # Simplify and re-render the source container
                    if root_window and root_window in self.manager.model.roots:
                        self.manager.layout_renderer.simplify_model(root_window)
                        if root_window in self.manager.model.roots:
                            self.manager.layout_renderer.render_layout(root_window)
                            # Force visual refresh after layout rendering
                            root_window.update()
                            root_window.repaint()
                            from PySide6.QtWidgets import QApplication
                            QApplication.processEvents()
                        else:
                            # If container was removed from roots, still update its title
                            root_window.update_dynamic_title()
        
        # Calculate geometry for new floating window
        from PySide6.QtCore import QSize, QRect, QPoint
        widget_size = widget.content_container.size() if widget.content_container.size().isValid() else QSize(350, 250)
        title_height = 30  # Approximate title bar height
        
        # Position the window so the cursor is on the title bar
        window_pos = cursor_pos - QPoint(widget_size.width() // 2, title_height // 2)
        window_geometry = QRect(window_pos, widget_size + QSize(0, title_height))
        
        # Validate geometry
        window_geometry = self.manager._validate_window_geometry(window_geometry)
        
        # Use the existing create_floating_window method
        floating_window = self.manager.create_floating_window([widget], window_geometry)
        
        if floating_window:
            # Emit signals for the undocking and layout change
            self.manager.signals.widget_undocked.emit(widget)
            self.manager.signals.layout_changed.emit()
            
            # Schedule a delayed title refresh for all containers to ensure visual consistency
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
        # Use the comprehensive approach that searches all containers
        for container in self.manager.containers:
            if self.manager.is_deleted(container):
                continue
            
            # Use findChildren to get all QTabWidget instances in the container
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
        
        # Determine target container
        if hasattr(target_widget, 'parent_container') and target_widget.parent_container:
            target_container = target_widget.parent_container
        elif isinstance(target_widget, DockContainer):
            target_container = target_widget
        else:
            return

        # Get target node
        if target_container not in self.manager.model.roots:
            return
            
        target_root_node = self.manager.model.roots[target_container]

        # Perform the docking using the model
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
        
        # Find the container that hosts this tab widget
        target_container = None
        for container in self.manager.containers:
            if hasattr(container, 'tearable_tab_widget') and container.tearable_tab_widget is target_tab_widget:
                target_container = container
                break
        
        if not target_container:
            return
            
        # Handle tab insertion logic here
        # This would involve updating the model to insert at the specific index
        # For now, fall back to regular docking
        self._finalize_regular_docking(source_container, source_root_node, 
                                     (target_container, "center", None))