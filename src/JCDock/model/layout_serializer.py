import pickle
from PySide6.QtWidgets import QSplitter
from PySide6.QtCore import QRect, Qt

from .dock_model import LayoutModel, AnyNode, SplitterNode, TabGroupNode, WidgetNode
from ..widgets.dock_container import DockContainer


class LayoutSerializer:
    """
    Handles serialization and deserialization of dock layout state.
    Extracted from DockingManager to improve separation of concerns.
    """
    
    def __init__(self, manager):
        """
        Initialize with reference to DockingManager for accessing state.
        
        Args:
            manager: Reference to the DockingManager instance
        """
        self.manager = manager

    def save_layout_to_bytearray(self) -> bytearray:
        """
        Serializes the entire layout state to binary data.
        
        Returns:
            bytearray: Serialized layout data that can be saved to file
        """
        layout_data = []

        if self.manager.main_window and self.manager.main_window in self.manager.model.roots:
            main_dock_area = self.manager.main_window
            main_root_node = self.manager.model.roots[main_dock_area]

            if hasattr(main_dock_area, 'splitter'):
                self._save_splitter_sizes_to_model(main_dock_area.splitter, main_root_node)

            main_window_state = {
                'class': self.manager.main_window.__class__.__name__,
                'geometry': self.manager.main_window.geometry().getRect(),
                'is_maximized': self.manager.main_window.isMaximized(),
                'normal_geometry': None,
                'is_main_window': getattr(self.manager.main_window, 'is_main_window', True),
                'auto_persistent_root': getattr(self.manager.main_window, '_is_persistent_root', False),
                'content': self._serialize_node(main_root_node)
            }
            layout_data.append(main_window_state)

        for window, root_node in self.manager.model.roots.items():
            if window is self.manager.main_window:
                continue

            if self.manager.is_deleted(window):
                continue

            if hasattr(window, 'splitter'):
                self._save_splitter_sizes_to_model(window.splitter, root_node)

            window_state = {
                'class': window.__class__.__name__,
                'geometry': window.geometry().getRect(),
                'is_maximized': getattr(window, '_is_maximized', False),
                'normal_geometry': None,
                'is_main_window': getattr(window, 'is_main_window', False),
                'auto_persistent_root': getattr(window, '_is_persistent_root', False),
                'content': self._serialize_node(root_node)
            }
            if window_state['is_maximized']:
                normal_geom = getattr(window, '_normal_geometry', None)
                if normal_geom:
                    window_state['normal_geometry'] = normal_geom.getRect()

            layout_data.append(window_state)

        return pickle.dumps(layout_data)

    def _serialize_node(self, node: AnyNode) -> dict:
        """
        Recursively serializes a layout node to a dictionary.
        
        Args:
            node: The layout node to serialize
            
        Returns:
            dict: Serialized node data
        """
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
            serialized_data = {
                'type': 'WidgetNode',
                'id': node.widget.persistent_id,
                'margin': getattr(node.widget, '_content_margin_size', 5)
            }
            
            # Check if the content widget supports state persistence
            content_widget = getattr(node.widget, 'content_widget', None)
            state_saved = False
            
            # First try: Check for built-in get_dock_state method
            if content_widget and hasattr(content_widget, 'get_dock_state') and callable(getattr(content_widget, 'get_dock_state')):
                try:
                    widget_state = content_widget.get_dock_state()
                    if isinstance(widget_state, dict):
                        serialized_data['internal_state'] = widget_state
                        state_saved = True
                except Exception as e:
                    # Gracefully handle any errors in user's state saving logic
                    pass
            
            # Second try: Check for ad-hoc state handlers if built-in method failed
            if not state_saved and node.widget.persistent_id in self.manager.instance_state_handlers:
                state_provider, state_restorer = self.manager.instance_state_handlers[node.widget.persistent_id]
                if state_provider is not None and content_widget is not None:
                    try:
                        widget_state = state_provider(content_widget)
                        if isinstance(widget_state, dict):
                            serialized_data['internal_state'] = widget_state
                    except Exception as e:
                        # Gracefully handle any errors in user's ad-hoc state saving logic
                        pass
            
            return serialized_data
        return {}

    def load_layout_from_bytearray(self, data: bytearray):
        """
        Deserializes layout data and recreates the dock layout.
        
        Args:
            data: Binary layout data from save_layout_to_bytearray()
        """

        self._clear_layout()

        try:
            layout_data = pickle.loads(data)
        except Exception as e:
            print(f"Error deserializing layout data: {e}")
            return

        loaded_widgets_cache = {}

        for window_state in layout_data:
            window_class = window_state['class']
            new_window = None

            # Use property-based detection instead of class-based detection
            is_main_window = window_state.get('is_main_window', False)
            
            # Backward compatibility: if no is_main_window property, fall back to class-based detection
            if 'is_main_window' not in window_state:
                is_main_window = window_class in ('MainDockWindow')

            if is_main_window and window_class in ('DockContainer', 'MainDockWindow'):
                # This is the main window - restore to existing main window
                container = self.manager.main_window
                geom_tuple = window_state['geometry']
                self.manager.main_window.setGeometry(geom_tuple[0], geom_tuple[1], geom_tuple[2], geom_tuple[3])

                if window_state.get('is_maximized', False):
                    self.manager.main_window.showMaximized()

                self.manager.model.roots[container] = self._deserialize_node(window_state['content'], loaded_widgets_cache)
                self.manager._render_layout(container)
                continue

            elif window_class == 'DockPanel':
                widget_data = window_state['content']['children'][0]
                persistent_id = widget_data.get('id')

                cache_key = f"{persistent_id}_{id(widget_data)}_{len(loaded_widgets_cache)}"
                
                if cache_key in loaded_widgets_cache:
                    new_window = loaded_widgets_cache[cache_key]
                else:
                    try:
                        new_window = self.manager._create_panel_from_key(persistent_id)
                        if new_window:
                            loaded_widgets_cache[cache_key] = new_window
                    except ValueError as e:
                        print(f"ERROR: Cannot recreate widget '{persistent_id}': {e}")
                        new_window = None

                if new_window:
                    self.manager.model.roots[new_window] = self._deserialize_node(window_state['content'], loaded_widgets_cache)
                    self.manager.register_widget(new_window)

            elif window_class in ('DockContainer', 'FloatingDockRoot'):
                # This is a floating container - create new floating window
                auto_persistent_root = window_state.get('auto_persistent_root', True)  # Default to True for floating containers
                
                new_window = DockContainer(
                    manager=self.manager,
                    show_title_bar=True,
                    window_title="Restored Floating Window",
                    is_main_window=False,
                    auto_persistent_root=auto_persistent_root
                )
                self.manager.register_dock_area(new_window)
                self.manager.model.roots[new_window] = self._deserialize_node(window_state['content'], loaded_widgets_cache)
                self.manager._render_layout(new_window)

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
                self.manager.bring_to_front(new_window)

    def _clear_layout(self):
        """
        Closes all managed windows and resets the model to a clean state.
        """
        windows_to_close = list(self.manager.model.roots.keys())

        for window in windows_to_close:
            if self.manager._is_persistent_root(window):
                if hasattr(window, 'splitter') and window.splitter:
                    window.splitter.setParent(None)
                    window.splitter.deleteLater()
                    window.splitter = None
                self.manager.model.roots[window] = SplitterNode(orientation=Qt.Horizontal)
                self.manager._render_layout(window)
                continue
            if window in self.manager.model.roots:
                self.manager.model.unregister_widget(window)

            window.setParent(None)
            window.close()
        self.manager.widgets.clear()
        self.manager.containers.clear()
        self.manager.window_stack.clear()
        self.manager.floating_widget_count = 0
        if self.manager.main_window:
            self.manager.containers.append(self.manager.main_window)
            self.manager.window_stack.append(self.manager.main_window)

    def _deserialize_node(self, node_data: dict, loaded_widgets_cache: dict) -> AnyNode:
        """
        Recursively recreates layout nodes from serialized data.
        
        Args:
            node_data: Serialized node dictionary
            loaded_widgets_cache: Cache of already created widgets
            
        Returns:
            AnyNode: Recreated layout node
        """
        node_type = node_data.get('type')

        if node_type == 'SplitterNode':
            children_data = node_data.get('children', [])
            children = [
                node for node in (self._deserialize_node(child, loaded_widgets_cache) for child in children_data) if node is not None
            ]
            return SplitterNode(
                orientation=node_data['orientation'],
                sizes=node_data['sizes'],
                children=children
            )
        elif node_type == 'TabGroupNode':
            children_data = node_data.get('children', [])
            children = [
                node for node in (self._deserialize_node(child, loaded_widgets_cache) for child in children_data) if node is not None
            ]
            return TabGroupNode(children=children)
        elif node_type == 'WidgetNode':
            persistent_id = node_data.get('id')
            if not persistent_id:
                return None  # Return None on failure

            cache_key = f"{persistent_id}_{id(node_data)}_{len(loaded_widgets_cache)}"
            
            if cache_key in loaded_widgets_cache:
                new_widget = loaded_widgets_cache[cache_key]
            else:
                # Use the DockingManager's internal panel factory from the registry
                try:
                    new_widget = self.manager._create_panel_from_key(persistent_id)
                    if new_widget:
                        loaded_widgets_cache[cache_key] = new_widget
                        self.manager.register_widget(new_widget)
                except ValueError as e:
                    print(f"ERROR: Cannot recreate widget '{persistent_id}': {e}")
                    new_widget = None

            if new_widget:
                # Check if there's saved internal state to restore
                internal_state = node_data.get('internal_state')
                if internal_state and isinstance(internal_state, dict):
                    content_widget = getattr(new_widget, 'content_widget', None)
                    state_restored = False
                    
                    # First try: Check for built-in set_dock_state method
                    if content_widget and hasattr(content_widget, 'set_dock_state') and callable(getattr(content_widget, 'set_dock_state')):
                        try:
                            content_widget.set_dock_state(internal_state)
                            state_restored = True
                        except Exception as e:
                            # Gracefully handle any errors in user's restoration logic
                            # Don't let a single faulty widget crash the entire layout load
                            pass
                    
                    # Second try: Check for ad-hoc state handlers if built-in method failed
                    if not state_restored and persistent_id in self.manager.instance_state_handlers:
                        state_provider, state_restorer = self.manager.instance_state_handlers[persistent_id]
                        if state_restorer is not None and content_widget is not None:
                            try:
                                state_restorer(content_widget, internal_state)
                            except Exception as e:
                                # Gracefully handle any errors in user's ad-hoc restoration logic
                                # Don't let a single faulty widget crash the entire layout load
                                pass
                
                return WidgetNode(widget=new_widget)

        return None  # The default fallback should also be None

    def _find_first_tab_group_node(self, node: AnyNode) -> TabGroupNode | None:
        """
        Recursively traverses a node tree to find the first TabGroupNode.
        
        Args:
            node: The node to search from
            
        Returns:
            TabGroupNode | None: First tab group found, or None
        """
        if isinstance(node, TabGroupNode):
            return node
        if isinstance(node, SplitterNode):
            for child in node.children:
                result = self._find_first_tab_group_node(child)
                if result:
                    return result
        return None

    def _save_splitter_sizes_to_model(self, widget, node):
        """
        Recursively saves the current sizes of QSplitters into the layout model.
        
        Args:
            widget: The QSplitter widget
            node: The corresponding SplitterNode in the model
        """
        if not isinstance(widget, QSplitter) or not isinstance(node, SplitterNode):
            return

        node.sizes = widget.sizes()

        if len(node.children) != widget.count():
            return

        for i in range(widget.count()):
            child_widget = widget.widget(i)
            child_node = node.children[i]
            self._save_splitter_sizes_to_model(child_widget, child_node)