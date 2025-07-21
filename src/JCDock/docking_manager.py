import pickle

from PySide6.QtWidgets import QWidget, QSplitter, QVBoxLayout, QTabWidget, QHBoxLayout, QPushButton, QStyle, QLabel, \
    QTableWidget, QTableWidgetItem, QApplication
from PySide6.QtCore import Qt, QRect, QEvent, QPoint, QRectF, QSize, QTimer, Signal, QObject
from PySide6.QtGui import QColor

from .floating_dock_root import FloatingDockRoot
from .main_dock_window import MainDockWindow
from .dock_model import LayoutModel, AnyNode, SplitterNode, TabGroupNode, WidgetNode
from .dockable_widget import DockableWidget
from .dock_container import DockContainer
from .hit_test_cache import HitTestCache

class DockingSignals(QObject):
    """
    A collection of signals to allow applications to react to layout changes.
    """
    # Emitted whenever any widget is successfully docked into a container.
    # Args: widget (DockableWidget), container (DockContainer)
    widget_docked = Signal(object, object)

    # Emitted whenever any widget is successfully undocked to become a floating window.
    # Args: widget (DockableWidget)
    widget_undocked = Signal(object)

    # Emitted right before a widget is closed and its references are removed.
    # Args: persistent_id (str)
    widget_closed = Signal(str)

    # A general signal emitted whenever the layout model has been finalized after a change.
    layout_changed = Signal()

