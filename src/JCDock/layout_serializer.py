import pickle
from PySide6.QtWidgets import QSplitter
from PySide6.QtCore import QRect, Qt

from .dock_model import LayoutModel, AnyNode, SplitterNode, TabGroupNode, WidgetNode
from .dock_container import DockContainer
from .floating_dock_root import FloatingDockRoot


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

        # Handle main window layout first
        if self.manager.main_window and self.manager.main_window.dock_area in self.manager.model.roots:
            main_dock_area = self.manager.main_window.dock_area
            main_root_node = self.manager.model.roots[main_dock_area]

            if hasattr(main_dock_area, 'splitter'):
                self._save_splitter_sizes_to_model(main_dock_area.splitter, main_root_node)

            main_window_state = {
                'class': self.manager.main_window.__class__.__name__,
                'geometry': self.manager.main_window.geometry().getRect(),
                'is_maximized': self.manager.main_window.isMaximized(),
                'normal_geometry': None,
                'content': self._serialize_node(main_root_node)
            }
            layout_data.append(main_window_state)

        # Handle floating windows
        for window, root_node in self.manager.model.roots.items():
            if window is (self.manager.main_window.dock_area if self.manager.main_window else None):
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
            return {
                'type': 'WidgetNode',
                'id': node.widget.persistent_id,
                'margin': getattr(node.widget, '_content_margin_size', 5)
            }
        return {}

    def load_layout_from_bytearray(self, data: bytearray):
        """
        Deserializes layout data and recreates the dock layout.
        
        Args:
            data: Binary layout data from save_layout_to_bytearray()
        """
        # No longer need to check for widget_factory - we use the registry system

        self._clear_layout()

        try:
            layout_data = pickle.loads(data)
        except Exception as e:
            print(f"Error deserializing layout data: {e}")
            return

        loaded_widgets_cache = {}

        for window_state in layout_data:
            window_class = window_state['class']

            # Handle main window
            if window_class == 'MainDockWindow':
                container = self.manager.main_window.dock_area
                geom_tuple = window_state['geometry']
                self.manager.main_window.setGeometry(geom_tuple[0], geom_tuple[1], geom_tuple[2], geom_tuple[3])

                if window_state.get('is_maximized', False):
                    self.manager.main_window.showMaximized()

                self.manager.model.roots[container] = self._deserialize_node(window_state['content'], loaded_widgets_cache)
                self.manager._render_layout(container)
                continue

            # Handle floating windows
            new_window = None
            if window_class == 'DockPanel':
                widget_data = window_state['content']['children'][0]
                persistent_id = widget_data.get('id')

                # CRITICAL FIX: Use unique cache key for floating windows too
                cache_key = f"{persistent_id}_{id(widget_data)}_{len(loaded_widgets_cache)}"
                
                if cache_key in loaded_widgets_cache:
                    new_window = loaded_widgets_cache[cache_key]
                else:
                    # Use the DockingManager's internal panel factory from the registry
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

            elif window_class == 'DockContainer':
                new_window = DockContainer(manager=self.manager, parent=None)
                self.manager.model.roots[new_window] = self._deserialize_node(window_state['content'], loaded_widgets_cache)
                self.manager.containers.append(new_window)
                self.manager.add_widget_handlers(new_window)
                self.manager.bring_to_front(new_window)
                self.manager._render_layout(new_window)

            elif window_class == 'FloatingDockRoot':
                new_window = FloatingDockRoot(manager=self.manager)
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
        # Make a copy of the list of windows to close, as the original list will be modified
        windows_to_close = list(self.manager.model.roots.keys())

        for window in windows_to_close:
            # Don't close persistent roots, just clear their content
            if self.manager._is_persistent_root(window):
                # Clear the splitter from the persistent root
                if hasattr(window, 'splitter') and window.splitter:
                    window.splitter.setParent(None)
                    window.splitter.deleteLater()
                    window.splitter = None
                # Reset its model to an empty node
                self.manager.model.roots[window] = SplitterNode(orientation=Qt.Horizontal)
                # Re-render to show empty state
                self.manager._render_layout(window)
                continue

            # For all other floating windows, unregister and close them
            if window in self.manager.model.roots:
                self.manager.model.unregister_widget(window)

            window.setParent(None)
            window.close()

        # Reset all manager state
        self.manager.widgets.clear()
        self.manager.containers.clear()
        self.manager.window_stack.clear()
        self.manager.floating_widget_count = 0
        # Re-add the main window's dock area back to the containers list
        if self.manager.main_window:
            self.manager.containers.append(self.manager.main_window.dock_area)
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
            children = [self._deserialize_node(child_data, loaded_widgets_cache) for child_data in node_data['children']]
            return SplitterNode(
                orientation=node_data['orientation'],
                sizes=node_data['sizes'],
                children=children
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

            # CRITICAL FIX: Create unique cache key for each widget instance
            # This prevents multiple widgets of the same type from sharing the same instance
            cache_key = f"{persistent_id}_{id(node_data)}_{len(loaded_widgets_cache)}"
            
            if cache_key in loaded_widgets_cache:
                new_widget = loaded_widgets_cache[cache_key]
            else:
                # Use the DockingManager's internal panel factory from the registry
                try:
                    new_widget = self.manager._create_panel_from_key(persistent_id)
                    if new_widget:
                        loaded_widgets_cache[cache_key] = new_widget
                        # Important: Register the widget with the manager
                        self.manager.register_widget(new_widget)
                except ValueError as e:
                    print(f"ERROR: Cannot recreate widget '{persistent_id}': {e}")
                    new_widget = None

            if new_widget:
                return WidgetNode(widget=new_widget)

        return TabGroupNode()

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