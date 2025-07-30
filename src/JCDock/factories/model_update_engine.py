from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSplitter

from ..model.dock_model import SplitterNode, TabGroupNode, WidgetNode
from ..widgets.dock_panel import DockPanel
from ..widgets.dock_container import DockContainer


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
        self._is_docking_operation = False
    
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
                        # Remove empty TabGroupNodes and adjust sizes proportionally
                        non_empty_children = []
                        remaining_indices = []
                        for i, child in enumerate(current_node.children):
                            if not (isinstance(child, TabGroupNode) and not child.children):
                                non_empty_children.append(child)
                                remaining_indices.append(i)
                        
                        if len(non_empty_children) != len(current_node.children):
                            print(f"SIMPLIFY: Removing {len(current_node.children) - len(non_empty_children)} empty children from splitter")
                            print(f"  Original children: {len(current_node.children)}, Remaining: {len(non_empty_children)}")
                            print(f"  Original sizes: {current_node.sizes}")
                            
                            # Some children were removed, redistribute their space proportionally
                            if current_node.sizes and len(current_node.sizes) == len(current_node.children) and remaining_indices:
                                # Get sizes of remaining children
                                remaining_sizes = [current_node.sizes[i] for i in remaining_indices]
                                
                                # Calculate total space from all original children
                                total_original_space = sum(current_node.sizes)
                                
                                print(f"  Remaining indices: {remaining_indices}")
                                print(f"  Remaining sizes: {remaining_sizes}")
                                print(f"  Total original space: {total_original_space}")
                                
                                # Redistribute the total space proportionally among remaining children
                                remaining_total = sum(remaining_sizes)
                                if remaining_total > 0:
                                    redistributed_sizes = []
                                    for size in remaining_sizes:
                                        proportion = size / remaining_total
                                        new_size = int(proportion * total_original_space)
                                        redistributed_sizes.append(max(new_size, 50))  # Minimum size
                                    current_node.sizes = redistributed_sizes
                                    print(f"  Redistributed sizes: {redistributed_sizes}")
                                else:
                                    # All remaining children had zero size, distribute equally
                                    equal_size = max(total_original_space // len(non_empty_children), 100)
                                    current_node.sizes = [equal_size] * len(non_empty_children)
                                    print(f"  Equal distribution (zero remaining): {current_node.sizes}")
                            
                            current_node.children = non_empty_children
                            made_changes = True
                            break
                            
                        # Promote single child splitters while preserving parent's size allocation
                        if len(current_node.children) == 1:
                            child_to_promote = current_node.children[0]
                            print(f"SIMPLIFY: Promoting single child from splitter")
                            print(f"  Current node sizes: {current_node.sizes}")
                            print(f"  Child to promote: {type(child_to_promote).__name__}")
                            
                            if parent_node is None:
                                if not is_persistent_root:
                                    print(f"  Promoting to root")
                                    self.manager.model.roots[root_window] = child_to_promote
                                    made_changes = True
                                    break
                            elif isinstance(parent_node, SplitterNode):
                                try:
                                    idx = parent_node.children.index(current_node)
                                    print(f"  Promoting to parent at index {idx}")
                                    print(f"  Parent sizes before: {parent_node.sizes}")
                                    parent_node.children[idx] = child_to_promote
                                    # Preserve the size allocation for this position
                                    # The size at idx should remain the same since the promoted child takes the full space
                                    print(f"  Parent sizes after: {parent_node.sizes}")
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
            # Note: Complex relationship preservation system removed
            # Relying solely on direct splitter sizes stored in model
            
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

    def capture_widget_size_relationships(self, root_window):
        """
        DEPRECATED: Complex relationship preservation system removed.
        Use save_splitter_sizes_to_model() for direct size preservation.
        """
        print("WARNING: capture_widget_size_relationships is deprecated. Use save_splitter_sizes_to_model() instead.")
        pass

    def apply_preserved_relationships(self, root_window):
        """
        DEPRECATED: Complex relationship preservation system removed.
        Direct splitter sizes are now preserved automatically in the model.
        """
        print("WARNING: apply_preserved_relationships is deprecated. Direct splitter sizes are preserved in model.")
        pass

    def _adjust_splitter_sizes_for_relationships(self, root_window, node, widget_ids, relationships):
        """
        DEPRECATED: Complex relationship adjustment system removed.
        """
        pass

    def _debug_print_splitter_hierarchy(self, qt_widget, model_node, stage, indent=0):
        """
        Debug method to print the current splitter hierarchy and sizes.
        """
        prefix = "  " * indent
        
        if hasattr(qt_widget, 'orientation'):  # QSplitter
            orientation = "H" if qt_widget.orientation() == Qt.Horizontal else "V"
            sizes = qt_widget.sizes()
            model_sizes = model_node.sizes if hasattr(model_node, 'sizes') else []
            print(f"{prefix}Splitter ({orientation}): QT sizes={sizes}, Model sizes={model_sizes}")
            
            for i in range(qt_widget.count()):
                child_widget = qt_widget.widget(i)
                child_node = model_node.children[i] if hasattr(model_node, 'children') and i < len(model_node.children) else None
                self._debug_print_splitter_hierarchy(child_widget, child_node, stage, indent + 1)
                
        elif hasattr(qt_widget, 'count'):  # QTabWidget
            print(f"{prefix}TabWidget: {qt_widget.count()} tabs")
            for i in range(qt_widget.count()):
                tab_widget = qt_widget.widget(i)
                dock_widget = tab_widget.property("dockable_widget") if tab_widget else None
                if dock_widget:
                    size = tab_widget.size()
                    print(f"{prefix}  Tab {i}: {dock_widget.persistent_id} ({size.width()}x{size.height()})")
        else:
            # Individual widget
            size = qt_widget.size()
            print(f"{prefix}Widget: {qt_widget.__class__.__name__} ({size.width()}x{size.height()})")

    def calculate_initial_splitter_sizes(self, target_node, dock_location, container):
        """
        Calculates appropriate initial sizes for a new splitter node based on existing
        layout proportions and the target widget size.
        """
        print(f"\n=== CALCULATING INITIAL SPLITTER SIZES FOR DOCKING ===")
        print(f"Target node: {type(target_node).__name__}")
        print(f"Dock location: {dock_location}")
        print(f"Container: {container}")
        
        if not hasattr(container, 'splitter') or not container.splitter:
            print("No splitter found in container, using default [50, 50]")
            return [50, 50]  # Default equal split
            
        # Get the target widgets to determine if we have valid targets
        target_widgets = self.manager.model.get_all_widgets_from_node(target_node)
        if not target_widgets:
            print("No target widgets found, using default [50, 50]")
            return [50, 50]
        
        # For docking operations, the new widget gets a smaller proportional size
        # We'll give it approximately 25% of the target's space initially
        # This better preserves existing proportions while providing reasonable space for the new widget
        if dock_location in ["top", "bottom"]:
            # Vertical split - target keeps ~75%, new widget gets ~25%
            target_proportion = 75
            source_proportion = 25
        else:  # left, right
            # Horizontal split - target keeps ~75%, new widget gets ~25%  
            target_proportion = 75
            source_proportion = 25
            
        if dock_location in ["top", "left"]:
            calculated_sizes = [source_proportion, target_proportion]
        else:
            calculated_sizes = [target_proportion, source_proportion]
            
        print(f"Calculated initial sizes: {calculated_sizes}")
        print("=== END DOCKING SIZE CALCULATION ===\n")
        return calculated_sizes
    
    def set_docking_operation_mode(self, is_docking: bool):
        """
        Sets whether we're currently in a docking operation.
        During docking operations, relationship preservation is skipped.
        """
        self._is_docking_operation = is_docking
        if is_docking:
            print("DOCKING: Enabled docking operation mode - relationship preservation will be skipped")
        else:
            print("DOCKING: Disabled docking operation mode - relationship preservation will resume")
    
    def _get_node_current_size(self, target_node, container):
        """
        Gets the current pixel size of a node within the container's layout.
        """
        if not hasattr(container, 'splitter') or not container.splitter:
            return None
            
        # For now, return a simple approximation based on container size
        # This could be enhanced to traverse the actual splitter hierarchy
        container_size = container.size()
        # Use width for horizontal splits, height for vertical splits
        return min(container_size.width(), container_size.height())