class DockingManager(QObject):
    def __init__(self):
        super().__init__()
        self.widgets = []
        self.containers = []
        self.last_dock_target = None
        self.model = LayoutModel()
        self.active_overlays = []
        self.main_window = None  # Reference to the main application window for parenting.
        self.window_stack = []
        self.floating_widget_count = 0  # Counter for cascading new widgets.
        self.widget_factory = None  # This will hold the factory function
        self.debug_mode = True
        self.signals = DockingSignals()
        self._rendering_layout = False  # Flag to prevent event processing during layout updates
        self._undocking_in_progress = False  # Flag to prevent overlay operations during undocking
        self.hit_test_cache = HitTestCache()
        
        # Set up debug overlay reporting if debug mode is enabled
        if self.debug_mode:
            self.signals.layout_changed.connect(self._debug_report_active_overlays)

    def save_layout_to_bytearray(self) -> bytearray:
        layout_data = []

        if self.main_window and self.main_window.dock_area in self.model.roots:
            main_dock_area = self.main_window.dock_area
            main_root_node = self.model.roots[main_dock_area]

            if hasattr(main_dock_area, 'splitter'):
                self._save_splitter_sizes_to_model(main_dock_area.splitter, main_root_node)

            main_window_state = {
                'class': self.main_window.__class__.__name__,
                'geometry': self.main_window.geometry().getRect(),
                'is_maximized': self.main_window.isMaximized(),
                'normal_geometry': None,
                'content': self._serialize_node(main_root_node)
            }
            layout_data.append(main_window_state)

        for window, root_node in self.model.roots.items():
            if window is (self.main_window.dock_area if self.main_window else None):
                continue

            if self.is_deleted(window):
                continue

            if hasattr(window, 'splitter'):
                self._save_splitter_sizes_to_model(window.splitter, root_node)

            window_state = {
                'class': window.__class__.__name__,
                'geometry': window.geometry().getRect(),
                'is_maximized': getattr(window, '_is_maximized', False),
                'normal_geometry': None,
                'content': self._serialize_node(root_node)
            }
            if window_state['is_maximized']:
                normal_geom = getattr(window, '_normal_geometry', None)
                if normal_geom:
                    window_state['normal_geometry'] = normal_geom.getRect()

            layout_data.append(window_state)

        return pickle.dumps(layout_data)

    def _serialize_node(self, node: AnyNode) -> dict:
        if isinstance(node, SplitterNode):
            return {
                'type': 'SplitterNode',
                'orientation': node.orientation,
                'sizes': node.sizes,
                'children': [self._serialize_node(child) for child in node.children]
            }
        elif isinstance(node, TabGroupNode):
            return {
                'type': 'TabGroupNode',
                'children': [self._serialize_node(child) for child in node.children]
            }
        elif isinstance(node, WidgetNode):
            return {
                'type': 'WidgetNode',
                'id': node.widget.persistent_id,
                'margin': getattr(node.widget, '_content_margin_size', 5)
            }
        return {}

    def load_layout_from_bytearray(self, data: bytearray):
        if not self.widget_factory:
            print("ERROR: Cannot load layout without a widget factory. Please set one using set_widget_factory().")
            return

        self._clear_layout()

        try:
            layout_data = pickle.loads(data)
        except Exception as e:
            print(f"Error deserializing layout data: {e}")
            return

        loaded_widgets_cache = {}

        for window_state in layout_data:
            window_class = window_state['class']

            if window_class == 'MainDockWindow':
                container = self.main_window.dock_area
                geom_tuple = window_state['geometry']
                self.main_window.setGeometry(geom_tuple[0], geom_tuple[1], geom_tuple[2], geom_tuple[3])

                if window_state.get('is_maximized', False):
                    self.main_window.showMaximized()

                self.model.roots[container] = self._deserialize_node(window_state['content'], loaded_widgets_cache)
                self._render_layout(container)
                continue

            new_window = None
            if window_class == 'DockableWidget':
                widget_data = window_state['content']['children'][0]
                persistent_id = widget_data.get('id')

                if persistent_id in loaded_widgets_cache:
                    new_window = loaded_widgets_cache[persistent_id]
                else:
                    new_window = self.widget_factory(widget_data)
                    if new_window:
                        loaded_widgets_cache[persistent_id] = new_window

                if new_window:
                    self.model.roots[new_window] = self._deserialize_node(window_state['content'], loaded_widgets_cache)
                    self.register_widget(new_window)

            elif window_class == 'DockContainer':
                new_window = DockContainer(manager=self, parent=None)
                self.model.roots[new_window] = self._deserialize_node(window_state['content'], loaded_widgets_cache)
                self.containers.append(new_window)
                self.add_widget_handlers(new_window)
                self.bring_to_front(new_window)
                self._render_layout(new_window)

            elif window_class == 'FloatingDockRoot':
                new_window = FloatingDockRoot(manager=self)
                self.register_dock_area(new_window)
                self.model.roots[new_window] = self._deserialize_node(window_state['content'], loaded_widgets_cache)
                self._render_layout(new_window)

            if new_window:
                geom_tuple = window_state['geometry']
                new_window.setGeometry(geom_tuple[0], geom_tuple[1], geom_tuple[2], geom_tuple[3])

                if window_state['is_maximized']:
                    new_window._is_maximized = True
                    norm_geom_tuple = window_state['normal_geometry']
                    if norm_geom_tuple:
                        new_window._normal_geometry = QRect(norm_geom_tuple[0], norm_geom_tuple[1], norm_geom_tuple[2],
                                                            norm_geom_tuple[3])
                    new_window.main_layout.setContentsMargins(0, 0, 0, 0)
                    new_window.title_bar.maximize_button.setIcon(new_window.title_bar._create_control_icon("restore"))

                new_window.show()
                new_window.raise_()
                new_window.activateWindow()
                self.bring_to_front(new_window)

    def _clear_layout(self):
        """
        Closes all managed windows and resets the model to a clean state.
        """
        # Make a copy of the list of windows to close, as the original list will be modified
        windows_to_close = list(self.model.roots.keys())

        for window in windows_to_close:
            # Don't close the main application window, just clear its content
            if isinstance(window, DockContainer) and window.parent() is self.main_window:
                # Clear the splitter from the main dock area
                if window.splitter:
                    window.splitter.setParent(None)
                    window.splitter.deleteLater()
                    window.splitter = None
                # Reset its model to an empty node
                self.model.roots[window] = SplitterNode(orientation=Qt.Horizontal)
                continue

            # For all other floating windows, unregister and close them
            if window in self.model.roots:
                self.model.unregister_widget(window)

            window.setParent(None)
            window.close()

        # Reset all manager state
        self.widgets.clear()
        self.containers.clear()
        self.window_stack.clear()
        self.floating_widget_count = 0
        # Re-add the main window's dock area back to the containers list
        if self.main_window:
            self.containers.append(self.main_window.dock_area)
            self.window_stack.append(self.main_window)

    def _deserialize_node(self, node_data: dict, loaded_widgets_cache: dict) -> AnyNode:
        node_type = node_data.get('type')

        if node_type == 'SplitterNode':
            return SplitterNode(
                orientation=node_data['orientation'],
                sizes=node_data['sizes'],
                children=[self._deserialize_node(child_data, loaded_widgets_cache) for child_data in
                          node_data['children']]
            )
        elif node_type == 'TabGroupNode':
            return TabGroupNode(
                children=[self._deserialize_node(child_data, loaded_widgets_cache) for child_data in
                          node_data['children']]
            )
        elif node_type == 'WidgetNode':
            persistent_id = node_data.get('id')
            if not persistent_id:
                return TabGroupNode()

            if persistent_id in loaded_widgets_cache:
                new_widget = loaded_widgets_cache[persistent_id]
            else:
                new_widget = self.widget_factory(node_data)
                if new_widget:
                    loaded_widgets_cache[persistent_id] = new_widget

            if new_widget:
                return WidgetNode(widget=new_widget)

        return TabGroupNode()

    def _find_first_tab_group_node(self, node: AnyNode) -> TabGroupNode | None:
        """
        Recursively traverses a node tree to find the first TabGroupNode.
        """
        if isinstance(node, TabGroupNode):
            return node
        if isinstance(node, SplitterNode):
            for child in node.children:
                result = self._find_first_tab_group_node(child)
                if result:
                    return result
        return None

    def set_widget_factory(self, factory_callable):
        """
        Registers the application-specific function that can create widgets from a persistent ID.
        The callable must accept a string ID and return a DockableWidget instance.
        """
        self.widget_factory = factory_callable

    def bring_to_front(self, widget):
        """Brings a window to the top of our manual stack."""

        # This is the fix. We will build a new list without the widget,
        # then append it. This is more robust than remove().
        self.window_stack = [w for w in self.window_stack if w is not widget]
        self.window_stack.append(widget)

    def move_widget_to_container(self, widget_to_move: DockableWidget, target_container: DockContainer) -> bool:
        """
        Moves a widget from its current location directly into a target container as a new tab.
        This is now a high-level wrapper around the core dock_widget function.
        """
        # 1. Validate inputs
        if self.is_deleted(widget_to_move) or self.is_deleted(target_container):
            print(f"ERROR: Cannot move a deleted widget or to a deleted container.")
            return False

        # 2. Check if the widget is already in the target container
        _tab_group, _parent_node, source_root_window = self.model.find_host_info(widget_to_move)
        if source_root_window is target_container:
            print("INFO: Widget is already in the target container.")
            return True

        # 3. Use the core docking engine to perform the move.
        # Docking to the "center" of a container is the same as adding it as a tab.
        # The dock_widget function is robust and handles all cleanup and model updates.
        self.dock_widget(widget_to_move, target_container, "center")

        return True

    def find_widget_by_id(self, persistent_id: str) -> DockableWidget | None:
        """
        Searches all managed windows and containers to find a DockableWidget by its persistent_id.
        Returns the widget instance if found, otherwise None.
        """
        all_widget_nodes = []
        for root_node in self.model.roots.values():
            all_widget_nodes.extend(self.model.get_all_widgets_from_node(root_node))

        for widget_node in all_widget_nodes:
            if widget_node.widget.persistent_id == persistent_id:
                return widget_node.widget

        return None

    def get_all_widgets(self) -> list[DockableWidget]:
        """
        Returns a flat list of all DockableWidget instances currently managed by the system.
        """
        all_widgets = []
        all_widget_nodes = []
        for root_node in self.model.roots.values():
            all_widget_nodes.extend(self.model.get_all_widgets_from_node(root_node))

        for widget_node in all_widget_nodes:
            all_widgets.append(widget_node.widget)

        return all_widgets

    def get_floating_widgets(self) -> list[DockableWidget]:
        """
        Returns a list of all DockableWidgets that are currently top-level floating windows.
        """
        floating_widgets = []
        for root_window in self.model.roots.keys():
            if isinstance(root_window, DockableWidget):
                floating_widgets.append(root_window)
        return floating_widgets

    def is_widget_docked(self, widget: DockableWidget) -> bool:
        """
        Checks if a specific DockableWidget is currently docked in a container.
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
        Enables or disables the printing of the layout state and overlay census
        to the console after operations.
        """
        # Disconnect any existing connection first
        try:
            self.signals.layout_changed.disconnect(self._debug_report_active_overlays)
        except (TypeError, RuntimeError):
            # No connection exists or signal system issue - this is fine
            pass
            
        self.debug_mode = enabled
        
        # Connect overlay reporting if debug mode is enabled
        if enabled:
            self.signals.layout_changed.connect(self._debug_report_active_overlays)
            
        print(f"DockingManager debug mode set to: {self.debug_mode}")
        if enabled:
            print("Overlay state reporting will be triggered after layout changes.")

    def register_widget(self, widget: DockableWidget):
        widget.manager = self
        self.model.register_widget(widget)
        self.widgets.append(widget)
        self.add_widget_handlers(widget)  # Sets up title bar handlers
        self.bring_to_front(widget)

        # --- ADDED: Install DockingManager's event filter on the DockableWidget ---
        if not self.is_deleted(widget):
            widget.installEventFilter(self)  # Install manager on the DockableWidget itself
            widget.setMouseTracking(True)  # Ensure it generates mouse move events
            widget.setAttribute(Qt.WA_Hover, True)  # Potentially useful for consistent event generation

        if not widget.parent_container:
            self.floating_widget_count += 1

        if self.debug_mode:
            self.model.pretty_print()

    def register_dock_area(self, dock_area: DockContainer):
        dock_area.manager = self
        self.model.roots[dock_area] = SplitterNode(orientation=Qt.Horizontal)
        if dock_area not in self.containers:
            self.containers.append(dock_area)
        if dock_area not in self.window_stack:
            self.window_stack.append(dock_area)

        self.add_widget_handlers(dock_area)

        # --- ADDED: Install DockingManager's event filter on the DockContainer ---
        if not self.is_deleted(dock_area):
            dock_area.installEventFilter(self)  # Install manager on the DockContainer
            dock_area.setMouseTracking(True)  # Ensure it generates mouse move events
            dock_area.setAttribute(Qt.WA_Hover, True)  # Potentially useful for consistent event generation

        if self.debug_mode:
            self.model.pretty_print()

    def unregister_dock_area(self, dock_area: DockContainer):
        if dock_area in self.containers:
            self.containers.remove(dock_area)
        if dock_area in self.model.roots:
            self.model.unregister_widget(dock_area)
        if dock_area in self.window_stack:
            self.window_stack.remove(dock_area)

        if self.debug_mode:
            self.model.pretty_print()

    def _cleanup_widget_references(self, widget_to_remove):
        if widget_to_remove in self.widgets: self.widgets.remove(widget_to_remove)
        if widget_to_remove in self.containers: self.containers.remove(widget_to_remove)
        if widget_to_remove in self.active_overlays: self.active_overlays.remove(widget_to_remove)
        if self.last_dock_target and self.last_dock_target[0] is widget_to_remove:
            self.last_dock_target = None
        if widget_to_remove in self.window_stack:
            self.window_stack.remove(widget_to_remove)
        self.model.unregister_widget(widget_to_remove)

    def _render_layout(self, container: DockContainer):
        root_node = self.model.roots.get(container)
        if not root_node:
            print(f"ERROR: Cannot render layout for unregistered container {container.objectName()}")
            return

        # Destroy any overlays on the container before rendering
        if hasattr(container, 'overlay') and container.overlay:
            container.overlay.destroy_overlay()
            container.overlay = None
            
        # Set flag to prevent event processing during layout rendering
        self._rendering_layout = True
        try:
            # Clean up overlays on all currently contained widgets
            for widget in container.contained_widgets:
                if hasattr(widget, 'overlay') and widget.overlay:
                    widget.overlay.destroy_overlay()
                    widget.overlay = None
                    
            container.contained_widgets.clear()
            new_content_widget = self._render_node(root_node, container)
            old_content_widget = container.splitter
            if new_content_widget:
                container.inner_content_layout.addWidget(new_content_widget)

            if old_content_widget:
                old_content_widget.hide()
                old_content_widget.setParent(None)
                old_content_widget.deleteLater()

            container.splitter = new_content_widget

            if container.splitter:
                container._reconnect_tab_signals(container.splitter)
                container.update_corner_widget_visibility()

            if self.debug_mode:
                self.model.pretty_print()
        finally:
            # Always clear the flag, even if an error occurs
            self._rendering_layout = False

    def _render_node(self, node: AnyNode, container: DockContainer) -> QWidget:
        if isinstance(node, SplitterNode):
            qt_splitter = QSplitter(node.orientation)
            qt_splitter.setObjectName("ContainerSplitter")
            qt_splitter.setStyleSheet("""
                QSplitter::handle {
                    background-color: #C4C4C3;
                    border: none;
                }
                QSplitter::handle:hover {
                    background-color: #A9A9A9;
                }
            """)
            qt_splitter.setHandleWidth(2)
            qt_splitter.setChildrenCollapsible(False)
            for child_node in node.children:
                child_widget = self._render_node(child_node, container)
                if child_widget:
                    qt_splitter.addWidget(child_widget)
            if node.sizes and len(node.sizes) == qt_splitter.count():
                qt_splitter.setSizes(node.sizes)
            else:
                qt_splitter.setSizes([100] * qt_splitter.count())
            return qt_splitter
        elif isinstance(node, TabGroupNode):
            qt_tab_widget = container._create_tab_widget_with_controls()
            for widget_node in node.children:
                widget = widget_node.widget
                qt_tab_widget.addTab(widget.content_container, widget.windowTitle())
                if widget.original_bg_color:
                    bg_color_name = widget.original_bg_color.name()
                    widget.content_container.setStyleSheet(
                        f"#ContentContainer {{ background-color: {bg_color_name}; border-radius: 0px; }}")
                widget.parent_container = container
                # Remove shadow effect when widget becomes docked
                widget._remove_shadow_effect()
                if widget not in container.contained_widgets:
                    container.contained_widgets.append(widget)
            return qt_tab_widget
        elif isinstance(node, WidgetNode):
            return node.widget.content_container

    def add_widget_handlers(self, widget):
        """
        Finds the title bar of a given widget (either a DockableWidget or a
        DockContainer) and attaches the custom mouse handlers for dragging.
        """
        # This method is now safe for both classes because it checks for a generic
        # 'title_bar' attribute, which both DockableWidget and DockContainer possess.
        if hasattr(widget, 'title_bar') and widget.title_bar:
            # The TitleBar's mouseMoveEvent will now call the manager directly.
            # We only need to override the release handler here.
            widget.title_bar.mouseReleaseEvent = self.create_release_handler(widget)

    def handle_drag_move(self, widget, event):
        """
        High-performance drag handling using cached hit-testing.
        """
        if widget.resizing or not widget.title_bar.moving:
            return
            
        # Don't show overlays during critical operations
        if self._undocking_in_progress or self._rendering_layout:
            return
            
        # Additional safety check - verify the widget is actually being dragged
        if not hasattr(widget, 'title_bar') or not widget.title_bar or not widget.title_bar.moving:
            self.destroy_all_overlays()
            return

        if isinstance(widget, FloatingDockRoot):
            self.destroy_all_overlays()
            self.last_dock_target = None
            return

        global_mouse_pos = event.globalPosition().toPoint()

        # Step 1: Check for tab bar insertion first (highest priority)
        tab_bar_info = self.hit_test_cache.find_tab_bar_at_position(global_mouse_pos)
        if tab_bar_info:
            tab_bar = tab_bar_info.tab_widget.tabBar()
            local_pos = tab_bar.mapFromGlobal(global_mouse_pos)
            drop_index = tab_bar.get_drop_index(local_pos)

            if drop_index != -1:
                widget.setWindowOpacity(0.65)
                self.destroy_all_overlays()
                tab_bar.set_drop_indicator_index(drop_index)
                self.last_dock_target = (tab_bar_info.tab_widget, "insert", drop_index)
                return
            else:
                tab_bar.set_drop_indicator_index(-1)

        # Step 2: Find the drop target using cached data
        cached_target = self.hit_test_cache.find_drop_target_at_position(global_mouse_pos, widget)
        target_widget = cached_target.widget if cached_target else None

        widget.setWindowOpacity(1.0)

        # Step 3: Update overlay visibility based on target
        required_overlays = set()
        if target_widget:
            required_overlays.add(target_widget)
            if getattr(target_widget, 'parent_container', None):
                required_overlays.add(target_widget.parent_container)

        current_overlays = set(self.active_overlays)

        # Hide overlays no longer needed
        for w in (current_overlays - required_overlays):
            if not self.is_deleted(w):
                w.hide_overlay()
            self.active_overlays.remove(w)

        # Show overlays for new targets
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
        for overlay_widget in self.active_overlays:
            if overlay_widget is final_target:
                overlay_widget.show_preview(final_location)
            else:
                overlay_widget.show_preview(None)

        self.last_dock_target = (final_target, final_location) if (final_target and final_location) else None

    def raise_all_floating_widgets(self):
        """Brings all true 'floating layer' widgets to the top of the stacking order..."""

        for window in self.window_stack:
            if not window:
                continue

            is_base_window = (window is self.main_window) or isinstance(window, FloatingDockRoot)
            if not is_base_window:
                window.raise_()

    def create_release_handler(self, widget):
        original_release_event = widget.title_bar.mouseReleaseEvent

        def release_handler(event):
            # Ensure the widget is fully opaque as soon as the drag is released.
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

            # Invalidate the cache and run one immediate, brute-force cleanup
            self.hit_test_cache.invalidate()
            self.destroy_all_overlays()
            self.last_dock_target = None
            
            if operation_changed_layout:
                self.signals.layout_changed.emit()
                
            # The Ultimate Safety Net: A single, delayed, forceful check
            QTimer.singleShot(200, self.force_cleanup_stuck_overlays)

        return release_handler

    def create_floating_window(self, widgets: list[DockableWidget], geometry: QRect, was_maximized=False,
                               normal_geometry=None):
        if not widgets: return None
        if len(widgets) == 1:
            widget_to_float = widgets[0]
            # Pass the state down to the undock function.
            return self._reparent_to_floating_window(widget_to_float, geometry, was_maximized, normal_geometry)
        else:
            new_container = DockContainer(manager=self, parent=None)
            new_container.setGeometry(geometry)

            widget_nodes = [WidgetNode(w) for w in widgets]
            tab_group_node = TabGroupNode(children=widget_nodes)
            self.model.roots[new_container] = tab_group_node
            for widget in widgets:
                widget.parent_container = new_container
            self.add_widget_handlers(new_container)
            self.containers.append(new_container)
            self.bring_to_front(new_container)
            self._render_layout(new_container)
            new_container.show()

            new_container.raise_()
            new_container.activateWindow()
            return new_container

    def _reparent_to_floating_window(self, widget_to_undock, geometry, was_maximized=False, normal_geometry=None):
        # Destroy any overlay associated with this widget before reparenting
        if hasattr(widget_to_undock, 'overlay') and widget_to_undock.overlay:
            widget_to_undock.overlay.destroy_overlay()
            widget_to_undock.overlay = None
            
        cc = widget_to_undock.content_container
        cc.setParent(None)
        widget_to_undock.main_layout.addWidget(cc)
        widget_to_undock.content_container.setStyleSheet("background: transparent;")
        widget_to_undock.parent_container = None

        widget_to_undock.setParent(None)
        widget_to_undock.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)

        # The definitive fix: Set the maximized state BEFORE setting geometry and showing.
        if was_maximized:
            widget_to_undock._is_maximized = True
            if normal_geometry:
                widget_to_undock._normal_geometry = normal_geometry
            widget_to_undock.main_layout.setContentsMargins(0, 0, 0, 0)
            widget_to_undock.title_bar.maximize_button.setIcon(
                widget_to_undock.title_bar._create_control_icon("restore")
            )

        # Now that the state is correct, set the geometry. The show() method in DockableWidget
        # will now see the _is_maximized flag and correctly skip the auto-positioning logic.
        widget_to_undock.setGeometry(geometry)

        # Set up shadow effect for floating widget
        if not was_maximized:
            widget_to_undock._setup_shadow_effect()

        # This is the step that was missing from my flawed manual implementation.
        # We must explicitly show both the content and the main window frame.
        cc.show()
        widget_to_undock.show()

        self.register_widget(widget_to_undock)

        widget_to_undock.raise_()
        widget_to_undock.activateWindow()
        return widget_to_undock

    def undock_widget(self, widget_to_undock: DockableWidget, global_pos: QPoint = None) -> DockableWidget | None:
        """
        Programmatically undocks a widget from its container, making it a floating window.

        :param widget_to_undock: The widget to make floating.
        :param global_pos: An optional QPoint to specify the new top-left of the floating window.
        :return: The widget that is now floating, or None on failure.
        """
        # PRE-EMPTIVE CLEANUP: Destroy ALL overlays before major layout change
        self.destroy_all_overlays()
        # PHANTOM OVERLAY FIX: Force immediate processing of overlay destruction paint events
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

        widget_node_to_remove = next((wn for wn in host_tab_group.children if wn.widget is widget_to_undock), None)
        if widget_node_to_remove:
            host_tab_group.children.remove(widget_node_to_remove)

        # Calculate geometry
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
            main_window_pos = self.main_window.pos()
            new_pos = QPoint(main_window_pos.x() + 150 + (count % 7) * 40,
                             main_window_pos.y() + 150 + (count % 7) * 40)

        new_geometry = QRect(new_pos, new_size)

        self._reparent_to_floating_window(widget_to_undock, new_geometry)

        self._simplify_model(root_window)
        if root_window in self.model.roots:
            self._render_layout(root_window)
            
            # CRITICAL: Force aggressive visual cleanup on the remaining container
            # This prevents stranded overlay graphics on Widget 1 when Widget 2 is undocked
            root_window.update()
            root_window.repaint()

        self.signals.widget_undocked.emit(widget_to_undock)
        
        # Additional cleanup to ensure no visual artifacts remain
        if root_window in self.model.roots:
            QTimer.singleShot(10, lambda: self._cleanup_container_overlays(root_window))
            
        return widget_to_undock

    def dock_widget(self, source_widget: DockableWidget, target_entity: QWidget, location: str):
        """
        Programmatically docks a source widget to a target entity (widget or container).

        :param source_widget: The DockableWidget to be docked.
        :param target_entity: The DockableWidget or DockContainer to dock into.
        :param location: A string representing the dock location ('top', 'left', 'bottom', 'right', 'center').
        """
        # 1. Validate inputs
        if self.is_deleted(source_widget) or source_widget not in self.get_all_widgets():
            print(f"ERROR: Source widget is not valid or not managed by this manager.")
            return

        is_target_valid = False
        if isinstance(target_entity, DockableWidget) and not self.is_deleted(
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

        # 2. Call the internal docking logic
        self.dock_widgets(source_widget, target_entity, location)

        # 3. Emit the final layout changed signal
        self.signals.layout_changed.emit()

    def dock_widgets(self, source_widget, target_entity, dock_location):
        # PRE-EMPTIVE CLEANUP: Destroy ALL overlays before major layout change
        self.destroy_all_overlays()
        # PHANTOM OVERLAY FIX: Force immediate processing of overlay destruction paint events
        QApplication.processEvents()
        
        source_node_to_move = self.model.roots.get(source_widget)
        if not source_node_to_move:
            print(f"ERROR: Source '{source_widget.windowTitle()}' not found in model roots.")
            return

        # Handle the "insert" action for dropping onto a tab bar
        if dock_location == "insert":
            from tearable_tab_widget import TearableTabWidget
            insertion_index = target_entity
            target_tab_widget = self.last_dock_target[0]

            if not isinstance(target_tab_widget, TearableTabWidget): return
            if not target_tab_widget.count(): return

            first_content_widget = target_tab_widget.widget(0)
            owner_widget = next((w for w in self.widgets if w.content_container is first_content_widget), None)
            if not owner_widget: return

            target_group, _, root_window = self.model.find_host_info(owner_widget)
            if not target_group: return

            self.model.unregister_widget(source_widget)
            source_widget.hide()

            all_source_widgets = self.model.get_all_widgets_from_node(source_node_to_move)

            for i, widget_node in enumerate(all_source_widgets):
                target_group.children.insert(insertion_index + i, widget_node)

            self._render_layout(root_window)
            # Force immediate visual update
            root_window.update()
            root_window.repaint()
            
            self.signals.widget_docked.emit(source_widget, root_window)
            # Immediate cleanup after docking signal
            self.destroy_all_overlays()
            
            # Final forceful visual refresh after a short delay
            QTimer.singleShot(10, lambda: self._cleanup_container_overlays(root_window))
            return

        # --- Standard Docking Logic ---
        container_to_modify = None
        target_node = None
        target_parent = None

        if isinstance(target_entity, DockableWidget):
            # Target is a widget, so we need to find its host container and model nodes.
            target_node, target_parent, container_to_modify = self.model.find_host_info(target_entity)
            # If the target is a floating widget, we need special handling.
            if isinstance(container_to_modify, DockableWidget):
                # The private helper will handle emitting its own signal upon creating a new container
                return self._dock_to_floating_widget(source_widget, container_to_modify, dock_location)

        elif isinstance(target_entity, DockContainer):
            # Target is a container, so it's the one we'll modify.
            container_to_modify = target_entity
            target_node = self.model.roots.get(container_to_modify)

            # FIX: If docking to an empty container, just replace its root.
            if target_node and not target_node.children:
                self.model.unregister_widget(source_widget)
                source_widget.hide()
                self.model.roots[container_to_modify] = source_node_to_move
                self._render_layout(container_to_modify)
                # Force immediate visual update
                container_to_modify.update()
                container_to_modify.repaint()
                
                self.signals.widget_docked.emit(source_widget, container_to_modify)
                # Immediate cleanup after docking signal
                self.destroy_all_overlays()
                
                # Final forceful visual refresh after a short delay
                QTimer.singleShot(10, lambda: self._cleanup_container_overlays(container_to_modify))
                return  # Operation is complete

            target_parent = None  # Otherwise, proceed to split the root node.

        if not container_to_modify:
            print(f"ERROR: Could not resolve a container to dock into.")
            return

        # At this point, we have the container to modify and the target node within it.
        self.model.unregister_widget(source_widget)
        source_widget.hide()

        self._save_splitter_sizes_to_model(container_to_modify.splitter, self.model.roots[container_to_modify])

        if dock_location == 'center' and isinstance(target_node, TabGroupNode):
            all_source_widgets = self.model.get_all_widgets_from_node(source_node_to_move)
            target_node.children.extend(all_source_widgets)
        else:
            orientation = Qt.Orientation.Vertical if dock_location in ["top", "bottom"] else Qt.Orientation.Horizontal
            new_splitter = SplitterNode(orientation=orientation)
            if dock_location in ["top", "left"]:
                new_splitter.children = [source_node_to_move, target_node]
            else:
                new_splitter.children = [target_node, source_node_to_move]

            if target_parent is None:
                # The target was the root node, so the new splitter becomes the new root.
                self.model.roots[container_to_modify] = new_splitter
            elif isinstance(target_parent, SplitterNode):
                # Replace the old target node with the new splitter in the parent.
                try:
                    idx = target_parent.children.index(target_node)
                    target_parent.children[idx] = new_splitter
                except (ValueError, IndexError):
                    print("ERROR: Consistency error during model update.")
                    # As a fallback, just make it the new root.
                    self.model.roots[container_to_modify] = new_splitter

        # Clean up any overlays before rendering
        if hasattr(container_to_modify, 'overlay') and container_to_modify.overlay:
            container_to_modify.overlay.destroy_overlay()
            container_to_modify.overlay = None
            
        self._render_layout(container_to_modify)
        
        # Force immediate visual update before cleanup
        container_to_modify.update()
        container_to_modify.repaint()
        
        self.signals.widget_docked.emit(source_widget, container_to_modify)
        # Immediate cleanup after docking signal
        self.destroy_all_overlays()
        
        # Additional cleanup with slight delay to catch any lingering visual artifacts
        QTimer.singleShot(10, lambda: self._cleanup_container_overlays(container_to_modify))

    def _cleanup_container_overlays(self, container):
        """
        Targeted cleanup of overlays specifically on a container and its children.
        """
        if not container or self.is_deleted(container):
            return
            
        # Clean overlay on the container itself
        if hasattr(container, 'overlay') and container.overlay:
            container.overlay.destroy_overlay()
            container.overlay = None
            
        # Clean overlays on all child widgets
        for child in container.findChildren(QWidget):
            if hasattr(child, 'overlay') and child.overlay:
                child.overlay.destroy_overlay()
                child.overlay = None
                
        # AGGRESSIVE VISUAL CLEANUP: Force complete redraw of the container and all children
        def force_repaint_recursive(widget):
            if widget and not self.is_deleted(widget):
                widget.update()
                widget.repaint()
                # Also repaint all children to ensure overlay graphics are gone
                for child in widget.findChildren(QWidget):
                    if not self.is_deleted(child):
                        try:
                            child.update()
                            child.repaint()
                        except TypeError:
                            # Some widgets like QTableWidget have update() methods with required parameters
                            # Skip these and let Qt handle their updates naturally
                            pass
        
        force_repaint_recursive(container)
        
        # Process any pending paint events immediately
        QApplication.processEvents()

    def _dock_to_floating_widget(self, source_widget, target_widget, dock_location):
        """
        Private helper to handle the specific case of docking any source
        to a standalone, floating DockableWidget. This always creates a new
        DockContainer to house them both.
        """
        source_node_to_move = self.model.roots.get(source_widget)
        target_node_to_move = self.model.roots.get(target_widget)

        if not source_node_to_move or not target_node_to_move:
            print("ERROR: Cannot find source or target node for floating dock operation.")
            return

        # Unregister both floating widgets from the model.
        self.model.unregister_widget(source_widget)
        self.model.unregister_widget(target_widget)

        new_root_node = None
        if dock_location == 'center':
            # Merge all widgets from both sources into the target's node.
            all_source_widgets = self.model.get_all_widgets_from_node(source_node_to_move)
            target_node_to_move.children.extend(all_source_widgets)
            new_root_node = target_node_to_move
        else:
            orientation = Qt.Orientation.Vertical if dock_location in ["top", "bottom"] else Qt.Orientation.Horizontal
            new_splitter = SplitterNode(orientation=orientation)
            if dock_location in ["top", "left"]:
                new_splitter.children = [source_node_to_move, target_node_to_move]
            else:
                new_splitter.children = [target_node_to_move, source_node_to_move]
            new_root_node = new_splitter

        # Create the new container. It MUST be a standard DockContainer to allow for simplification.
        new_container = DockContainer(manager=self, parent=None)
        new_container.setGeometry(target_widget.geometry())

        # Manually register the new container. Do not use register_dock_area, which is for persistent roots.
        self.model.roots[new_container] = new_root_node
        self.containers.append(new_container)
        self.add_widget_handlers(new_container)
        self.bring_to_front(new_container)

        # Clean up overlays on both widgets before hiding them
        if hasattr(source_widget, 'overlay') and source_widget.overlay:
            source_widget.overlay.destroy_overlay()
            source_widget.overlay = None
        if hasattr(target_widget, 'overlay') and target_widget.overlay:
            target_widget.overlay.destroy_overlay()
            target_widget.overlay = None
            
        # Hide the old windows.
        source_widget.hide()
        target_widget.hide()

        # Render and show the new container.
        self._render_layout(new_container)
        new_container.show()
        new_container.on_activation_request()

        # Force immediate visual update
        new_container.update()
        new_container.repaint()
        
        # Emit the necessary signals after the operation is complete.
        self.signals.widget_docked.emit(source_widget, new_container)
        # Immediate cleanup after docking signal
        self.destroy_all_overlays()
        
        # Additional targeted cleanup for the new container
        QTimer.singleShot(10, lambda: self._cleanup_container_overlays(new_container))

    def _update_model_after_close(self, widget_to_close: DockableWidget):
        """
        INTERNAL: Updates the data model after a widget has been closed.
        This should not be called directly. Use request_close_widget.
        """
        host_tab_group, parent_node, root_window = self.model.find_host_info(widget_to_close)

        # Emit the signal before changing the model, so listeners can query the widget's state.
        self.signals.widget_closed.emit(widget_to_close.persistent_id)

        # Case 1: The widget is floating by itself.
        if widget_to_close in self.model.roots:
            self.model.unregister_widget(widget_to_close)

        # Case 2: The widget is docked inside a container.
        elif host_tab_group and isinstance(root_window, DockContainer):
            widget_node_to_remove = next((wn for wn in host_tab_group.children if wn.widget is widget_to_close), None)
            if widget_node_to_remove:
                host_tab_group.children.remove(widget_node_to_remove)
            self._simplify_model(root_window)
            if root_window in self.model.roots:
                self._render_layout(root_window)

        self.signals.layout_changed.emit()

    def request_close_widget(self, widget_to_close: DockableWidget):
        """
        Public method to safely close a single managed widget.
        """
        if self.is_deleted(widget_to_close):
            return

        host_tab_group, parent_node, root_window = self.model.find_host_info(widget_to_close)

        # Emit the signal before changing the model, so listeners can query the widget's state.
        self.signals.widget_closed.emit(widget_to_close.persistent_id)

        # Case 1: The widget is floating by itself.
        if widget_to_close in self.model.roots:
            self.model.unregister_widget(widget_to_close)

        # Case 2: The widget is docked inside a container.
        elif host_tab_group and isinstance(root_window, DockContainer):
            widget_node_to_remove = next((wn for wn in host_tab_group.children if wn.widget is widget_to_close), None)
            if widget_node_to_remove:
                host_tab_group.children.remove(widget_node_to_remove)
            self._simplify_model(root_window)
            if root_window in self.model.roots:
                self._render_layout(root_window)

        self.signals.layout_changed.emit()
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

        # Emit a close signal for every widget that is about to be closed.
        all_widgets_in_container = self.model.get_all_widgets_from_node(root_node)
        for widget_node in all_widgets_in_container:
            self.signals.widget_closed.emit(widget_node.widget.persistent_id)

        # Unregister the container from the model and emit the layout change signal.
        self.model.unregister_widget(container_to_close)
        self.signals.layout_changed.emit()
        container_to_close.close()

    def _simplify_model(self, root_window: QWidget):
        if root_window not in self.model.roots:
            return

        # PRE-EMPTIVE CLEANUP: Destroy ALL overlays before major layout change
        self.destroy_all_overlays()

        # Determine if this window is one of our special, persistent roots.
        is_persistent_root = (root_window is self.main_window.dock_area) or \
                             isinstance(root_window, FloatingDockRoot)
                    
        # Prevent event processing during model simplification
        self._rendering_layout = True
        root_window.setUpdatesEnabled(False)
        try:
            while True:
                made_changes = False
                root_node = self.model.roots.get(root_window)
                if not root_node: break

                nodes_to_check = [(root_node, None)]
                while nodes_to_check:
                    current_node, parent_node = nodes_to_check.pop(0)
                    if isinstance(current_node, SplitterNode):
                        original_child_count = len(current_node.children)
                        current_node.children = [c for c in current_node.children if
                                                 not (isinstance(c, TabGroupNode) and not c.children)]
                        if len(current_node.children) != original_child_count:
                            made_changes = True
                            break
                        if len(current_node.children) == 1:
                            child_to_promote = current_node.children[0]
                            if parent_node is None:
                                self.model.roots[root_window] = child_to_promote
                            elif isinstance(parent_node, SplitterNode):
                                try:
                                    idx = parent_node.children.index(current_node)
                                    parent_node.children[idx] = child_to_promote
                                except ValueError:
                                    print("ERROR: Consistency error during model simplification.")
                            made_changes = True
                            break
                        for child in current_node.children:
                            nodes_to_check.append((child, current_node))

                if made_changes:
                    self._render_layout(root_window)
                    continue

                root_node = self.model.roots.get(root_window)
                if not root_node:
                    break

                # A regular container that becomes empty should be closed.
                # A persistent root should be preserved.
                if (isinstance(root_node, (SplitterNode, TabGroupNode)) and not root_node.children):
                    if not is_persistent_root:
                        # Clean up overlay before closing
                        if hasattr(root_window, 'overlay') and root_window.overlay:
                            root_window.overlay.destroy_overlay()
                            root_window.overlay = None
                        self.model.unregister_widget(root_window)
                        root_window.close()
                    return  # Stop simplification for this window.

                # A regular container with one widget should become that widget.
                if isinstance(root_node, TabGroupNode) and len(root_node.children) == 1:
                    if not is_persistent_root:
                        widget_to_undock = root_node.children[0].widget
                        container_geometry = root_window.geometry()

                        # Capture the maximized state from the old container.
                        was_maximized = getattr(root_window, '_is_maximized', False)
                        normal_geometry = getattr(root_window, '_normal_geometry', None)

                        # Clean up overlay before closing
                        if hasattr(root_window, 'overlay') and root_window.overlay:
                            root_window.overlay.destroy_overlay()
                            root_window.overlay = None
                            
                        # PHANTOM OVERLAY FIX: Force synchronous processing of paint events
                        # This ensures overlay repaint completes before container is hidden
                        QApplication.processEvents()
                            
                        root_window.hide()
                        self.model.unregister_widget(root_window)
                        root_window.close()

                        # Call the updated function with the captured state.
                        newly_floated_window = self.create_floating_window(
                            [widget_to_undock], container_geometry, was_maximized, normal_geometry
                        )

                        if newly_floated_window and not self.is_deleted(newly_floated_window):
                            newly_floated_window.raise_()
                            newly_floated_window.activateWindow()
                        return

                break
        finally:
            # Always clear the flag and re-enable updates
            self._rendering_layout = False
            if not self.is_deleted(root_window):
                root_window.setUpdatesEnabled(True)
                root_window.update()

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
            # The fix is here: Call the new public method.
            self.request_close_widget(widget)

    def undock_tab_group(self, tab_widget: QTabWidget):
        # PRE-EMPTIVE CLEANUP: Destroy ALL overlays before major layout change
        self.destroy_all_overlays()
        # PHANTOM OVERLAY FIX: Force immediate processing of overlay destruction paint events
        QApplication.processEvents()
        
        # Prevent overlay operations during undocking
        self._undocking_in_progress = True
        try:
            # Clear dock target state
            self.last_dock_target = None
            
            if not tab_widget or not tab_widget.parentWidget(): return
            container = tab_widget.parentWidget()
            while container and not isinstance(container, DockContainer):
                container = container.parentWidget()
            if not container: return
            
            # Force destroy overlay on the container being modified
            if hasattr(container, 'overlay') and container.overlay:
                container.overlay.destroy_overlay()
                container.overlay = None

            widgets_to_move = []
            for i in range(tab_widget.count()):
                content = tab_widget.widget(i)
                owner = next((w for w in container.contained_widgets if w.content_container is content), None)
                if owner: widgets_to_move.append(owner)

            if not widgets_to_move: return

            host_tab_group, parent_node, root_window = self.model.find_host_info(widgets_to_move[0])
            if host_tab_group is None: return

            new_geom = QRect(tab_widget.mapToGlobal(QPoint(0, 0)), tab_widget.size())

            if parent_node:
                parent_node.children.remove(host_tab_group)
            else:
                self.model.unregister_widget(root_window)

            # Create the new floating window for the user's selection.
            newly_floated_window = self.create_floating_window(widgets_to_move, new_geom)

            # Simplify the old container, which may cause another window to float.
            if not self.is_deleted(root_window):
                # Force destroy overlay before simplification
                if hasattr(root_window, 'overlay') and root_window.overlay:
                    root_window.overlay.destroy_overlay() 
                    root_window.overlay = None
                self._simplify_model(root_window)
                
                # CRITICAL: Force visual cleanup on remaining container after undocking
                # This prevents stranded overlay graphics when widgets are undocked
                if root_window in self.model.roots:
                    root_window.update()
                    root_window.repaint()
                    # Additional delayed cleanup
                    QTimer.singleShot(10, lambda: self._cleanup_container_overlays(root_window))

            # After all simplification, ensure the window the user explicitly undocked is on top.
            if newly_floated_window and not self.is_deleted(newly_floated_window):
                newly_floated_window.raise_()
                newly_floated_window.activateWindow()
                # This is the crucial part: re-assert its position at the top of our manual stack.
                self.bring_to_front(newly_floated_window)

            # Emit the necessary signals for each widget that was undocked.
            for widget in widgets_to_move:
                self.signals.widget_undocked.emit(widget)

            # Emit the final signal indicating the overall layout has changed.
            self.signals.layout_changed.emit()
        finally:
            # Always clear the flag
            self._undocking_in_progress = False
            # Clear any dock-related state
            self.last_dock_target = None
            # Ensure no widgets think they're being dragged
            for widget in self.widgets + self.containers:
                if hasattr(widget, 'title_bar') and widget.title_bar:
                    widget.title_bar.moving = False
            # Schedule multiple cleanup passes to catch any lingering overlays
            QTimer.singleShot(100, self.destroy_all_overlays)
            QTimer.singleShot(200, self.force_cleanup_stuck_overlays)

    def destroy_all_overlays(self):
        """
        Ultimate brute-force cleanup of ALL overlay widgets in the application.
        This method uses QApplication.allWidgets() to find and destroy every single
        DockingOverlay instance, regardless of where it came from or whether it's orphaned.
        """
        overlays_destroyed = 0
        
        # ULTRA-AGGRESSIVE APPROACH: Multiple passes to catch stubborn overlays
        from .docking_overlay import DockingOverlay
        
        # Pass 1: Use QApplication.allWidgets() to find DockingOverlay instances
        try:
            all_widgets = QApplication.allWidgets()
            for widget in all_widgets:
                # Check if this is a DockingOverlay
                if isinstance(widget, DockingOverlay) and not self.is_deleted(widget):
                    try:
                        # Force immediate destruction without relying on destroy_overlay()
                        if self.debug_mode:
                            print(f"[DESTROY] Destroying DockingOverlay at {hex(id(widget))}")
                        widget.hide()
                        widget.close()
                        widget.setParent(None)
                        widget.deleteLater()
                        overlays_destroyed += 1
                    except RuntimeError:
                        # Widget may already be deleted - continue
                        if self.debug_mode:
                            print(f"[DESTROY] Failed to destroy overlay at {hex(id(widget))} - already deleted")
                        pass
                        
        except RuntimeError:
            # QApplication.allWidgets() can occasionally fail - continue
            pass
        
        # Pass 2: Search by class name string to catch any missed overlays
        try:
            all_widgets = QApplication.allWidgets()
            for widget in all_widgets:
                widget_class_name = widget.__class__.__name__
                if ('DockingOverlay' in widget_class_name or 
                    'Overlay' in widget_class_name) and not self.is_deleted(widget):
                    try:
                        widget.hide()
                        widget.setParent(None)
                        widget.deleteLater()
                        overlays_destroyed += 1
                    except RuntimeError:
                        pass
                        
        except RuntimeError:
            pass
            
        # Pass 3: Look for orphaned overlay-related widgets by characteristics
        try:
            all_widgets = QApplication.allWidgets()
            for widget in all_widgets:
                if not self.is_deleted(widget) and (
                    widget.objectName() == "preview_overlay" or 
                    (hasattr(widget, 'styleSheet') and widget.styleSheet() and 
                     ('rgba(0, 0, 255, 128)' in widget.styleSheet() or  # Blue preview areas
                      'lightgray' in widget.styleSheet() or  # Icon backgrounds
                      'lightblue' in widget.styleSheet() or 
                      'lightgreen' in widget.styleSheet())) or
                    # Orphaned overlay-like widgets with no parent
                    (widget.parentWidget() is None and 
                     hasattr(widget, 'styleSheet') and widget.styleSheet() and
                     'rgba(' in widget.styleSheet())):
                    try:
                        widget.hide()
                        widget.setParent(None)
                        widget.deleteLater()
                        overlays_destroyed += 1
                    except RuntimeError:
                        pass
                        
        except RuntimeError:
            pass
        
        # Clear managed overlay references
        for item in list(self.widgets) + list(self.containers):
            if not self.is_deleted(item) and hasattr(item, 'overlay'):
                item.overlay = None
        
        # Clear the active overlays tracking list
        self.active_overlays.clear()

        # Clear all tab bar drop indicators
        from .tearable_tab_widget import TearableTabBar
        for container in self.containers:
            if not self.is_deleted(container):
                for tab_bar in container.findChildren(TearableTabBar):
                    try:
                        tab_bar.set_drop_indicator_index(-1)
                    except RuntimeError:
                        pass
                        
        if self.debug_mode and overlays_destroyed > 0:
            print(f"[CLEANUP] Destroyed {overlays_destroyed} overlay widgets")

    def force_cleanup_stuck_overlays(self):
        """
        Emergency cleanup method to find and destroy any stuck overlay widgets
        that may have been missed by normal cleanup processes.
        """
        stuck_overlays_found = 0
        
        try:
            # More aggressive search for stuck overlay widgets
            all_widgets = QApplication.allWidgets()
            for widget in all_widgets:
                should_clean = False
                
                # Check for DockingOverlay instances
                from .docking_overlay import DockingOverlay
                if isinstance(widget, DockingOverlay):
                    should_clean = True
                
                # Check for widgets with blue preview styling (stuck preview overlays)
                elif (hasattr(widget, 'styleSheet') and widget.styleSheet() and 
                      ('rgba(0, 0, 255, 128)' in widget.styleSheet() or 
                       'rgba(0,0,255,128)' in widget.styleSheet().replace(' ', ''))):
                    should_clean = True
                
                # Check for widgets that look like overlay icons
                elif (hasattr(widget, 'text') and 
                      hasattr(widget, 'styleSheet') and 
                      widget.styleSheet() and
                      widget.text() in ['▲', '◀', '▼', '▶', '⧉'] and
                      ('lightgray' in widget.styleSheet() or 
                       'lightblue' in widget.styleSheet() or 
                       'lightgreen' in widget.styleSheet())):
                    should_clean = True
                
                # Check for widgets with transparent mouse events (typical of overlays)
                elif (hasattr(widget, 'testAttribute') and 
                      widget.testAttribute(Qt.WA_TransparentForMouseEvents) and
                      hasattr(widget, 'styleSheet') and widget.styleSheet() and
                      'rgba(' in widget.styleSheet()):
                    should_clean = True
                
                if should_clean and not self.is_deleted(widget):
                    try:
                        # Try to hide any child preview overlays first
                        if hasattr(widget, 'preview_overlay') and widget.preview_overlay:
                            widget.preview_overlay.hide()
                            widget.preview_overlay.setParent(None)
                            widget.preview_overlay.deleteLater()
                        
                        # Hide and destroy the widget
                        widget.hide()
                        widget.setParent(None)
                        widget.deleteLater()
                        stuck_overlays_found += 1
                    except RuntimeError:
                        pass
                        
        except RuntimeError:
            pass
            
        if self.debug_mode and stuck_overlays_found > 0:
            print(f"Force cleanup removed {stuck_overlays_found} stuck overlay widgets")
        
        return stuck_overlays_found

    def _debug_report_active_overlays(self):
        """
        Debug method to scan and report all DockingOverlay widgets currently in the application.
        This provides a comprehensive "census" of overlay state to identify stuck overlays.
        """
        if not self.debug_mode:
            return
            
        print("\n" + "="*80)
        print("--- OVERLAY STATE REPORT ---")
        print("="*80)
        
        overlay_count = 0
        visible_overlay_count = 0
        stuck_overlay_count = 0
        
        try:
            from .docking_overlay import DockingOverlay
            all_widgets = QApplication.allWidgets()
            
            for widget in all_widgets:
                if isinstance(widget, DockingOverlay):
                    overlay_count += 1
                    
                    # Gather comprehensive diagnostic information
                    try:
                        parent_widget = None
                        parent_access_error = False
                        try:
                            parent_widget = widget.parentWidget()
                        except RuntimeError as e:
                            parent_access_error = True
                            parent_widget = None
                            
                        parent_name = parent_widget.objectName() if parent_widget else "None"
                        parent_class = parent_widget.__class__.__name__ if parent_widget else "None"
                        
                        is_visible = widget.isVisible()
                        is_deleted = self.is_deleted(widget)
                        geometry = widget.geometry()
                        
                        preview_visible = False
                        preview_deleted = False
                        if hasattr(widget, 'preview_overlay') and widget.preview_overlay:
                            try:
                                preview_visible = widget.preview_overlay.isVisible()
                                preview_deleted = self.is_deleted(widget.preview_overlay)
                            except RuntimeError:
                                preview_deleted = True
                        
                        # Count visible overlays
                        if is_visible:
                            visible_overlay_count += 1
                            
                        # Enhanced stuck detection
                        is_stuck = False
                        stuck_reasons = []
                        
                        if is_visible and not is_deleted:
                            is_stuck = True
                            stuck_reasons.append("visible")
                            
                        if parent_widget is None and not is_deleted:
                            is_stuck = True
                            stuck_reasons.append("orphaned")
                            
                        if parent_access_error:
                            is_stuck = True
                            stuck_reasons.append("parent_access_error")
                            
                        if preview_visible and not preview_deleted:
                            is_stuck = True
                            stuck_reasons.append("preview_stuck")
                            
                        if is_stuck:
                            stuck_overlay_count += 1
                            
                        # Print detailed information
                        status = "STUCK" if is_stuck else "OK"
                        stuck_reason = f" - Reason: {', '.join(stuck_reasons)}" if stuck_reasons else ""
                            
                        print(f"[{status}] DockingOverlay #{overlay_count}{stuck_reason}")
                        print(f"  Parent: {parent_class}('{parent_name}') {'[ACCESS ERROR]' if parent_access_error else ''}")
                        print(f"  Visible: {is_visible}")
                        print(f"  Preview Visible: {preview_visible} {'[DELETED]' if preview_deleted else ''}")
                        print(f"  Deleted: {is_deleted}")
                        print(f"  Geometry: {geometry.x()}, {geometry.y()}, {geometry.width()}x{geometry.height()}")
                        print(f"  Memory: {hex(id(widget))}")
                        
                        # Additional validation checks
                        if is_stuck:
                            print(f"  ** DIAGNOSTIC: This overlay should be investigated **")
                            if parent_widget is None:
                                print(f"  ** ISSUE: Overlay has no parent - likely orphaned **")
                            if preview_visible:
                                print(f"  ** ISSUE: Preview overlay is visible - blue area may be stuck **")
                        print()
                        
                    except RuntimeError as e:
                        print(f"[ERROR] DockingOverlay #{overlay_count} - RuntimeError accessing properties: {e}")
                        print()
                        
        except Exception as e:
            print(f"Error during overlay report: {e}")
            
        # Summary
        print("-" * 80)
        print(f"SUMMARY: {overlay_count} total overlays, {visible_overlay_count} visible, {stuck_overlay_count} stuck")
        if stuck_overlay_count > 0:
            print(f"WARNING: {stuck_overlay_count} overlays appear to be stuck and should be investigated!")
        else:
            print("All overlays appear to be properly cleaned up.")
        print("="*80 + "\n")

    def _save_splitter_sizes_to_model(self, widget, node):
        """Recursively saves the current sizes of QSplitters into the layout model."""
        if not isinstance(widget, QSplitter) or not isinstance(node, SplitterNode):
            return

        # Save the current widget's sizes to its corresponding model node.
        node.sizes = widget.sizes()

        # If the model and view have a different number of children, we can't safely recurse.
        if len(node.children) != widget.count():
            return

        # Recursively save the sizes for any children that are also splitters.
        for i in range(widget.count()):
            child_widget = widget.widget(i)
            child_node = node.children[i]
            self._save_splitter_sizes_to_model(child_widget, child_node)

    def is_deleted(self, q_object):
        """Debug helper to check if a Qt object's C++ part is deleted."""
        if q_object is None:
            return True
        try:
            # Accessing any C++ method will raise RuntimeError if it's deleted.
            q_object.objectName()
            return False
        except RuntimeError:
            return True

    def create_new_floating_root(self):
        """
        Creates, registers, and shows a new floating root window that can
        act as a secondary main docking area.
        """
        # 1. Create an instance of our new specialized class.
        new_root_window = FloatingDockRoot(manager=self)

        # 2. Register it with the manager as a top-level dock area.
        #    This is the same method used to register the main window's dock area.
        self.register_dock_area(new_root_window)

        # 3. Show the new window.
        new_root_window.show()

        # 4. Bring it to the front of the other windows and activate it.
        new_root_window.raise_()
        new_root_window.activateWindow()
        self.bring_to_front(new_root_window)  # Also add to our manual stack.

    def undock_single_widget_by_tear(self, widget_to_undock: DockableWidget, global_mouse_pos: QPoint):
        # Clean up any overlays before tearing
        self.destroy_all_overlays()
        # PHANTOM OVERLAY FIX: Force immediate processing of overlay destruction paint events
        QApplication.processEvents()
        self.last_dock_target = None

        # Destroy overlay on the widget being undocked
        if hasattr(widget_to_undock, 'overlay') and widget_to_undock.overlay:
            widget_to_undock.overlay.destroy_overlay()
            widget_to_undock.overlay = None
            
        # 1. Find the widget in the model and remove it from its current group.
        host_tab_group, parent_node, root_window = self.model.find_host_info(widget_to_undock)
        if not host_tab_group:
            return

        # Destroy overlay on the root window before modification
        if hasattr(root_window, 'overlay') and root_window.overlay:
            root_window.overlay.destroy_overlay()
            root_window.overlay = None
            
        widget_node_to_remove = next((wn for wn in host_tab_group.children if wn.widget is widget_to_undock), None)
        if widget_node_to_remove:
            # Temporarily disable updates on the root window to prevent flicker during the transition
            if not self.is_deleted(root_window):
                root_window.setUpdatesEnabled(False)

            host_tab_group.children.remove(widget_node_to_remove)

            # 2. Calculate the geometry for the new floating window.

            # Estimate the size of the new window based on the widget's current size
            if widget_to_undock.content_container.isVisible():
                new_window_size = widget_to_undock.content_container.size()
            else:
                # Fallback size if the container wasn't the active tab
                new_window_size = QSize(300, 200)

                # Add padding for the title bar
            title_height = widget_to_undock.title_bar.height()
            new_window_size.setHeight(new_window_size.height() + title_height)

            # Calculate the top-left position so the mouse is on the title bar
            offset_y = title_height // 2
            offset_x = 50  # A reasonable horizontal offset for the drag start

            new_window_pos = global_mouse_pos - QPoint(offset_x, offset_y)
            new_geometry = QRect(new_window_pos, new_window_size)

            # 3. Create the floating window (this also re-registers the widget in the model)
            newly_floated_window = self.create_floating_window([widget_to_undock], new_geometry)

            # 4. Simplify the model for the source window (where the tab was removed from)
            if not self.is_deleted(root_window):
                self._simplify_model(root_window)
                # If the root window still exists, re-render its layout
                if root_window in self.model.roots:
                    self._render_layout(root_window)
                    # CRITICAL: Force aggressive visual cleanup on the remaining container
                    root_window.update()
                    root_window.repaint()
                # Re-enable updates
                root_window.setUpdatesEnabled(True)
                root_window.update()
                
                # Additional cleanup to ensure no visual artifacts remain
                if root_window in self.model.roots:
                    QTimer.singleShot(10, lambda: self._cleanup_container_overlays(root_window))

            # 5. Seamless Handover: Start dragging the new window immediately
            if newly_floated_window:
                # Ensure the new window is activated and on top
                newly_floated_window.on_activation_request()

                # Manually put the title bar into "moving" mode
                title_bar = newly_floated_window.title_bar
                title_bar.moving = True
                # Calculate the offset from the top-left corner of the new window to the mouse
                title_bar.offset = global_mouse_pos - newly_floated_window.pos()
                # Grab the mouse so the drag continues seamlessly
                title_bar.grabMouse()

    def activate_widget(self, widget_to_activate: DockableWidget):
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

        # If the widget is in a container, we need to select its tab first.
        if isinstance(root_window, DockContainer):
            all_tabs = root_window.findChildren(QTabWidget)
            for tab_widget in all_tabs:
                if tab_widget.isAncestorOf(widget_to_activate.content_container):
                    tab_widget.setCurrentWidget(widget_to_activate.content_container)
                    break  # Found the tab, no need to keep searching

        # Now, activate the top-level window (which could be the widget itself or its container)
        root_window.on_activation_request()

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """
        Intercepts events for managed widgets to handle global drag-and-drop.
        This is the main entry point for the manager to receive mouse events
        from its filtered widgets.
        """
        # Ignore all events during layout rendering or undocking to prevent phantom overlays
        if self._rendering_layout or self._undocking_in_progress:
            return False
            
        if event.type() == QEvent.Type.MouseMove:

            dragging_widget = None
            for widget in self.widgets + self.containers:
                if self.is_deleted(widget):
                    continue
                if hasattr(widget, 'title_bar') and widget.title_bar and widget.title_bar.moving:
                    dragging_widget = widget
                    break

            if dragging_widget:
                self.handle_drag_move(dragging_widget, event)
                return True
            else:
                # No widget is being dragged, ensure no overlays are shown
                if self.active_overlays:
                    self.destroy_all_overlays()

        return super().eventFilter(obj, event)
        
    def _clean_orphaned_overlays(self):
        """
        Audits and heals the active_overlays list by removing invalid entries
        and destroying orphaned overlay widgets found in the application.
        """
        # Step 1: Clean up the active_overlays tracking list
        items_to_remove = []
        
        for item in self.active_overlays[:]:  # Create a copy to avoid modification during iteration
            should_remove = False
            
            # Check if the item itself is deleted
            if self.is_deleted(item):
                should_remove = True
            # Check if the overlay is deleted or invalid
            elif hasattr(item, 'overlay'):
                if not item.overlay or self.is_deleted(item.overlay):
                    should_remove = True
                else:
                    # Check for parent-child relationship inconsistencies
                    try:
                        overlay_parent = item.overlay.parentWidget()
                        
                        if isinstance(item, DockableWidget):
                            # For docked widgets, overlay should be parented to the container
                            if item.parent_container:
                                if overlay_parent != item.parent_container:
                                    should_remove = True
                            # For floating widgets, overlay should be parented to the widget itself
                            else:
                                if overlay_parent != item:
                                    should_remove = True
                        elif isinstance(item, DockContainer):
                            # For containers, overlay should be parented to the container
                            if overlay_parent != item:
                                should_remove = True
                                
                    except RuntimeError:
                        # Overlay access failed, mark for removal
                        should_remove = True
            else:
                # Item has no overlay attribute, remove from tracking
                should_remove = True
                
            if should_remove:
                items_to_remove.append(item)
                
        # Remove invalid items from tracking and destroy their overlays
        for item in items_to_remove:
            if item in self.active_overlays:
                self.active_overlays.remove(item)
            if hasattr(item, 'overlay') and item.overlay:
                try:
                    if not self.is_deleted(item.overlay):
                        item.overlay.destroy_overlay()
                    item.overlay = None
                except RuntimeError:
                    pass
                    
        # Step 2: Scan for orphaned overlays not in our tracking lists
        from .docking_overlay import DockingOverlay
        try:
            for widget in QApplication.allWidgets():
                if isinstance(widget, DockingOverlay) and not self.is_deleted(widget):
                    # Check if this overlay has no parent (orphaned)
                    if widget.parentWidget() is None:
                        try:
                            widget.destroy_overlay()
                            if self.debug_mode:
                                print(f"[AUDIT] Destroyed orphaned overlay at {hex(id(widget))}")
                        except RuntimeError:
                            pass
        except RuntimeError:
            pass
