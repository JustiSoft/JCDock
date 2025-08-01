from PySide6.QtWidgets import QSplitter, QTabWidget
from PySide6.QtCore import Qt
from functools import partial

from ..core.docking_state import DockingState
from .dock_model import AnyNode, SplitterNode, TabGroupNode, WidgetNode
from ..widgets.dock_panel import DockPanel
from ..widgets.dock_container import DockContainer


class LayoutRenderer:
    """
    Handles rendering of layout models into Qt widgets.
    Extracted from DockingManager to improve separation of concerns.
    """
    
    def __init__(self, manager):
        """
        Initialize with reference to DockingManager for accessing state.
        
        Args:
            manager: Reference to the DockingManager instance
        """
        self.manager = manager

    def render_layout(self, container: DockContainer, widget_to_activate: DockPanel = None):
        """
        Main layout rendering method that creates UI from model.
        
        Args:
            container: The container to render layout for
            widget_to_activate: Optional widget to activate after rendering
        """
        root_node = self.manager.model.roots.get(container)
        if not root_node:
            print(f"ERROR: Cannot render layout for unregistered container {container.objectName()}")
            return

        if hasattr(container, 'overlay') and container.overlay:
            container.overlay.destroy_overlay()
            container.overlay = None
            
        self.manager._set_state(DockingState.RENDERING)
        try:
            for widget in container.contained_widgets:
                if hasattr(widget, 'overlay') and widget.overlay:
                    widget.overlay.destroy_overlay()
                    widget.overlay = None
                    
            container.contained_widgets.clear()
            new_content_widget = self._render_node(root_node, container, widget_to_activate=widget_to_activate)
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
                
            for widget in container.contained_widgets:
                if hasattr(widget, 'content_container') and widget.content_container:
                    widget.content_container.show()
                    widget.content_container.update()

        finally:
            self.manager._set_state(DockingState.IDLE)
            
        self._update_tab_bar_visibility(container)
        container.update_dynamic_title()

    def _render_node(self, node: AnyNode, container: DockContainer, inside_splitter: bool = False, widget_to_activate: DockPanel = None, is_on_left_edge: bool = True, is_on_right_edge: bool = True, is_on_top_edge: bool = True, is_on_bottom_edge: bool = True) -> QTabWidget:
        """
        Recursively renders model nodes into Qt widgets.
        
        Args:
            node: The layout node to render
            container: The container hosting the layout
            inside_splitter: Whether this node is inside a splitter
            widget_to_activate: Optional widget to activate
            is_on_left_edge: Whether this node is on the leftmost edge of the layout
            is_on_right_edge: Whether this node is on the rightmost edge of the layout
            is_on_top_edge: Whether this node is on the topmost edge of the layout
            is_on_bottom_edge: Whether this node is on the bottommost edge of the layout
            
        Returns:
            QWidget: The rendered Qt widget
        """
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
            
            # Wire splitterMoved signal with specific splitter and model node using partial
            splitter_handler = partial(self.manager._on_splitter_moved, qt_splitter, node)
            qt_splitter.splitterMoved.connect(splitter_handler)
            
            for i, child_node in enumerate(node.children):
                # Calculate edge context for this child
                total_children = len(node.children)
                is_first_child = (i == 0)
                is_last_child = (i == total_children - 1)
                
                if node.orientation == Qt.Horizontal:
                    # For horizontal splitters, children inherit top/bottom edges from parent
                    # Left edge: child is on left edge if it's first AND parent is on left edge
                    # Right edge: child is on right edge if it's last AND parent is on right edge
                    child_left_edge = is_first_child and is_on_left_edge
                    child_right_edge = is_last_child and is_on_right_edge
                    child_top_edge = is_on_top_edge
                    child_bottom_edge = is_on_bottom_edge
                else:  # Qt.Vertical
                    # For vertical splitters, children inherit left/right edges from parent
                    # Top edge: child is on top edge if it's first AND parent is on top edge
                    # Bottom edge: child is on bottom edge if it's last AND parent is on bottom edge
                    child_left_edge = is_on_left_edge
                    child_right_edge = is_on_right_edge
                    child_top_edge = is_first_child and is_on_top_edge
                    child_bottom_edge = is_last_child and is_on_bottom_edge
                
                child_widget = self._render_node(
                    child_node, 
                    container, 
                    inside_splitter=True, 
                    widget_to_activate=widget_to_activate,
                    is_on_left_edge=child_left_edge,
                    is_on_right_edge=child_right_edge,
                    is_on_top_edge=child_top_edge,
                    is_on_bottom_edge=child_bottom_edge
                )
                if child_widget:
                    qt_splitter.addWidget(child_widget)
            # Apply preserved sizes correctly
            if node.sizes and len(node.sizes) == qt_splitter.count():
                qt_splitter.setSizes(node.sizes)
            elif node.sizes and len(node.sizes) > qt_splitter.count():
                redistributed_sizes = self._redistribute_removed_space(node.sizes, qt_splitter.count())
                qt_splitter.setSizes(redistributed_sizes)
            else:
                qt_splitter.setSizes([100] * qt_splitter.count())
            return qt_splitter
        elif isinstance(node, TabGroupNode):
            qt_tab_widget = container._create_tab_widget_with_controls()
            
            # Set dynamic border properties based on inherited position context
            self._set_border_properties(qt_tab_widget, is_on_left_edge, is_on_right_edge, is_on_top_edge, is_on_bottom_edge)
            for widget_node in node.children:
                widget = widget_node.widget
                tab_index = qt_tab_widget.addTab(widget.content_container, widget.windowTitle())
                
                # Set tab icon if the widget has one
                if hasattr(widget, 'get_icon') and widget.get_icon():
                    qt_tab_widget.setTabIcon(tab_index, widget.get_icon())
                
                widget.content_container.setProperty("dockable_widget", widget)
                if widget.original_bg_color:
                    bg_color_name = widget.original_bg_color.name()
                    widget.content_container.setStyleSheet(
                        f"#ContentContainer {{ background-color: {bg_color_name}; border-radius: 0px; }}")
                widget.parent_container = container
                widget.content_container.show()
                widget.content_container.setVisible(True)
                widget.content_container.activateWindow()
                widget.content_container.raise_()
                if hasattr(widget, 'content_widget') and widget.content_widget:
                    widget.content_widget.setVisible(True)
                if widget not in container.contained_widgets:
                    container.contained_widgets.append(widget)
                    
            if qt_tab_widget.count() > 0:
                current_index = qt_tab_widget.currentIndex()
                if current_index >= 0:
                    current_widget = qt_tab_widget.widget(current_index)
                    if current_widget:
                        current_widget.setVisible(True)
                        current_widget.update()
                        
                qt_tab_widget.update()
                qt_tab_widget.repaint()
            
            tab_count = qt_tab_widget.count()
            
            if inside_splitter:
                qt_tab_widget.tabBar().setVisible(True)
                corner_widget = qt_tab_widget.cornerWidget()
                if corner_widget:
                    corner_widget.setVisible(True)
            elif tab_count == 1 and not self.manager._is_persistent_root(container):
                qt_tab_widget.tabBar().setVisible(False)
                corner_widget = qt_tab_widget.cornerWidget()
                if corner_widget:
                    corner_widget.setVisible(False)
            else:
                qt_tab_widget.tabBar().setVisible(True)
                corner_widget = qt_tab_widget.cornerWidget()
                if corner_widget:
                    corner_widget.setVisible(True)
            
            if widget_to_activate is not None:
                for tab_index in range(qt_tab_widget.count()):
                    tab_content = qt_tab_widget.widget(tab_index)
                    if tab_content == widget_to_activate.content_container:
                        qt_tab_widget.setCurrentIndex(tab_index)
                        break
            
            return qt_tab_widget
        elif isinstance(node, WidgetNode):
            widget = node.widget
            widget.content_container.show()
            return widget.content_container

    def _update_tab_bar_visibility(self, container: DockContainer):
        """
        Updates tab bar visibility for all tab widgets in the container based on new UI rules.
        
        Args:
            container: The container to update tab bar visibility for
        """
        if not container.splitter:
            return
            
        if isinstance(container.splitter, QTabWidget):
            tab_widget = container.splitter
            tab_count = tab_widget.count()
            corner_widget = tab_widget.cornerWidget()
            
            if tab_count == 1 and not self.manager._is_persistent_root(container):
                tab_widget.tabBar().setVisible(False)
                if corner_widget:
                    corner_widget.setVisible(False)
            else:
                tab_widget.tabBar().setVisible(True)
                if corner_widget:
                    corner_widget.setVisible(True)
        else:
            tab_widgets = container.splitter.findChildren(QTabWidget)
            for tab_widget in tab_widgets:
                tab_widget.tabBar().setVisible(True)
                corner_widget = tab_widget.cornerWidget()
                if corner_widget:
                    corner_widget.setVisible(True)

    def simplify_model(self, root_window):
        """
        Removes empty nodes and simplifies model structure.
        
        Args:
            root_window: The root window to simplify the model for
        """
        if root_window not in self.manager.model.roots:
            return

        root_node = self.manager.model.roots[root_window]
        simplified_node = self._simplify_node(root_node)
        
        if self.manager._is_persistent_root(root_window):
            if simplified_node is None:
                from .dock_model import TabGroupNode
                simplified_node = TabGroupNode()
            self.manager.model.roots[root_window] = simplified_node
        elif simplified_node != root_node:
            if simplified_node is None:
                del self.manager.model.roots[root_window]
            else:
                self.manager.model.roots[root_window] = simplified_node

    def _redistribute_removed_space(self, original_sizes: list[int], target_count: int) -> list[int]:
        """
        Redistributes space from removed widgets proportionally to remaining widgets.
        
        Args:
            original_sizes: The original sizes before widgets were removed
            target_count: The number of widgets that should remain
            
        Returns:
            list[int]: Redistributed sizes for the remaining widgets
        """
        if not original_sizes or target_count <= 0:
            return [100] * target_count
            
        if len(original_sizes) <= target_count:
            # No redistribution needed
            return original_sizes[:target_count]
        
        # Calculate total space and space to redistribute
        total_original_space = sum(original_sizes)
        
        # For now, assume the removed widgets are the ones that are no longer in the model
        # This is a simplified approach - we take the first target_count widgets
        # and redistribute the remaining space proportionally
        remaining_sizes = original_sizes[:target_count]
        remaining_total = sum(remaining_sizes)
        
        if remaining_total == 0:
            return [100] * target_count
            
        # Calculate proportion of each remaining widget
        redistributed_sizes = []
        for size in remaining_sizes:
            proportion = size / remaining_total
            new_size = int(proportion * total_original_space)
            redistributed_sizes.append(max(new_size, 50))  # Minimum size of 50
            
        return redistributed_sizes

    def _simplify_node(self, node: AnyNode) -> AnyNode:
        """
        Recursively simplifies a node by removing empty nodes and flattening single-child structures.
        
        Args:
            node: The node to simplify
            
        Returns:
            AnyNode: The simplified node
        """
        if isinstance(node, SplitterNode):
            simplified_children = []
            for child in node.children:
                simplified_child = self._simplify_node(child)
                if simplified_child:
                    simplified_children.append(simplified_child)
            
            node.children = simplified_children
            
            if not node.children:
                return None
            
            if len(node.children) == 1:
                return node.children[0]
                
            return node
            
        elif isinstance(node, TabGroupNode):
            node.children = [child for child in node.children if child and isinstance(child, WidgetNode)]
            
            if not node.children:
                return None
                
            return node
            
        elif isinstance(node, WidgetNode):
            return node
            
        return None

    def update_model_after_close(self, widget_to_close: DockPanel):
        """
        Updates the model when a widget is closed.
        
        Args:
            widget_to_close: The widget that was closed
        """
        host_tab_group, host_parent_node, root_window = self.manager.model.find_host_info(widget_to_close)
        
        if not host_tab_group:
            return
            
        widget_node_to_remove = None
        for widget_node in host_tab_group.children:
            if widget_node.widget is widget_to_close:
                widget_node_to_remove = widget_node
                break
                
        if widget_node_to_remove:
            host_tab_group.children.remove(widget_node_to_remove)
            
        if root_window:
            self.simplify_model(root_window)
            if root_window in self.manager.model.roots:
                self.render_layout(root_window)
            else:
                if hasattr(root_window, 'close'):
                    root_window.close()

    def _set_border_properties(self, widget, is_on_left_edge, is_on_right_edge, is_on_top_edge, is_on_bottom_edge):
        """
        Sets dynamic border properties on a widget based on its absolute position in the layout hierarchy.
        
        Args:
            widget: The widget to set properties on
            is_on_left_edge: Whether the widget is on the absolute left edge of the layout
            is_on_right_edge: Whether the widget is on the absolute right edge of the layout
            is_on_top_edge: Whether the widget is on the absolute top edge of the layout
            is_on_bottom_edge: Whether the widget is on the absolute bottom edge of the layout
        """
        # Set border visibility based on absolute position in layout
        # A border should only be visible if the widget is at the absolute edge
        widget.setProperty("borderLeftVisible", is_on_left_edge)
        widget.setProperty("borderRightVisible", is_on_right_edge)
        widget.setProperty("borderTopVisible", is_on_top_edge)
        widget.setProperty("borderBottomVisible", is_on_bottom_edge)
        
        # Force style re-evaluation
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()