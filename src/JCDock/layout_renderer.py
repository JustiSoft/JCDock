from PySide6.QtWidgets import QSplitter, QTabWidget
from PySide6.QtCore import Qt

from .docking_state import DockingState
from .dock_model import AnyNode, SplitterNode, TabGroupNode, WidgetNode
from .dock_panel import DockPanel
from .dock_container import DockContainer


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

        # Destroy any overlays on the container before rendering
        if hasattr(container, 'overlay') and container.overlay:
            container.overlay.destroy_overlay()
            container.overlay = None
            
        # Set state to prevent event processing during layout rendering
        self.manager._set_state(DockingState.RENDERING)
        try:
            # Clean up overlays on all currently contained widgets
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
                
            # Ensure all contained widgets are visible after layout rendering
            for widget in container.contained_widgets:
                if hasattr(widget, 'content_container') and widget.content_container:
                    widget.content_container.show()
                    widget.content_container.update()

        finally:
            # Always return to idle state, even if an error occurs
            self.manager._set_state(DockingState.IDLE)
            
        # Update tab bar visibility after rendering
        self._update_tab_bar_visibility(container)
        
        # Update container title based on current widgets
        container.update_dynamic_title()

    def _render_node(self, node: AnyNode, container: DockContainer, inside_splitter: bool = False, widget_to_activate: DockPanel = None) -> QTabWidget:
        """
        Recursively renders model nodes into Qt widgets.
        
        Args:
            node: The layout node to render
            container: The container hosting the layout
            inside_splitter: Whether this node is inside a splitter
            widget_to_activate: Optional widget to activate
            
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
            for child_node in node.children:
                child_widget = self._render_node(child_node, container, inside_splitter=True, widget_to_activate=widget_to_activate)
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
                widget.content_container.setProperty("dockable_widget", widget)
                if widget.original_bg_color:
                    bg_color_name = widget.original_bg_color.name()
                    widget.content_container.setStyleSheet(
                        f"#ContentContainer {{ background-color: {bg_color_name}; border-radius: 0px; }}")
                widget.parent_container = container
                # Ensure content container is visible after reparenting
                widget.content_container.show()
                # CRITICAL FIX: Force visibility and ensure proper reparenting
                widget.content_container.setVisible(True)
                widget.content_container.activateWindow()
                widget.content_container.raise_()
                # Double-check that the content widget inside has proper size
                if hasattr(widget, 'content_widget') and widget.content_widget:
                    widget.content_widget.setVisible(True)
                # DockPanel instances never have shadow effects (they're not windows)
                # DockPanel instances never have shadow effects (they're not windows)
                if widget not in container.contained_widgets:
                    container.contained_widgets.append(widget)
                    
            # CRITICAL FIX: After all tabs are added, ensure the tab widget properly displays content
            if qt_tab_widget.count() > 0:
                # Make sure the first tab is properly selected and visible
                current_index = qt_tab_widget.currentIndex()
                if current_index >= 0:
                    current_widget = qt_tab_widget.widget(current_index)
                    if current_widget:
                        current_widget.setVisible(True)
                        current_widget.update()
                        
                # Force the tab widget to update its display
                qt_tab_widget.update()
                qt_tab_widget.repaint()
            
            # Apply new UI rules for tab bar visibility
            tab_count = qt_tab_widget.count()
            
            if inside_splitter:
                # Rule C: Inside splitter - always show tab bar and corner widget
                qt_tab_widget.tabBar().setVisible(True)
                corner_widget = qt_tab_widget.cornerWidget()
                if corner_widget:
                    corner_widget.setVisible(True)
            elif tab_count == 1 and not self.manager._is_persistent_root(container):
                # Rule A: Single widget state - hide tab bar and corner widget (except for persistent roots)
                qt_tab_widget.tabBar().setVisible(False)
                corner_widget = qt_tab_widget.cornerWidget()
                if corner_widget:
                    corner_widget.setVisible(False)
            else:
                # Rule B: Tabbed state - show tab bar and corner widget
                qt_tab_widget.tabBar().setVisible(True)
                corner_widget = qt_tab_widget.cornerWidget()
                if corner_widget:
                    corner_widget.setVisible(True)
            
            # Activate the specified widget if provided
            if widget_to_activate is not None:
                for tab_index in range(qt_tab_widget.count()):
                    tab_content = qt_tab_widget.widget(tab_index)
                    if tab_content == widget_to_activate.content_container:
                        qt_tab_widget.setCurrentIndex(tab_index)
                        break
            
            return qt_tab_widget
        elif isinstance(node, WidgetNode):
            widget = node.widget
            # Ensure content container is visible before returning it
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
            # Root is TabGroupNode - apply Rules A/B
            tab_widget = container.splitter
            tab_count = tab_widget.count()
            corner_widget = tab_widget.cornerWidget()
            
            if tab_count == 1 and not self.manager._is_persistent_root(container):
                # Rule A: Single widget state - hide tab bar and corner widget (except for persistent roots)
                tab_widget.tabBar().setVisible(False)
                if corner_widget:
                    corner_widget.setVisible(False)
            else:
                # Rule B: Tabbed state - show tab bar and corner widget
                tab_widget.tabBar().setVisible(True)
                if corner_widget:
                    corner_widget.setVisible(True)
        else:
            # Root is SplitterNode - apply Rule C to all child tab widgets
            tab_widgets = container.splitter.findChildren(QTabWidget)
            for tab_widget in tab_widgets:
                # Rule C: Inside splitter - always show tab bar and corner widget
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
        
        # Special handling for persistent roots - they should never be removed from the model
        if self.manager._is_persistent_root(root_window):
            if simplified_node is None:
                # Create an empty TabGroupNode to maintain the persistent root
                from .dock_model import TabGroupNode
                simplified_node = TabGroupNode()
            self.manager.model.roots[root_window] = simplified_node
        elif simplified_node != root_node:
            if simplified_node is None:
                # Non-persistent roots can be removed when empty
                del self.manager.model.roots[root_window]
            else:
                self.manager.model.roots[root_window] = simplified_node

    def _simplify_node(self, node: AnyNode) -> AnyNode:
        """
        Recursively simplifies a node by removing empty nodes and flattening single-child structures.
        
        Args:
            node: The node to simplify
            
        Returns:
            AnyNode: The simplified node
        """
        if isinstance(node, SplitterNode):
            # First, simplify all children
            simplified_children = []
            for child in node.children:
                simplified_child = self._simplify_node(child)
                if simplified_child:  # Only add non-empty children
                    simplified_children.append(simplified_child)
            
            # Update the node's children
            node.children = simplified_children
            
            # If no children remain, return None (empty node)
            if not node.children:
                return None
            
            # If only one child remains, return the child directly (flatten)
            if len(node.children) == 1:
                return node.children[0]
                
            return node
            
        elif isinstance(node, TabGroupNode):
            # Remove empty widget nodes
            node.children = [child for child in node.children if child and isinstance(child, WidgetNode)]
            
            # If no children remain, return None (empty node)
            if not node.children:
                return None
                
            return node
            
        elif isinstance(node, WidgetNode):
            # Widget nodes are always valid if they exist
            return node
            
        return None

    def update_model_after_close(self, widget_to_close: DockPanel):
        """
        Updates the model when a widget is closed.
        
        Args:
            widget_to_close: The widget that was closed
        """
        # Find the widget in the model
        host_tab_group, host_parent_node, root_window = self.manager.model.find_host_info(widget_to_close)
        
        if not host_tab_group:
            return
            
        # Remove the widget from its tab group
        widget_node_to_remove = None
        for widget_node in host_tab_group.children:
            if widget_node.widget is widget_to_close:
                widget_node_to_remove = widget_node
                break
                
        if widget_node_to_remove:
            host_tab_group.children.remove(widget_node_to_remove)
            
        # Simplify the model and re-render if needed
        if root_window:
            self.simplify_model(root_window)
            if root_window in self.manager.model.roots:
                self.render_layout(root_window)
            else:
                # Container was removed, close it
                if hasattr(root_window, 'close'):
                    root_window.close()