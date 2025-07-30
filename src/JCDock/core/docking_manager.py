import pickle

from PySide6.QtWidgets import QWidget, QTabWidget, QApplication
from PySide6.QtCore import Qt, QRect, QEvent, QPoint, QRectF, QSize, QTimer, Signal, QObject, QMimeData
from PySide6.QtGui import QColor, QDrag, QPixmap, QPainter, QCursor

from .docking_state import DockingState
from ..widgets.floating_dock_root import FloatingDockRoot
from ..widgets.main_dock_window import MainDockWindow
from ..model.dock_model import LayoutModel, AnyNode, SplitterNode, TabGroupNode, WidgetNode
from ..widgets.dock_panel import DockPanel
from ..widgets.dock_container import DockContainer
from ..utils.hit_test_cache import HitTestCache
from ..utils.performance_monitor import PerformanceMonitor
from ..model.layout_serializer import LayoutSerializer
from ..interaction.drag_drop_controller import DragDropController
from ..model.layout_renderer import LayoutRenderer
from ..factories.widget_factory import WidgetFactory
from ..factories.window_manager import WindowManager
from ..interaction.overlay_manager import OverlayManager
from ..factories.model_update_engine import ModelUpdateEngine
from .widget_registry import get_registry

class DockingSignals(QObject):
    """
    A collection of signals to allow applications to react to layout changes.
    """
    widget_docked = Signal(object, object)

    widget_undocked = Signal(object)

    widget_closed = Signal(str)

    layout_changed = Signal()

