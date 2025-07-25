from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSplitter

from .dock_model import SplitterNode, TabGroupNode, WidgetNode
from .dock_panel import DockPanel
from .dock_container import DockContainer


class ModelUpdateEngine:
    """
    Handles model updates, simplification, and cleanup after widget operations.
    Manages the layout model consistency and container lifecycle.
    """
    
    def __init__(self, manager):
        """
        Initialize the model update engine.
        
        Args:
            manager: Reference to the DockingManager instance
        """
        self.manager = manager
    
    def update_model_after_close(self, widget_to_close: DockPanel):
        """
        Updates the model and layout after a widget is closed.
        
        Args:
            widget_to_close: The DockPanel that was closed
        """
        host_tab_group, parent_node, root_window = self.manager.model.find_host_info(widget_to_close)

        self.manager.signals.widget_closed.emit(widget_to_close.persistent_id)

        if widget_to_close in self.manager.model.roots:
            self.manager.model.unregister_widget(widget_to_close)

        elif host_tab_group and isinstance(root_window, DockContainer):
            currently_active_widget = self.manager._get_currently_active_widget(root_window)
            if currently_active_widget == widget_to_close:
                currently_active_widget = None
            
            widget_node_to_remove = next((wn for wn in host_tab_group.children if wn.widget is widget_to_close), None)
            if widget_node_to_remove:
                host_tab_group.children.remove(widget_node_to_remove)
            self.simplify_model(root_window, currently_active_widget)
            if root_window in self.manager.model.roots:
                self.manager._render_layout(root_window)

        self.manager.signals.layout_changed.emit()

    def simplify_model(self, root_window, widget_to_activate: DockPanel = None):
        """
        Simplifies the layout model by removing empty nodes and optimizing structure.
        
        Args:
            root_window: The root window to simplify
            widget_to_activate: Optional widget to activate after simplification
        """
        # First delegate to LayoutRenderer for basic simplification
        self.manager.layout_renderer.simplify_model(root_window)

        if root_window in self.manager.model.roots:
            self.manager._render_layout(root_window, widget_to_activate)
        else:
            if hasattr(root_window, 'close'):
                root_window.close()

        is_persistent_root = self.manager._is_persistent_root(root_window)

        try:
            while True:
                made_changes = False
                root_node = self.manager.model.roots.get(root_window)
                if not root_node: 
                    break

                nodes_to_check = [(root_node, None)]
                while nodes_to_check:
                    current_node, parent_node = nodes_to_check.pop(0)
                    if isinstance(current_node, SplitterNode):
                        original_child_count = len(current_node.children)
                        # Remove empty TabGroupNodes
                        current_node.children = [c for c in current_node.children if
                                                not (isinstance(c, TabGroupNode) and not c.children)]
                        if len(current_node.children) != original_child_count:
                            made_changes = True
                            break
                            
                        # Promote single child splitters
                        if len(current_node.children) == 1:
                            child_to_promote = current_node.children[0]
                            if parent_node is None:
                                if not is_persistent_root:
                                    self.manager.model.roots[root_window] = child_to_promote
                                    made_changes = True
                                    break
                            elif isinstance(parent_node, SplitterNode):
                                try:
                                    idx = parent_node.children.index(current_node)
                                    parent_node.children[idx] = child_to_promote
                                    made_changes = True
                                    break
                                except ValueError:
                                    print("ERROR: Consistency error during model simplification.")
                        
                        # Continue checking children
                        for child in current_node.children:
                            nodes_to_check.append((child, current_node))

                if made_changes:
                    self.manager._render_layout(root_window, widget_to_activate)
                    continue

                # Check if root node is empty
                root_node = self.manager.model.roots.get(root_window)
                if not root_node:
                    break

                if (isinstance(root_node, (SplitterNode, TabGroupNode)) and not root_node.children):
                    if not is_persistent_root:
                        # Clean up overlay before closing
                        if hasattr(root_window, 'overlay') and root_window.overlay:
                            root_window.overlay.destroy_overlay()
                            root_window.overlay = None
                        self.manager.model.unregister_widget(root_window)
                        root_window.close()
                    else:
                        # For persistent roots, reset to clean default state
                        self.manager.model.roots[root_window] = SplitterNode(orientation=Qt.Orientation.Horizontal)
                        self.manager._render_layout(root_window, widget_to_activate)
                    return  

                break
        finally:
            # Always re-enable updates
            if not self.manager.is_deleted(root_window):
                root_window.setUpdatesEnabled(True)
                root_window.update()

    def save_splitter_sizes_to_model(self, widget, node):
        """
        Recursively saves the current sizes of QSplitters into the layout model.
        
        Args:
            widget: The QSplitter widget
            node: The corresponding SplitterNode in the model
        """
        if not isinstance(widget, QSplitter) or not isinstance(node, SplitterNode):
            return

        # Save the current widget's sizes to its corresponding model node
        node.sizes = widget.sizes()

        # If the model and view have a different number of children, we can't safely recurse
        if len(node.children) != widget.count():
            return

        # Recursively save the sizes for any children that are also splitters
        for i in range(widget.count()):
            child_widget = widget.widget(i)
            child_node = node.children[i]
            self.save_splitter_sizes_to_model(child_widget, child_node)