class DockingManager(QObject):
    def __init__(self):
        super().__init__()
        self.widgets = []
        self.containers = []
        self.last_dock_target = None
        self.model = LayoutModel()
        self.active_overlays = []
        self.main_window = None
        self.window_stack = []
        self.floating_widget_count = 0
        self.debug_mode = False
        self.signals = DockingSignals()
        
        self.state = DockingState.IDLE
        
        self._is_updating_focus = False
        self.hit_test_cache = HitTestCache()
        self._drag_source_id = None
        self.performance_monitor = PerformanceMonitor()
        
        self.layout_serializer = LayoutSerializer(self)
        self.drag_drop_controller = DragDropController(self)
        self.layout_renderer = LayoutRenderer(self)
        self.widget_factory = WidgetFactory(self)
        self.window_manager = WindowManager(self)
        self.overlay_manager = OverlayManager(self)
        self.model_update_engine = ModelUpdateEngine(self)
        
        # Connect performance monitor to hit test cache
        self.hit_test_cache.set_performance_monitor(self.performance_monitor)
        
        if self.debug_mode:
            self.signals.layout_changed.connect(self._debug_report_layout_state)
        
        self._install_global_event_filter()

    def enable_performance_monitoring(self):
        """Enable performance monitoring for debugging and optimization."""
        self.performance_monitor.enable()
    
    def disable_performance_monitoring(self):
        """Disable performance monitoring."""
        self.performance_monitor.disable()
    
    def get_performance_stats(self) -> dict:
        """Get current performance statistics."""
        stats = self.performance_monitor.get_overall_stats()
        
        # Add cache-specific stats
        if hasattr(self.hit_test_cache, 'get_geometry_cache_stats'):
            stats['hit_test_cache'] = self.hit_test_cache.get_geometry_cache_stats()
        
        # Add resize performance stats from containers
        resize_stats = []
        for container in self.containers:
            if hasattr(container, '_resize_cache') and container._resize_cache:
                resize_stats.append({
                    'container': str(container),
                    'cache_stats': container._resize_cache.get_cache_stats()
                })
        
        if resize_stats:
            stats['resize_operations'] = resize_stats
        
        return stats
    
    def clear_performance_metrics(self):
        """Clear all performance metrics."""
        self.performance_monitor.clear_metrics()

    def _install_global_event_filter(self) -> None:
        """Install a global event filter on QApplication for centralized event handling."""
        app = QApplication.instance()
        if app:
            app.installEventFilter(self)

    def _set_state(self, new_state: DockingState) -> None:
        """Set the docking manager state."""
        if self.state != new_state:
            self.state = new_state

    def is_idle(self) -> bool:
        """Check if the docking manager is in the idle state."""
        return self.state == DockingState.IDLE

    def is_rendering(self) -> bool:
        """Check if the docking manager is currently rendering layouts."""
        return self.state == DockingState.RENDERING

    def is_user_interacting(self) -> bool:
        """Check if the user is currently dragging or resizing windows."""
        return self.state in [DockingState.DRAGGING_WINDOW, DockingState.RESIZING_WINDOW, DockingState.DRAGGING_TAB]

    def _is_persistent_root(self, container: DockContainer) -> bool:
        """
        Check if the container is a persistent root (should never be closed).
        
        This is the authoritative method for checking persistent root status.
        It first checks the container's is_persistent_root property (if set),
        then falls back to type-based checks for MainDockWindow and FloatingDockRoot.
        
        Use this method rather than checking container.is_persistent_root directly
        to ensure all persistent root types are properly identified.
        """
        if hasattr(container, 'is_persistent_root') and container.is_persistent_root:
            return True
        
        if self.main_window and container is self.main_window.dock_area:
            return True
        if isinstance(container, FloatingDockRoot):
            return True
        return False
    
    def _is_child_of_persistent_root(self, container: DockContainer) -> bool:
        """Check if the container contains widgets that belong to a persistent root."""
        if not container or not hasattr(container, 'contained_widgets'):
            return False
            
        for widget in container.contained_widgets:
            if hasattr(widget, 'parent_container') and widget.parent_container:
                if self._is_persistent_root(widget.parent_container):
                    return True
                    
        for root_container, root_node in self.model.roots.items():
            if self._is_persistent_root(root_container) and container is not root_container:
                all_widgets_in_root = self.model.get_all_widgets_from_node(root_node)
                for widget_node in all_widgets_in_root:
                    if hasattr(widget_node.widget, 'parent_container') and widget_node.widget.parent_container is container:
                        return True
        return False

    def _update_container_root(self, container: DockContainer, new_root_node: AnyNode):
        """
        Safely update a container's root node, respecting persistent root status.
        For persistent roots, updates the existing root in-place. For others, replaces the root.
        """
        if self._is_persistent_root(container):
            self.model.roots[container] = new_root_node
            self._render_layout(container)
        else:
            self.model.roots[container] = new_root_node

    def save_layout_to_bytearray(self) -> bytearray:
        """Delegate to LayoutSerializer."""
        return self.layout_serializer.save_layout_to_bytearray()

    # Layout Serialization Delegation Methods
    # These methods provide a unified API through DockingManager for layout operations
    # that are implemented in separate specialized classes (LayoutSerializer, LayoutRenderer).
    # This delegation pattern allows external components to interact with layout functionality
    # through the central DockingManager without needing direct references to internal classes.
    
    def _serialize_node(self, node: AnyNode) -> dict:
        """Delegate to LayoutSerializer. Used internally by layout persistence."""
        return self.layout_serializer._serialize_node(node)

    def load_layout_from_bytearray(self, data: bytearray):
        """Delegate to LayoutSerializer. Public API for loading layouts."""
        return self.layout_serializer.load_layout_from_bytearray(data)

    def _clear_layout(self):
        """Delegate to LayoutSerializer. Internal method for clearing layouts."""
        return self.layout_serializer._clear_layout()

    def _deserialize_node(self, node_data: dict, loaded_widgets_cache: dict) -> AnyNode:
        """Delegate to LayoutSerializer. Used internally by layout restoration."""
        return self.layout_serializer._deserialize_node(node_data, loaded_widgets_cache)

    def _find_first_tab_group_node(self, node: AnyNode) -> TabGroupNode | None:
        """Delegate to LayoutSerializer."""
        return self.layout_serializer._find_first_tab_group_node(node)


    def _create_panel_from_key(self, key: str) -> DockPanel:
        """Delegate to WidgetFactory for panel creation."""
        return self.widget_factory.create_panel_from_key(key)

    def create_floating_widget_from_key(self, key: str, position=None, size=None) -> DockContainer:
        """Delegate to WidgetFactory for floating widget creation."""
        return self.widget_factory.create_floating_widget_from_key(key, position, size)

    def add_as_floating_widget(self, widget_instance: QWidget, persistent_key: str, title: str = None, 
                              position=None, size=None) -> DockContainer:
        """Delegate to WidgetFactory for floating widget creation from instance."""
        return self.widget_factory.add_as_floating_widget(widget_instance, persistent_key, title, position, size)

    def bring_to_front(self, widget):
        """Delegate to WindowManager for window stacking."""
        return self.window_manager.bring_to_front(widget)

    def sync_window_activation(self, activated_widget):
        """Delegate to WindowManager for window activation synchronization."""
        return self.window_manager.sync_window_activation(activated_widget)

    def move_widget_to_container(self, widget_to_move: DockPanel, target_container: DockContainer) -> bool:
        """
        Moves a widget from its current location directly into a target container as a new tab.
        This is now a high-level wrapper around the core dock_widget function.
        """
        if self.is_deleted(widget_to_move) or self.is_deleted(target_container):
            print(f"ERROR: Cannot move a deleted widget or to a deleted container.")
            return False

        _tab_group, _parent_node, source_root_window = self.model.find_host_info(widget_to_move)
        if source_root_window is target_container:
            return True

        self.dock_widget(widget_to_move, target_container, "center")

        return True

    def find_widget_by_id(self, persistent_id: str) -> DockPanel | None:
        """
        Searches all managed windows and containers to find a DockPanel by its persistent_id.
        Returns the widget instance if found, otherwise None.
        """
        all_widget_nodes = []
        for root_node in self.model.roots.values():
            all_widget_nodes.extend(self.model.get_all_widgets_from_node(root_node))

        for widget_node in all_widget_nodes:
            if widget_node.widget.persistent_id == persistent_id:
                return widget_node.widget

        return None

    def get_all_widgets(self) -> list[DockPanel]:
        """
        Returns a flat list of all DockPanel instances currently managed by the system.
        """
        all_widgets = []
        all_widget_nodes = []
        for root_node in self.model.roots.values():
            all_widget_nodes.extend(self.model.get_all_widgets_from_node(root_node))

        for widget_node in all_widget_nodes:
            all_widgets.append(widget_node.widget)

        return all_widgets

    def is_widget_docked(self, widget: DockPanel) -> bool:
        """
        Checks if a specific DockPanel is currently docked in a container.
        Returns True if docked, False if floating.
        """
        if widget.parent_container is not None:
            return True
        return False

    def set_main_window(self, window):
        """Stores a reference to the main application window."""
        self.main_window = window
        if window not in self.window_stack:
            self.window_stack.append(window)

    def set_debug_mode(self, enabled: bool):
        """
        Enables or disables the printing of the layout state
        to the console after operations.
        """
        try:
            self.signals.layout_changed.disconnect(self._debug_report_layout_state)
        except (TypeError, RuntimeError):
            pass
            
        self.debug_mode = enabled
        
        if enabled:
            self.signals.layout_changed.connect(self._debug_report_layout_state)
            

    def register_widget(self, widget: DockPanel):
        """
        Registers a DockPanel with the manager but does NOT create a floating window.
        DockPanel instances should only be added to DockContainers, not used as standalone windows.
        """
        widget.manager = self
        self.widgets.append(widget)
        self.add_widget_handlers(widget)

        if not self.is_deleted(widget):
            widget.installEventFilter(self)
            widget.setMouseTracking(True)
            widget.setAttribute(Qt.WA_Hover, True)


    def register_dock_area(self, dock_area: DockContainer):
        dock_area.manager = self
        self.model.roots[dock_area] = SplitterNode(orientation=Qt.Horizontal)
        if dock_area not in self.containers:
            self.containers.append(dock_area)
        if dock_area not in self.window_stack:
            self.window_stack.append(dock_area)

        self.add_widget_handlers(dock_area)

        if not self.is_deleted(dock_area):
            dock_area.installEventFilter(self)
            dock_area.setMouseTracking(True)
            dock_area.setAttribute(Qt.WA_Hover, True)

    def unregister_dock_area(self, dock_area: DockContainer):
        if dock_area in self.containers:
            self.containers.remove(dock_area)
        if dock_area in self.model.roots:
            self.model.unregister_widget(dock_area)
        if dock_area in self.window_stack:
            self.window_stack.remove(dock_area)

    def _cleanup_widget_references(self, widget_to_remove):
        if widget_to_remove in self.widgets: self.widgets.remove(widget_to_remove)
        if widget_to_remove in self.containers: self.containers.remove(widget_to_remove)
        if widget_to_remove in self.active_overlays: self.active_overlays.remove(widget_to_remove)
        if self.last_dock_target and self.last_dock_target[0] is widget_to_remove:
            self.last_dock_target = None
        if widget_to_remove in self.window_stack:
            self.window_stack.remove(widget_to_remove)
        self.model.unregister_widget(widget_to_remove)

    def _render_layout(self, container: DockContainer, widget_to_activate: DockPanel = None):
        """Delegate to LayoutRenderer. Used by drag_drop_controller and layout_serializer."""
        return self.layout_renderer.render_layout(container, widget_to_activate)

    def _update_tab_bar_visibility(self, container: DockContainer):
        """Delegate to LayoutRenderer. Internal method for tab bar management."""
        return self.layout_renderer._update_tab_bar_visibility(container)


    def _get_currently_active_widget(self, container: DockContainer) -> DockPanel | None:
        """
        Get the currently active widget in a container's tab group.
        Recursively searches through complex layouts (splitters containing tab groups).
        Returns None if container has no tab widget or no active tab.
        """
        if not container or not hasattr(container, 'layout') or not container.layout():
            return None
        
        def find_tab_widgets(widget):
            """Recursively find all QTabWidget instances in the widget hierarchy."""
            tab_widgets = []
            if isinstance(widget, QTabWidget):
                tab_widgets.append(widget)
            elif hasattr(widget, 'children'):
                for child in widget.children():
                    if isinstance(child, QWidget):
                        tab_widgets.extend(find_tab_widgets(child))
            if hasattr(widget, 'layout') and widget.layout():
                for i in range(widget.layout().count()):
                    item = widget.layout().itemAt(i)
                    if item and item.widget():
                        tab_widgets.extend(find_tab_widgets(item.widget()))
            return tab_widgets
        
        tab_widgets = find_tab_widgets(container)
        
        last_active_widget = None
        for tab_widget in tab_widgets:
            current_content = tab_widget.currentWidget()
            if current_content:
                active_widget = next((w for w in container.contained_widgets if w.content_container is current_content), None)
                if active_widget:
                    last_active_widget = active_widget
        
        return last_active_widget

    def _render_node(self, node: AnyNode, container: DockContainer, inside_splitter: bool = False, widget_to_activate: DockPanel = None) -> QWidget:
        """Delegate to LayoutRenderer. Internal method for rendering layout nodes."""
        return self.layout_renderer._render_node(node, container, inside_splitter, widget_to_activate)

    def add_widget_handlers(self, widget):
        """
        Finds the title bar of a given widget (either a DockPanel or a
        DockContainer) and attaches the custom mouse handlers for dragging.
        """
        if hasattr(widget, 'title_bar') and widget.title_bar:
            widget.title_bar.mouseReleaseEvent = self.create_release_handler(widget)

    def handle_live_move(self, source_container, event):
        """Delegate to DragDropController."""
        return self.drag_drop_controller.handle_live_move(source_container, event)

    def finalize_dock_from_live_move(self, source_container, dock_target_info):
        """Delegate to DragDropController."""
        return self.drag_drop_controller.finalize_dock_from_live_move(source_container, dock_target_info)

    def _finalize_tab_insertion(self, source_container, source_root_node, dock_target_info):
        """
        Performs model operations for tab insertion.
        """
        tab_widget, action, drop_index = dock_target_info
        if action != "insert":
            return
            
        from ..widgets.tearable_tab_widget import TearableTabWidget
        if not isinstance(tab_widget, TearableTabWidget) or not tab_widget.count():
            return
            
        first_content_widget = tab_widget.widget(0)
        target_widget = next((w for w in self.widgets if w.content_container is first_content_widget), None)
        if not target_widget:
            return
            
        target_group, _, destination_container = self.model.find_host_info(target_widget)
        if not target_group or not destination_container:
            return
            
        all_source_widgets = self.model.get_all_widgets_from_node(source_root_node)
        
        self.model.unregister_widget(source_container)
        
        for i, widget_node in enumerate(all_source_widgets):
            target_group.children.insert(drop_index + i, widget_node)
        
        widget_to_activate = all_source_widgets[0].widget if all_source_widgets else None
            
        self._render_layout(destination_container, widget_to_activate)
        destination_container.update()
        destination_container.repaint()
        
        # Shadow functionality removed
        
        if self._is_persistent_root(source_container):
            self.model.roots[source_container] = SplitterNode(orientation=Qt.Orientation.Horizontal)
            self._render_layout(source_container)
        else:
            source_container.close()
        
        if all_source_widgets:
            self.signals.widget_docked.emit(all_source_widgets[0].widget, destination_container)
        
        destination_container.update()
        destination_container.repaint()
        QApplication.processEvents()
        
        self.hit_test_cache.invalidate()

    def _finalize_regular_docking(self, source_container, source_root_node, dock_target_info):
        """
        Performs model operations for regular docking (left, right, top, bottom, center).
        """
        target_widget, location = dock_target_info
        
        if isinstance(target_widget, DockContainer):
            destination_container = self._handle_container_target_docking(target_widget, source_root_node, location)
        else:
            destination_container = self._handle_widget_target_docking(target_widget, source_root_node, location, source_container)
            if not destination_container:
                return
        
        self._complete_regular_docking(source_container, source_root_node, destination_container)

    def _handle_container_target_docking(self, destination_container, source_root_node, location):
        destination_root_node = self.model.roots.get(destination_container)
        if not destination_root_node:
            print(f"ERROR: No root node found for destination container {destination_container}")
            return None
            
        if location == 'center':
            self._perform_center_docking_to_container(destination_container, destination_root_node, source_root_node)
        else:
            self._perform_directional_docking_to_container(destination_container, destination_root_node, source_root_node, location)
        
        return destination_container

    def _perform_center_docking_to_container(self, destination_container, destination_root_node, source_root_node):
        if isinstance(destination_root_node, TabGroupNode):
            all_source_widgets = self.model.get_all_widgets_from_node(source_root_node)
            destination_root_node.children.extend(all_source_widgets)
        else:
            destination_tab_group = TabGroupNode()
            if isinstance(destination_root_node, WidgetNode):
                destination_tab_group.children.append(destination_root_node)
            else:
                dest_widgets = self.model.get_all_widgets_from_node(destination_root_node)
                destination_tab_group.children.extend(dest_widgets)
                
            source_widgets = self.model.get_all_widgets_from_node(source_root_node)
            destination_tab_group.children.extend(source_widgets)
            self._update_container_root(destination_container, destination_tab_group)

    def _perform_directional_docking_to_container(self, destination_container, destination_root_node, source_root_node, location):
        dest_widgets = self.model.get_all_widgets_from_node(destination_root_node)
        if self._is_persistent_root(destination_container) and not dest_widgets:
            if isinstance(source_root_node, SplitterNode):
                self._update_container_root(destination_container, source_root_node)
            else:
                source_widgets = self.model.get_all_widgets_from_node(source_root_node)
                new_tab_group = TabGroupNode()
                new_tab_group.children.extend(source_widgets)
                self._update_container_root(destination_container, new_tab_group)
        else:
            orientation = Qt.Orientation.Vertical if location in ["top", "bottom"] else Qt.Orientation.Horizontal
            new_splitter = SplitterNode(orientation=orientation)
            
            if self._is_persistent_root(destination_container):
                dest_tab_group = self._prepare_destination_node_for_splitting(destination_root_node)
                source_node = self._prepare_source_node_for_splitting(source_root_node)
                
                if location in ["top", "left"]:
                    new_splitter.children = [source_node, dest_tab_group]
                else:
                    new_splitter.children = [dest_tab_group, source_node]
                    
                self._update_container_root(destination_container, new_splitter)
            else:
                if location in ["top", "left"]:
                    new_splitter.children = [source_root_node, destination_root_node]
                else:
                    new_splitter.children = [destination_root_node, source_root_node]
                    
                self._update_container_root(destination_container, new_splitter)

    def _prepare_destination_node_for_splitting(self, destination_root_node):
        if isinstance(destination_root_node, WidgetNode):
            dest_tab_group = TabGroupNode()
            dest_tab_group.children.append(destination_root_node)
            return dest_tab_group
        elif isinstance(destination_root_node, TabGroupNode):
            return destination_root_node
        else:
            return destination_root_node

    def _prepare_source_node_for_splitting(self, source_root_node):
        if isinstance(source_root_node, SplitterNode):
            return source_root_node
        else:
            source_widgets = self.model.get_all_widgets_from_node(source_root_node)
            source_node = TabGroupNode()
            source_node.children.extend(source_widgets)
            return source_node

    def _handle_widget_target_docking(self, target_widget, source_root_node, location, source_container):
        destination_container = target_widget.parent_container
        if not destination_container:
            self._dock_to_floating_widget(source_container, target_widget, location)
            return None
        
        destination_root_node = self.model.roots.get(destination_container)
        if destination_root_node:
            all_widgets_in_dest = self.model.get_all_widgets_from_node(destination_root_node)
            
            if (len(all_widgets_in_dest) == 1 and 
                all_widgets_in_dest[0].widget == target_widget and 
                not self._is_persistent_root(destination_container)):
                self._dock_to_floating_widget_with_nodes(source_container, source_root_node, target_widget, location)
                return None
        
        container_root_node = self.model.roots.get(destination_container)
        if not container_root_node:
            print(f"ERROR: No root node found for destination container {destination_container}")
            return None
            
        target_widget_node, parent_node = self.model.find_widget_node_with_parent(container_root_node, target_widget)
        if not target_widget_node:
            print(f"ERROR: Could not find widget node for {target_widget}")
            return None
            
        ancestry_path = self.model._find_node_with_ancestry(container_root_node, target_widget_node)
        if len(ancestry_path) < 2:
            print(f"ERROR: Could not find proper ancestry for target widget")
            return None
        
        if location == 'center':
            self._perform_center_docking_to_widget(parent_node, target_widget_node, source_root_node, container_root_node, destination_container)
        else:
            self._perform_directional_docking_to_widget(ancestry_path, target_widget_node, source_root_node, location, destination_container)
        
        return destination_container

    def _perform_center_docking_to_widget(self, parent_node, target_widget_node, source_root_node, container_root_node, destination_container):
        source_widgets = self.model.get_all_widgets_from_node(source_root_node)
        if isinstance(parent_node, TabGroupNode):
            parent_node.children.extend(source_widgets)
        else:
            new_tab_group = TabGroupNode()
            new_tab_group.children.append(target_widget_node)
            new_tab_group.children.extend(source_widgets)
            
            if parent_node:
                self.model.replace_node_in_tree(container_root_node, target_widget_node, new_tab_group)
            else:
                self._update_container_root(destination_container, new_tab_group)

    def _perform_directional_docking_to_widget(self, ancestry_path, target_widget_node, source_root_node, location, destination_container):
        orientation = Qt.Orientation.Vertical if location in ["top", "bottom"] else Qt.Orientation.Horizontal
        new_splitter = SplitterNode(orientation=orientation)
        
        source_node = self._prepare_source_node_for_widget_docking(source_root_node)
        
        if len(ancestry_path) >= 3:
            self._handle_complex_ancestry_docking(ancestry_path, new_splitter, source_node, location)
        elif len(ancestry_path) == 2:
            self._handle_simple_ancestry_docking(ancestry_path, target_widget_node, new_splitter, source_node, location, destination_container)
        else:
            print(f"ERROR: Invalid ancestry path length for directional docking")

    def _prepare_source_node_for_widget_docking(self, source_root_node):
        if isinstance(source_root_node, SplitterNode):
            return source_root_node
        else:
            source_widgets = self.model.get_all_widgets_from_node(source_root_node)
            if len(source_widgets) == 1:
                source_node = TabGroupNode()
                source_node.children.append(source_widgets[0])
            else:
                source_node = TabGroupNode()
                source_node.children.extend(source_widgets)
            return source_node

    def _handle_complex_ancestry_docking(self, ancestry_path, new_splitter, source_node, location):
        grandparent_node = ancestry_path[-3]
        parent_tab_group = ancestry_path[-2]
        
        if isinstance(grandparent_node, SplitterNode) and isinstance(parent_tab_group, TabGroupNode):
            try:
                parent_index = grandparent_node.children.index(parent_tab_group)
                
                if location in ["top", "left"]:
                    new_splitter.children = [source_node, parent_tab_group]
                else:
                    new_splitter.children = [parent_tab_group, source_node]
                   
                grandparent_node.children[parent_index] = new_splitter              
                
            except ValueError:
                print(f"ERROR: Could not find parent TabGroupNode in grandparent's children")
        else:
            print(f"ERROR: Unexpected ancestry structure for directional docking")

    def _handle_simple_ancestry_docking(self, ancestry_path, target_widget_node, new_splitter, source_node, location, destination_container):
        root_node = ancestry_path[0]
        
        if isinstance(root_node, TabGroupNode):
            target_tab_group = root_node
        else:
            target_tab_group = TabGroupNode()
            target_tab_group.children.append(target_widget_node)
        
        if location in ["top", "left"]:
            new_splitter.children = [source_node, target_tab_group]
        else:
            new_splitter.children = [target_tab_group, source_node]
        
        self._update_container_root(destination_container, new_splitter)

    def _complete_regular_docking(self, source_container, source_root_node, destination_container):
        source_widgets = self.model.get_all_widgets_from_node(source_root_node)
        widget_to_activate = source_widgets[0].widget if source_widgets else None
        
        self._render_layout(destination_container, widget_to_activate)
        destination_container.update()
        destination_container.repaint()
        
        QApplication.processEvents()
        
        # Shadow functionality removed
        
        if self._is_persistent_root(source_container):
            self.model.roots[source_container] = SplitterNode(orientation=Qt.Orientation.Horizontal)
            self._render_layout(source_container)
        else:
            source_container.close()
        
        source_widgets = self.model.get_all_widgets_from_node(source_root_node)
        if source_widgets:
            self.signals.widget_docked.emit(source_widgets[0].widget, destination_container)
        
        destination_container.update()
        destination_container.repaint()
        QApplication.processEvents()
        
        self.hit_test_cache.invalidate()

    def create_release_handler(self, widget):
        original_release_event = widget.title_bar.mouseReleaseEvent

        def release_handler(event):
            widget.setWindowOpacity(1.0)

            original_release_event(event)
            operation_changed_layout = False
            if self.last_dock_target:
                operation_changed_layout = True
                if len(self.last_dock_target) == 3:
                    target_tab_widget, action, index = self.last_dock_target
                    self.dock_widgets(widget, index, action)
                elif len(self.last_dock_target) == 2:
                    target, dock_location = self.last_dock_target
                    self.dock_widgets(widget, target, dock_location)

            QApplication.processEvents()
            self.hit_test_cache.invalidate()
            self.destroy_all_overlays()
            self.last_dock_target = None
            
            if operation_changed_layout:
                self.signals.layout_changed.emit()
                
            QTimer.singleShot(200, self.force_cleanup_stuck_overlays)

        return release_handler


    def _validate_window_geometry(self, geometry: QRect) -> QRect:
        """Delegate to WindowManager for geometry validation."""
        return self.window_manager.validate_window_geometry(geometry)

    def create_simple_floating_widget(self, content_widget: QWidget, title: str = "Widget", 
                                     x: int = 300, y: int = 300, width: int = 400, height: int = 300) -> tuple[DockContainer, DockPanel]:
        """Delegate to WidgetFactory for simple floating widget creation."""
        return self.widget_factory.create_simple_floating_widget(content_widget, title, x, y, width, height)

    def create_floating_window(self, widgets: list[DockPanel], geometry: QRect, was_maximized=False,
                               normal_geometry=None):
        """Delegate to WidgetFactory for floating window creation."""
        return self.widget_factory.create_floating_window(widgets, geometry, was_maximized, normal_geometry)


    def undock_widget(self, widget_to_undock: DockPanel, global_pos: QPoint = None) -> DockContainer | None:
        """
        Programmatically undocks a widget from its container, making it a floating window.

        :param widget_to_undock: The widget to make floating.
        :param global_pos: An optional QPoint to specify the new top-left of the floating window.
        :return: The DockContainer that now contains the floating widget, or None on failure.
        """
        self.destroy_all_overlays()
        QApplication.processEvents()
        
        if self.is_deleted(widget_to_undock):
            print("ERROR: Cannot undock a deleted widget.")
            return None

        if not self.is_widget_docked(widget_to_undock):
            print("INFO: Widget is already floating.")
            return widget_to_undock

        host_tab_group, parent_node, root_window = self.model.find_host_info(widget_to_undock)
        if not host_tab_group or not root_window:
            print("ERROR: Could not find widget in the layout model.")
            return None

        currently_active_widget = None
        if isinstance(root_window, DockContainer):
            currently_active_widget = self._get_currently_active_widget(root_window)
            if currently_active_widget == widget_to_undock:
                currently_active_widget = None

        widget_node_to_remove = next((wn for wn in host_tab_group.children if wn.widget is widget_to_undock), None)
        if widget_node_to_remove:
            host_tab_group.children.remove(widget_node_to_remove)

        if widget_to_undock.content_container.isVisible():
            new_size = widget_to_undock.content_container.size()
        else:
            new_size = QSize(350, 250)

        title_height = widget_to_undock.title_bar.height()
        new_size.setHeight(new_size.height() + title_height)

        if global_pos:
            new_pos = global_pos
        else:
            count = self.floating_widget_count
            if widget_to_undock.content_container:
                widget_global_pos = widget_to_undock.content_container.mapToGlobal(QPoint(0, 0))
            else:
                widget_global_pos = widget_to_undock.mapToGlobal(QPoint(0, 0))
            new_pos = QPoint(widget_global_pos.x() + 150 + (count % 7) * 40,
                             widget_global_pos.y() + 150 + (count % 7) * 40)

        new_geometry = QRect(new_pos, new_size)

        newly_floated_window = self.create_floating_window([widget_to_undock], new_geometry)
        
        if not newly_floated_window:
            print("ERROR: Failed to create floating window.")
            return None

        self._simplify_model(root_window, currently_active_widget)
        if root_window in self.model.roots:
            root_window.update()
            root_window.repaint()
        else:
            root_window.update_dynamic_title()

        self.signals.widget_undocked.emit(widget_to_undock)
        
        if root_window in self.model.roots:
            root_window.update()
            root_window.repaint()
        if newly_floated_window:
            newly_floated_window.update()
            newly_floated_window.repaint()
        QApplication.processEvents()
        
        self.hit_test_cache.invalidate()
        
        if root_window in self.model.roots:
            QTimer.singleShot(10, lambda: self._cleanup_container_overlays(root_window))
            
        return newly_floated_window

    def dock_widget(self, source_widget: DockPanel, target_entity: QWidget, location: str):
        """
        Programmatically docks a source widget to a target entity (widget or container).

        :param source_widget: The DockPanel to be docked.
        :param target_entity: The DockPanel or DockContainer to dock into.
        :param location: A string representing the dock location ('top', 'left', 'bottom', 'right', 'center').
        """
        if self.is_deleted(source_widget) or source_widget not in self.get_all_widgets():
            print(f"ERROR: Source widget is not valid or not managed by this manager.")
            return

        is_target_valid = False
        if isinstance(target_entity, DockPanel) and not self.is_deleted(
                target_entity) and target_entity in self.get_all_widgets():
            is_target_valid = True
        elif isinstance(target_entity, DockContainer) and not self.is_deleted(
                target_entity) and target_entity in self.containers:
            is_target_valid = True

        if not is_target_valid:
            print(f"ERROR: Target entity '{target_entity.windowTitle()}' is not a valid, managed target.")
            return

        valid_locations = ["top", "left", "bottom", "right", "center"]
        if location not in valid_locations:
            print(f"ERROR: Invalid dock location '{location}'. Must be one of {valid_locations}.")
            return

        if source_widget is target_entity:
            print("ERROR: Cannot dock a widget to itself.")
            return

        self.dock_widgets(source_widget, target_entity, location)

        self.signals.layout_changed.emit()

    def dock_widgets(self, source_widget, target_entity, dock_location):
        source_node_to_move = self._prepare_source_for_docking(source_widget)
        if not source_node_to_move:
            return

        if dock_location == "insert":
            return self._handle_insert_docking(source_node_to_move, target_entity, source_widget)

        container_to_modify, target_node, target_parent = self._resolve_dock_target(target_entity, source_widget, dock_location)
        if not container_to_modify:
            return

        if target_node and not target_node.children:
            return self._handle_empty_container_docking(container_to_modify, source_node_to_move, source_widget)

        self._perform_docking_operation(container_to_modify, source_node_to_move, target_node, target_parent, dock_location)
        self._finalize_docking(container_to_modify, source_widget)

    def _prepare_source_for_docking(self, source_widget):
        self.destroy_all_overlays()
        QApplication.processEvents()
        
        source_node_to_move = self.model.roots.get(source_widget)
        
        if not source_node_to_move:
            host_tab_group, parent_node, root_window = self.model.find_host_info(source_widget)
            if host_tab_group and root_window:
                currently_active_widget = None
                if isinstance(root_window, DockContainer):
                    currently_active_widget = self._get_currently_active_widget(root_window)
                    if currently_active_widget == source_widget:
                        currently_active_widget = None
                        
                widget_node_to_move = next((wn for wn in host_tab_group.children if wn.widget is source_widget), None)
                if widget_node_to_move:
                    host_tab_group.children.remove(widget_node_to_move)
                    
                    tab_group_node = TabGroupNode(children=[widget_node_to_move])
                    source_node_to_move = tab_group_node
                    self.model.roots[source_widget] = source_node_to_move
                    
                    if root_window and root_window in self.model.roots:
                        self._simplify_model(root_window, currently_active_widget)
                else:
                    print(f"ERROR: Could not find widget node for '{source_widget.windowTitle()}' in its container.")
                    return None
            else:
                print(f"ERROR: Source '{source_widget.windowTitle()}' not found in model.")
                return None

        self.model.unregister_widget(source_widget)
        source_widget.hide()
        return source_node_to_move

    def _handle_insert_docking(self, source_node_to_move, target_entity, source_widget):
        from ..widgets.tearable_tab_widget import TearableTabWidget
        insertion_index = target_entity
        target_tab_widget = self.last_dock_target[0]

        if not isinstance(target_tab_widget, TearableTabWidget): 
            return
        if not target_tab_widget.count(): 
            return

        first_content_widget = target_tab_widget.widget(0)
        owner_widget = next((w for w in self.widgets if w.content_container is first_content_widget), None)
        if not owner_widget: 
            return

        target_group, _, root_window = self.model.find_host_info(owner_widget)
        if not target_group: 
            return

        all_source_widgets = self.model.get_all_widgets_from_node(source_node_to_move)

        for i, widget_node in enumerate(all_source_widgets):
            target_group.children.insert(insertion_index + i, widget_node)

        self._render_layout(root_window, source_widget)
        self._complete_docking_operation(root_window, source_widget)

    def _resolve_dock_target(self, target_entity, source_widget, dock_location):
        container_to_modify = None
        target_node = None
        target_parent = None

        if isinstance(target_entity, DockPanel):
            target_node, target_parent, container_to_modify = self.model.find_host_info(target_entity)
            
            if isinstance(container_to_modify, DockPanel):
                self._dock_to_floating_widget(source_widget, container_to_modify, dock_location)
                return None, None, None

        elif isinstance(target_entity, DockContainer):
            container_to_modify = target_entity
            target_node = self.model.roots.get(container_to_modify)
            target_parent = None

        if not container_to_modify:
            print(f"ERROR: Could not resolve a container to dock into.")
            return None, None, None

        return container_to_modify, target_node, target_parent

    def _handle_empty_container_docking(self, container_to_modify, source_node_to_move, source_widget):
        self._update_container_root(container_to_modify, source_node_to_move)
        self._render_layout(container_to_modify, source_widget)
        self._complete_docking_operation(container_to_modify, source_widget)

    def _perform_docking_operation(self, container_to_modify, source_node_to_move, target_node, target_parent, dock_location):
        self._save_splitter_sizes_to_model(container_to_modify.splitter, self.model.roots[container_to_modify])

        if dock_location == 'center' and isinstance(target_node, TabGroupNode):
            all_source_widgets = self.model.get_all_widgets_from_node(source_node_to_move)
            target_node.children.extend(all_source_widgets)
        else:
            actual_target_node = target_node
            
            orientation = Qt.Orientation.Vertical if dock_location in ["top", "bottom"] else Qt.Orientation.Horizontal
            new_splitter = SplitterNode(orientation=orientation)
            if dock_location in ["top", "left"]:
                new_splitter.children = [source_node_to_move, actual_target_node]
            else:
                new_splitter.children = [actual_target_node, source_node_to_move]

            if target_parent is None:
                self._update_container_root(container_to_modify, new_splitter)
            elif isinstance(target_parent, SplitterNode):
                try:
                    idx = target_parent.children.index(target_node)
                    target_parent.children[idx] = new_splitter
                except (ValueError, IndexError):
                    print("ERROR: Consistency error during model update.")
                    self._update_container_root(container_to_modify, new_splitter)

    def _finalize_docking(self, container_to_modify, source_widget):
        if hasattr(container_to_modify, 'overlay') and container_to_modify.overlay:
            container_to_modify.overlay.destroy_overlay()
            container_to_modify.overlay = None
            
        self._render_layout(container_to_modify, source_widget)
        self._complete_docking_operation(container_to_modify, source_widget)

    def _complete_docking_operation(self, container, source_widget):
        container.update()
        container.repaint()
        QApplication.processEvents()
        
        self.signals.widget_docked.emit(source_widget, container)
        self.destroy_all_overlays()
        
        container.update()
        container.repaint()
        QApplication.processEvents()
        
        self.hit_test_cache.invalidate()
        QTimer.singleShot(10, lambda: self._cleanup_container_overlays(container))

    def _cleanup_container_overlays(self, container):
        """Delegate to OverlayManager for container overlay cleanup."""
        return self.overlay_manager.cleanup_container_overlays(container)

    def _dock_to_floating_widget(self, source_widget, target_widget, dock_location):
        """
        Private helper to handle the specific case of docking any source
        to a standalone, floating DockPanel. This always creates a new
        DockContainer to house them both.
        """
        
        if isinstance(source_widget, DockContainer):
            source_node_to_move = self.model.roots.get(source_widget)
        else:
 
            source_node_to_move = self.model.roots.get(source_widget)
            
        if hasattr(target_widget, 'parent_container') and target_widget.parent_container:
            target_container = target_widget.parent_container
            target_node_to_move = self.model.roots.get(target_container)
        else:
            target_node_to_move = self.model.roots.get(target_widget)
        

        if not source_node_to_move or not target_node_to_move:
            print("ERROR: Cannot find source or target node for floating dock operation.")
            return

        if hasattr(target_widget, 'parent_container') and target_widget.parent_container:
            self.model.unregister_widget(target_widget.parent_container)
        else:
            self.model.unregister_widget(target_widget)

        new_root_node = None
        if dock_location == 'center':
            all_source_widgets = self.model.get_all_widgets_from_node(source_node_to_move)
            all_target_widgets = self.model.get_all_widgets_from_node(target_node_to_move)
            
            new_tab_group = TabGroupNode(children=all_target_widgets + all_source_widgets)
            new_root_node = new_tab_group
        else:
            orientation = Qt.Orientation.Vertical if dock_location in ["top", "bottom"] else Qt.Orientation.Horizontal
            new_splitter = SplitterNode(orientation=orientation)
            
            source_child_node = source_node_to_move
            if isinstance(source_node_to_move, WidgetNode):
                source_child_node = TabGroupNode(children=[source_node_to_move])
            elif not isinstance(source_node_to_move, (TabGroupNode, SplitterNode)):
                source_widgets = self.model.get_all_widgets_from_node(source_node_to_move)
                source_child_node = TabGroupNode(children=source_widgets)
                
            target_child_node = target_node_to_move
            if isinstance(target_node_to_move, WidgetNode):
                target_child_node = TabGroupNode(children=[target_node_to_move])
            elif not isinstance(target_node_to_move, (TabGroupNode, SplitterNode)):
                target_widgets = self.model.get_all_widgets_from_node(target_node_to_move)
                target_child_node = TabGroupNode(children=target_widgets)
            
            if dock_location in ["top", "left"]:
                new_splitter.children = [source_child_node, target_child_node]
            else:
                new_splitter.children = [target_child_node, source_child_node]
            new_root_node = new_splitter

        if not new_root_node:
            print("ERROR: Failed to create valid root node for floating dock operation.")
            return
            
        if hasattr(new_root_node, 'children'):
            for i, child in enumerate(new_root_node.children):
                if hasattr(child, 'widget'):
                    pass
                elif hasattr(child, 'children'):
                    pass

        new_container = DockContainer(manager=self, parent=None)
        new_container.setGeometry(target_widget.geometry())

        self.model.roots[new_container] = new_root_node
        self.containers.append(new_container)
        self.add_widget_handlers(new_container)
        self.bring_to_front(new_container)

        if hasattr(source_widget, 'overlay') and source_widget.overlay:
            source_widget.overlay.destroy_overlay()
            source_widget.overlay = None
        if hasattr(target_widget, 'overlay') and target_widget.overlay:
            target_widget.overlay.destroy_overlay()
            target_widget.overlay = None
            
        source_widget.hide()
        target_widget.hide()

        self._render_layout(new_container)
        new_container.show()
        new_container.on_activation_request()

        new_container.update()
        new_container.repaint()
        
        final_root = self.model.roots.get(new_container)
        
        all_widgets_in_container = []
        if final_root:
            all_widgets_in_container = self.model.get_all_widgets_from_node(final_root)
            for i, widget_node in enumerate(all_widgets_in_container):
                widget_title = widget_node.widget.windowTitle() if widget_node.widget else "Unknown"
                widget_visible = widget_node.widget.isVisible() if widget_node.widget else "Unknown"
        
        
        self.signals.widget_docked.emit(source_widget, new_container)
        self.destroy_all_overlays()
        
        new_container.update()
        new_container.repaint()
        QApplication.processEvents()
        
        self.hit_test_cache.invalidate()
        
        QTimer.singleShot(10, lambda: self._cleanup_container_overlays(new_container))

    def _dock_to_floating_widget_with_nodes(self, source_container, source_node_to_move, target_widget, dock_location):
        """
        Helper method that handles floating-to-floating docking when we already have the source node.
        """
        
        if hasattr(target_widget, 'parent_container') and target_widget.parent_container:
            target_container = target_widget.parent_container
            target_node_to_move = self.model.roots.get(target_container)
        else:
            print("ERROR: Target widget has no parent container")
            return
        
        if not source_node_to_move or not target_node_to_move:
            print("ERROR: Cannot find source or target node for floating dock operation.")
            return

        self.model.unregister_widget(source_container)
        self.model.unregister_widget(target_container)

        return self._perform_floating_dock_operation(source_container, source_node_to_move, target_widget, target_node_to_move, dock_location)

    def _perform_floating_dock_operation(self, source_container, source_node_to_move, target_widget, target_node_to_move, dock_location):
        """
        Performs the actual floating dock model construction and container creation.
        """
        new_root_node = None
        if dock_location == 'center':
            all_source_widgets = self.model.get_all_widgets_from_node(source_node_to_move)
            all_target_widgets = self.model.get_all_widgets_from_node(target_node_to_move)
            
            new_tab_group = TabGroupNode(children=all_target_widgets + all_source_widgets)
            new_root_node = new_tab_group
        else:
            orientation = Qt.Orientation.Vertical if dock_location in ["top", "bottom"] else Qt.Orientation.Horizontal
            new_splitter = SplitterNode(orientation=orientation)
            
            source_child_node = source_node_to_move
            if isinstance(source_node_to_move, WidgetNode):
                source_child_node = TabGroupNode(children=[source_node_to_move])
            elif not isinstance(source_node_to_move, (TabGroupNode, SplitterNode)):
                source_widgets = self.model.get_all_widgets_from_node(source_node_to_move)
                source_child_node = TabGroupNode(children=source_widgets)
                
            target_child_node = target_node_to_move
            if isinstance(target_node_to_move, WidgetNode):
                target_child_node = TabGroupNode(children=[target_node_to_move])
            elif not isinstance(target_node_to_move, (TabGroupNode, SplitterNode)):
                target_widgets = self.model.get_all_widgets_from_node(target_node_to_move)
                target_child_node = TabGroupNode(children=target_widgets)
            
            if dock_location in ["top", "left"]:
                new_splitter.children = [source_child_node, target_child_node]
            else:
                new_splitter.children = [target_child_node, source_child_node]
            new_root_node = new_splitter

        if not new_root_node:
            print("ERROR: Failed to create valid root node for floating dock operation.")
            return
            
        new_container = DockContainer(manager=self, parent=None)
        new_container.setGeometry(target_widget.parent_container.geometry() if target_widget.parent_container else target_widget.geometry())

        self.model.roots[new_container] = new_root_node
        self.containers.append(new_container)
        self.add_widget_handlers(new_container)
        self.bring_to_front(new_container)

        source_container.hide()
        if hasattr(target_widget, 'parent_container') and target_widget.parent_container:
            target_widget.parent_container.hide()

        self._render_layout(new_container)
        new_container.show()
        new_container.on_activation_request()

        new_container.update()
        new_container.repaint()
        
        final_root = self.model.roots.get(new_container)
        
        all_widgets_in_container = []
        if final_root:
            all_widgets_in_container = self.model.get_all_widgets_from_node(final_root)
            for i, widget_node in enumerate(all_widgets_in_container):
                widget_title = widget_node.widget.windowTitle() if widget_node.widget else "Unknown"
                widget_visible = widget_node.widget.isVisible() if widget_node.widget else "Unknown"
        
        
        if all_widgets_in_container:
            self.signals.widget_docked.emit(all_widgets_in_container[0].widget, new_container)
        self.destroy_all_overlays()
        
        new_container.update()
        new_container.repaint()
        QApplication.processEvents()
        
        self.hit_test_cache.invalidate()
        
        QTimer.singleShot(10, lambda: self._cleanup_container_overlays(new_container))

    def _update_model_after_close(self, widget_to_close: DockPanel):
        """Delegate to ModelUpdateEngine for model cleanup after widget close."""
        return self.model_update_engine.update_model_after_close(widget_to_close)

    def request_close_widget(self, widget_to_close: DockPanel):
        """
        Public method to safely close a single managed widget.
        """
        if self.is_deleted(widget_to_close):
            return

        host_tab_group, parent_node, root_window = self.model.find_host_info(widget_to_close)

        self.signals.widget_closed.emit(widget_to_close.persistent_id)

        if widget_to_close in self.model.roots:
            self.model.unregister_widget(widget_to_close)

        elif host_tab_group and isinstance(root_window, DockContainer):
            currently_active_widget = self._get_currently_active_widget(root_window)
            
            if currently_active_widget == widget_to_close:
                currently_active_widget = None
                
            widget_node_to_remove = next((wn for wn in host_tab_group.children if wn.widget is widget_to_close), None)
            if widget_node_to_remove:
                host_tab_group.children.remove(widget_node_to_remove)
            
            self._simplify_model(root_window, currently_active_widget)

        self.signals.layout_changed.emit()
        
        if root_window and not self.is_deleted(root_window):
            root_window.update()
            root_window.repaint()
        QApplication.processEvents()
        
        self.hit_test_cache.invalidate()
        
        widget_to_close.close()

    def request_close_container(self, container_to_close: DockContainer):
        """
        Public method to safely close an entire DockContainer and all widgets within it.
        """
        if self.is_deleted(container_to_close):
            return

        root_node = self.model.roots.get(container_to_close)
        if not root_node:
            return

        if self._is_persistent_root(container_to_close):
            all_widgets_in_container = self.model.get_all_widgets_from_node(root_node)
            for widget_node in all_widgets_in_container:
                self.signals.widget_closed.emit(widget_node.widget.persistent_id)
            
            self.model.roots[container_to_close] = SplitterNode(orientation=Qt.Orientation.Horizontal)
            self._render_layout(container_to_close)
            self.signals.layout_changed.emit()
            
            container_to_close.update()
            container_to_close.repaint()
            QApplication.processEvents()
            
            self.hit_test_cache.invalidate()
            return

        all_widgets_in_container = self.model.get_all_widgets_from_node(root_node)
        for widget_node in all_widgets_in_container:
            self.signals.widget_closed.emit(widget_node.widget.persistent_id)

        self.model.unregister_widget(container_to_close)
        self.signals.layout_changed.emit()
        
        QApplication.processEvents()
        
        self.hit_test_cache.invalidate()
        
        container_to_close.close()

    def _simplify_model(self, root_window: QWidget, widget_to_activate: DockPanel = None):
        """Delegate to ModelUpdateEngine for model simplification."""
        return self.model_update_engine.simplify_model(root_window, widget_to_activate)

    def close_tab_group(self, tab_widget: QTabWidget):
        if not tab_widget: return
        container = tab_widget.parentWidget()
        while container and not isinstance(container, DockContainer):
            container = container.parentWidget()
        if not container: return
        widgets_to_close = []
        for i in range(tab_widget.count()):
            content = tab_widget.widget(i)
            owner_widget = next((w for w in container.contained_widgets if w.content_container is content), None)
            if owner_widget:
                widgets_to_close.append(owner_widget)
        for widget in widgets_to_close:
            self.request_close_widget(widget)

    def undock_tab_group(self, tab_widget: QTabWidget):
        self.destroy_all_overlays()
        QApplication.processEvents()
        
        self._set_state(DockingState.RENDERING)
        try:
            self.last_dock_target = None
            
            if not tab_widget or not tab_widget.parentWidget(): return
            container = tab_widget.parentWidget()
            while container and not isinstance(container, DockContainer):
                container = container.parentWidget()
            if not container: return
            
            if hasattr(container, 'overlay') and container.overlay:
                container.overlay.destroy_overlay()
                container.overlay = None

            current_content = tab_widget.currentWidget()
            if not current_content: return
            
            active_widget = next((w for w in container.contained_widgets if w.content_container is current_content), None)
            if not active_widget: return
            
            widgets_to_move = [active_widget]

            host_tab_group, parent_node, root_window = self.model.find_host_info(active_widget)
            if host_tab_group is None: return

            new_geom = QRect(tab_widget.mapToGlobal(QPoint(0, 0)), tab_widget.size())

            widget_node_to_remove = None
            for child in host_tab_group.children:
                if isinstance(child, WidgetNode) and child.widget is active_widget:
                    widget_node_to_remove = child
                    break
            
            if widget_node_to_remove:
                host_tab_group.children.remove(widget_node_to_remove)

            newly_floated_window = self.create_floating_window(widgets_to_move, new_geom)

            if not self.is_deleted(root_window):
                remaining_active_widget = self._get_currently_active_widget(root_window)
                
                if hasattr(root_window, 'overlay') and root_window.overlay:
                    root_window.overlay.destroy_overlay() 
                    root_window.overlay = None
                self._simplify_model(root_window, remaining_active_widget)
                
                if root_window in self.model.roots:
                    root_window.update()
                    root_window.repaint()
                    QTimer.singleShot(10, lambda: self._cleanup_container_overlays(root_window))

            if newly_floated_window and not self.is_deleted(newly_floated_window):
                newly_floated_window.raise_()
                newly_floated_window.activateWindow()
                self.bring_to_front(newly_floated_window)

            for widget in widgets_to_move:
                self.signals.widget_undocked.emit(widget)

            self.signals.layout_changed.emit()
            
            if root_window and not self.is_deleted(root_window):
                root_window.update()
                root_window.repaint()
            if newly_floated_window and not self.is_deleted(newly_floated_window):
                newly_floated_window.update()
                newly_floated_window.repaint()
            QApplication.processEvents()
            
            self.hit_test_cache.invalidate()
        finally:
            self._set_state(DockingState.IDLE)
            self.last_dock_target = None
            for widget in self.widgets + self.containers:
                if hasattr(widget, 'title_bar') and widget.title_bar:
                    widget.title_bar.moving = False
            QTimer.singleShot(100, self.destroy_all_overlays)
            QTimer.singleShot(200, self.force_cleanup_stuck_overlays)

    def destroy_all_overlays(self):
        """Delegate to OverlayManager for comprehensive overlay cleanup."""
        return self.overlay_manager.destroy_all_overlays()
                        

    def force_cleanup_stuck_overlays(self):
        """Delegate to OverlayManager for emergency overlay cleanup."""
        return self.overlay_manager.force_cleanup_stuck_overlays()

    def _debug_report_layout_state(self):
        """
        Debug method to print the current layout state to the console.
        """
        if not self.debug_mode:
            return
        
        self.model.pretty_print(manager=self)

    def _save_splitter_sizes_to_model(self, widget, node):
        """Delegate to ModelUpdateEngine for splitter size persistence."""
        return self.model_update_engine.save_splitter_sizes_to_model(widget, node)

    def is_deleted(self, q_object):
        """Debug helper to check if a Qt object's C++ part is deleted."""
        if q_object is None:
            return True
        try:
            q_object.objectName()
            return False
        except RuntimeError:
            return True


    def has_simple_layout(self, container):
        """
        Determines if a container has a simple layout (single widget).
        For simple layouts, only widget overlays should show.
        For complex layouts, both container and widget overlays should show.
        """
        root_node = self.model.roots.get(container)
        if not root_node:
            return True
        
        if isinstance(root_node, WidgetNode):
            return True
        elif isinstance(root_node, TabGroupNode) and len(root_node.children) == 1:
            return True
        else:
            return False

    def create_new_floating_root(self):
        """Delegate to WindowManager for floating root creation."""
        return self.window_manager.create_new_floating_root()

    def undock_single_widget_by_tear(self, widget_to_undock: DockPanel, global_mouse_pos: QPoint):
        host_info = self._prepare_for_undocking(widget_to_undock)
        if not host_info:
            return
        
        host_tab_group, parent_node, root_window, currently_active_widget = host_info
        widget_node_to_remove = self._remove_widget_from_model(widget_to_undock, host_tab_group, root_window)
        
        if widget_node_to_remove:
            new_geometry = self._calculate_floating_window_geometry(widget_to_undock, global_mouse_pos)
            newly_floated_window = self.create_floating_window([widget_to_undock], new_geometry)
            
            self._finalize_undocking(root_window, currently_active_widget, newly_floated_window, global_mouse_pos)

    def _prepare_for_undocking(self, widget_to_undock):
        self.destroy_all_overlays()
        QApplication.processEvents()
        self.last_dock_target = None

        if hasattr(widget_to_undock, 'overlay') and widget_to_undock.overlay:
            widget_to_undock.overlay.destroy_overlay()
            widget_to_undock.overlay = None
            
        host_tab_group, parent_node, root_window = self.model.find_host_info(widget_to_undock)
        if not host_tab_group:
            return None

        currently_active_widget = None
        if isinstance(root_window, DockContainer):
            currently_active_widget = self._get_currently_active_widget(root_window)
            if currently_active_widget == widget_to_undock:
                currently_active_widget = None

        if hasattr(root_window, 'overlay') and root_window.overlay:
            root_window.overlay.destroy_overlay()
            root_window.overlay = None
        
        return host_tab_group, parent_node, root_window, currently_active_widget

    def _remove_widget_from_model(self, widget_to_undock, host_tab_group, root_window):
        widget_node_to_remove = next((wn for wn in host_tab_group.children if wn.widget is widget_to_undock), None)
        if widget_node_to_remove:
            if not self.is_deleted(root_window):
                root_window.setUpdatesEnabled(False)
            host_tab_group.children.remove(widget_node_to_remove)
        return widget_node_to_remove

    def _calculate_floating_window_geometry(self, widget_to_undock, global_mouse_pos):
        if widget_to_undock.content_container.isVisible():
            new_window_size = widget_to_undock.content_container.size()
        else:
            new_window_size = QSize(300, 200)

        title_height = widget_to_undock.title_bar.height()
        new_window_size.setHeight(new_window_size.height() + title_height)

        offset_y = title_height // 2
        offset_x = 50

        new_window_pos = global_mouse_pos - QPoint(offset_x, offset_y)
        return QRect(new_window_pos, new_window_size)

    def _finalize_undocking(self, root_window, currently_active_widget, newly_floated_window, global_mouse_pos):
        if not self.is_deleted(root_window):
            self._simplify_model(root_window, currently_active_widget)
            if root_window in self.model.roots:
                root_window.update()
                root_window.repaint()
            else:
                root_window.update_dynamic_title()
            root_window.setUpdatesEnabled(True)
            root_window.update()
            
            if root_window in self.model.roots:
                QTimer.singleShot(10, lambda: self._cleanup_container_overlays(root_window))

        if newly_floated_window:
            newly_floated_window.on_activation_request()

            title_bar = newly_floated_window.title_bar
            title_bar.moving = True
            title_bar.offset = global_mouse_pos - newly_floated_window.pos()
            title_bar.grabMouse()

    def start_tab_drag_operation(self, widget_persistent_id: str):
        """
        DEPRECATED: This method is no longer used. 
        Tab drag operations now use custom mouse tracking in TearableTabWidget.
        """
        return
        """
        Initiates a Qt-native drag operation for a tab with the given persistent ID.
        This method creates a QDrag object and handles the visual drag operation.
        """
        self.destroy_all_overlays()
        
        self.hit_test_cache.build_cache(self.window_stack, self.containers)
        
        widget_to_drag = self.find_widget_by_id(widget_persistent_id)
        if not widget_to_drag:
            print(f"ERROR: Widget with ID '{widget_persistent_id}' not found")
            return

        tab_widget, tab_index = self._find_tab_widget_for_widget(widget_to_drag)
        if not tab_widget or tab_index == -1:
            print(f"ERROR: Could not find tab widget for widget '{widget_persistent_id}'")
            return

        original_tab_text = tab_widget.tabText(tab_index)
        original_tab_enabled = tab_widget.isTabEnabled(tab_index)
        
        tab_widget.setTabEnabled(tab_index, False)
        tab_widget.setTabText(tab_index, f"[Dragging] {original_tab_text}")

        drag = QDrag(tab_widget)
        
        mime_data = QMimeData()
        mime_data.setData("application/x-jcdock-widget", widget_persistent_id.encode('utf-8'))
        drag.setMimeData(mime_data)

        tab_rect = tab_widget.tabBar().tabRect(tab_index)
        if not tab_rect.isEmpty():
            pixmap = QPixmap(tab_rect.size())
            pixmap.fill(Qt.transparent)
            
            painter = QPainter(pixmap)
            painter.setOpacity(0.7)
            tab_widget.tabBar().render(painter, QPoint(0, 0), tab_rect)
            painter.end()
            
            drag.setPixmap(pixmap)
            drag.setHotSpot(QPoint(tab_rect.width() // 2, tab_rect.height() // 2))

        self._drag_source_id = widget_persistent_id
        
        try:
            drop_action = drag.exec(Qt.MoveAction)
        finally:
            self._drag_source_id = None
            QApplication.processEvents()
            self.hit_test_cache.invalidate()

        if drop_action == Qt.MoveAction:
            pass
        else:
            tab_widget.setTabEnabled(tab_index, original_tab_enabled)
            tab_widget.setTabText(tab_index, original_tab_text)

            if drop_action == Qt.IgnoreAction:
                cursor_pos = QCursor.pos()
                self._create_floating_window_from_drag(widget_to_drag, cursor_pos)

    def _find_tab_widget_for_widget(self, widget):
        """
        Finds the QTabWidget and tab index containing the specified widget.
        Returns (tab_widget, index) or (None, -1) if not found.
        """
        for container in self.containers:
            if self.is_deleted(container):
                continue
            
            tab_widgets = container.findChildren(QTabWidget)
            for tab_widget in tab_widgets:
                for i in range(tab_widget.count()):
                    if tab_widget.widget(i) is widget.content_container:
                        return tab_widget, i
        
        return None, -1

    def _create_floating_window_from_drag(self, widget, cursor_pos):
        """
        Creates a floating window for a widget that was dragged to empty space.
        """
        if self.is_widget_docked(widget):
            host_tab_group, parent_node, root_window = self.model.find_host_info(widget)
            if host_tab_group:
                currently_active_widget = None
                if isinstance(root_window, DockContainer):
                    currently_active_widget = self._get_currently_active_widget(root_window)
                    if currently_active_widget == widget:
                        currently_active_widget = None
                
                widget_node_to_remove = next((wn for wn in host_tab_group.children if wn.widget is widget), None)
                if widget_node_to_remove:
                    host_tab_group.children.remove(widget_node_to_remove)
                    
                    if root_window and root_window in self.model.roots:
                        self._simplify_model(root_window, currently_active_widget)
                        if root_window in self.model.roots:
                            root_window.update()
                            root_window.repaint()
                            QApplication.processEvents()
                        else:
                            root_window.update_dynamic_title()
        
        widget_size = widget.content_container.size() if widget.content_container.size().isValid() else QSize(350, 250)
        title_height = 30
        
        window_pos = cursor_pos - QPoint(widget_size.width() // 2, title_height // 2)
        window_geometry = QRect(window_pos, widget_size + QSize(0, title_height))
        
        newly_floated_window = self.create_floating_window([widget], window_geometry)
        
        if newly_floated_window:
            self.signals.widget_undocked.emit(widget)
            self.signals.layout_changed.emit()
            
            QTimer.singleShot(100, self._refresh_all_container_titles)
        
        return newly_floated_window

    def _refresh_all_container_titles(self):
        """
        Forces a visual refresh of all container titles.
        Used to ensure title updates are visible after drag operations.
        """
        for container in self.containers:
            if not self.is_deleted(container) and hasattr(container, 'update_dynamic_title'):
                container.update_dynamic_title()

    def dock_widget_from_drag(self, widget_persistent_id: str, target_entity, dock_location: str):
        """
        Handles docking a widget during a drag and drop operation.
        This method properly removes the widget from its source location first,
        then docks it to the target.
        """
        
        widget_to_move = self.find_widget_by_id(widget_persistent_id)
        if not widget_to_move:
            print(f"ERROR: Widget with ID '{widget_persistent_id}' not found")
            return False

        
        source_removed = False
        if self.is_widget_docked(widget_to_move):
            host_tab_group, parent_node, root_window = self.model.find_host_info(widget_to_move)
            if host_tab_group:
                currently_active_widget = None
                if isinstance(root_window, DockContainer):
                    currently_active_widget = self._get_currently_active_widget(root_window)
                    if currently_active_widget == widget_to_move:
                        currently_active_widget = None
                
                widget_node_to_remove = next((wn for wn in host_tab_group.children if wn.widget is widget_to_move), None)
                if widget_node_to_remove:
                    host_tab_group.children.remove(widget_node_to_remove)
                    source_removed = True
                    
                    if root_window and root_window in self.model.roots:
                        self._simplify_model(root_window, currently_active_widget)
                        if root_window in self.model.roots:
                            pass
                        else:
                            root_window.update_dynamic_title()

        if source_removed:
            widget_node = WidgetNode(widget_to_move)
            tab_group_node = TabGroupNode(children=[widget_node])
            self.model.roots[widget_to_move] = tab_group_node
            
            widget_to_move.parent_container = None

        try:
            self.dock_widget(widget_to_move, target_entity, dock_location)
            return True
        except Exception as e:
            print(f"ERROR: Failed to dock widget during drag operation: {e}")
            if source_removed and widget_to_move in self.model.roots:
                self.model.unregister_widget(widget_to_move)
            return False

    def handle_qdrag_move(self, global_mouse_pos):
        """
        Centralized drag handling for QDrag operations.
        Uses the existing hit-testing system to show overlays on appropriate targets.
        """
        tab_bar_info = self.hit_test_cache.find_tab_bar_at_position(global_mouse_pos)
        if tab_bar_info:
            tab_bar = tab_bar_info.tab_widget.tabBar()
            local_pos = tab_bar.mapFromGlobal(global_mouse_pos)
            drop_index = tab_bar.get_drop_index(local_pos)

            if drop_index != -1:
                self.destroy_all_overlays()
                tab_bar.set_drop_indicator_index(drop_index)
                self.last_dock_target = (tab_bar_info.tab_widget, "insert", drop_index)
                return
            else:
                tab_bar.set_drop_indicator_index(-1)

        excluded_widget = None
        if self._drag_source_id:
            excluded_widget = self.find_widget_by_id(self._drag_source_id)
        
        cached_target = self.hit_test_cache.find_drop_target_at_position(global_mouse_pos, excluded_widget)
        target_widget = cached_target.widget if cached_target else None

        required_overlays = set()
        if target_widget:
            target_name = getattr(target_widget, 'objectName', lambda: f"{type(target_widget).__name__}@{id(target_widget)}")()
            
            if isinstance(target_widget, DockContainer):
                source_has_simple_layout = self.has_simple_layout(source_container if 'source_container' in locals() else excluded_widget)
                target_has_simple_layout = self.has_simple_layout(target_widget)
                
                if not source_has_simple_layout or not target_has_simple_layout:
                    required_overlays.add(target_widget)
            else:
                required_overlays.add(target_widget)
            parent_container = getattr(target_widget, 'parent_container', None)
            if parent_container:
                target_has_complex_layout = not self.has_simple_layout(parent_container)
                source_has_simple_layout = self.has_simple_layout(excluded_widget) if excluded_widget else False
                
                if target_has_complex_layout or not source_has_simple_layout:
                    required_overlays.add(parent_container)

        current_overlays = set(self.active_overlays)
        

        for w in (current_overlays - required_overlays):
            if not self.is_deleted(w):
                w.hide_overlay()
            self.active_overlays.remove(w)

        for w in (required_overlays - current_overlays):
            try:
                if not self.is_deleted(w):
                    if isinstance(w, DockContainer):
                        root_node = self.model.roots.get(w)
                        is_empty = not (root_node and root_node.children)
                        is_main_dock_area = (w is (self.main_window.dock_area if self.main_window else None))
                        is_floating_root = isinstance(w, FloatingDockRoot)
                        if is_empty and (is_main_dock_area or is_floating_root):
                            w.show_overlay(preset='main_empty')
                        else:
                            w.show_overlay(preset='standard')
                    else:
                        w.show_overlay()
                    self.active_overlays.append(w)
            except RuntimeError:
                if w in self.active_overlays:
                    self.active_overlays.remove(w)

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

        for overlay_widget in self.active_overlays:
            if overlay_widget is final_target:
                overlay_widget.show_preview(final_location)
            else:
                overlay_widget.show_preview(None)

        self.last_dock_target = (final_target, final_location) if (final_target and final_location) else None


    def activate_widget(self, widget_to_activate: DockPanel):
        """
        Brings a widget to the front and gives it focus.

        If the widget is in a tab group, its tab is made the current one.
        The top-level window containing the widget is then raised and activated.
        """
        if self.is_deleted(widget_to_activate):
            print(f"ERROR: Cannot activate a deleted widget.")
            return

        _tab_group, _parent_node, root_window = self.model.find_host_info(widget_to_activate)
        if not root_window:
            print(f"ERROR: Could not find a host window for '{widget_to_activate.windowTitle()}'.")
            return

        if isinstance(root_window, DockContainer):
            all_tabs = root_window.findChildren(QTabWidget)
            for tab_widget in all_tabs:
                if tab_widget.isAncestorOf(widget_to_activate.content_container):
                    tab_widget.setCurrentWidget(widget_to_activate.content_container)
                    break

        root_window.on_activation_request()

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """
        Centralized event filter that intercepts all application events.
        Routes mouse events through the HitTestCache system for efficient handling.
        """
        if not hasattr(event, 'type'):
            if self.debug_mode:
                print(f"DockingManager.eventFilter: Invalid event object type: {type(event)} from {type(obj)}")
            return False
        
        if self.is_rendering():
            return False
        
        if event.type() == QEvent.Type.MouseMove:
            return self._handle_global_mouse_move(obj, event)
        elif event.type() == QEvent.Type.MouseButtonPress:
            return self._handle_global_mouse_press(obj, event)
        elif event.type() == QEvent.Type.MouseButtonRelease:
            return self._handle_global_mouse_release(obj, event)
            
        return super().eventFilter(obj, event)

    def _handle_global_mouse_move(self, obj: QObject, event: QEvent) -> bool:
        """
        Handle mouse move events globally using HitTestCache for efficient targeting.
        Provides centralized coordination while delegating specific behaviors to components.
        """
        if self.is_user_interacting():
            return False
        
        if not self._is_managed_widget(obj):
            return False
        
        global_pos = event.globalPosition().toPoint()
        
        if not hasattr(self.hit_test_cache, '_cache_valid') or not self.hit_test_cache._cache_valid:
            self.hit_test_cache.build_cache(self.window_stack, self.containers)
        
        if self.is_idle():
            cached_target = self.hit_test_cache.find_drop_target_at_position(global_pos, None)
            
        
        return False

    def _handle_global_mouse_press(self, obj: QObject, event: QEvent) -> bool:
        """
        Handle mouse press events globally with state machine integration.
        Provides centralized coordination for drag initiation and window management.
        """
        if not self._is_managed_widget(obj):
            return False
        
        if self.is_idle():
            self.hit_test_cache.build_cache(self.window_stack, self.containers)
        
        return False

    def _handle_global_mouse_release(self, obj: QObject, event: QEvent) -> bool:
        """
        Handle mouse release events globally with state machine integration.
        Handles cleanup and state transitions after drag/resize operations.
        """
        if not self._is_managed_widget(obj):
            return False
        
        if self.is_user_interacting():
            pass
        
        return False

    def _is_managed_widget(self, obj: QObject) -> bool:
        """
        Check if the given object is a widget managed by this DockingManager.
        """
        if not isinstance(obj, QWidget):
            return False
        
        for widget in self.widgets:
            if obj is widget or obj.isAncestorOf(widget) or widget.isAncestorOf(obj):
                return True
        
        for container in self.containers:
            if obj is container or obj.isAncestorOf(container) or container.isAncestorOf(obj):
                return True
        
        return False
        
    def _clean_orphaned_overlays(self):
        """Delegate to OverlayManager for orphaned overlay cleanup."""
        return self.overlay_manager.clean_orphaned_overlays()
