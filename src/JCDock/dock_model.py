from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from typing import Union
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget
from .dock_panel import DockPanel

AnyNode = Union['SplitterNode', 'TabGroupNode', 'WidgetNode']

# --- Node Definitions ---

@dataclass
class WidgetNode:
    """Represents a single, concrete DockPanel in the layout."""
    widget: DockPanel
    id: uuid.UUID = field(default_factory=uuid.uuid4, init=False)

@dataclass
class TabGroupNode:
    """Represents a QTabWidget. It can only contain WidgetNodes."""
    children: list[WidgetNode] = field(default_factory=list)
    id: uuid.UUID = field(default_factory=uuid.uuid4, init=False)

@dataclass
class SplitterNode:
    """Represents a QSplitter. It can contain TabGroupNodes or other SplitterNodes."""
    orientation: Qt.Orientation
    children: list[Union[TabGroupNode, 'SplitterNode']] = field(default_factory=list)
    sizes: list[int] = field(default_factory=list)
    id: uuid.UUID = field(default_factory=uuid.uuid4, init=False)

# --- Layout Model ---

class LayoutModel:
    """The complete model for the entire application's dock layout."""
    def __init__(self):
        self.roots: dict[QWidget, AnyNode] = {}

    def register_widget(self, widget: DockPanel):
        """
        Legacy method - DockPanel instances should NOT be registered as floating windows.
        Use create_floating_window() in DockingManager instead to create DockContainers.
        This method is kept for compatibility but should not be used for new DockPanel instances.
        """
        pass

    def unregister_widget(self, widget: QWidget):
        """Removes a top-level widget (and its entire layout) from the model."""
        if widget in self.roots:
            del self.roots[widget]

    def pretty_print(self, manager=None):
        """Outputs the current state of the entire layout model to the console."""
        print("\n--- DOCKING LAYOUT STATE ---")
        if not self.roots:
            print("  (No registered windows)")
            print("----------------------------\n")
            return

        for i, (widget, root_node) in enumerate(self.roots.items()):
            window_title = widget.windowTitle() if widget.windowTitle() else "Container"
            print(f"\n[Window {i+1}: '{window_title}' ({type(widget).__name__}) ID: {widget.objectName()}]")
            self._print_node(root_node, indent=1, container_widget=widget, manager=manager)
        print("----------------------------\n")

    def _print_node(self, node: AnyNode, indent: int, container_widget=None, manager=None, active_widget=None):
        """Recursively prints a node and its children."""
        prefix = "  " * indent
        if isinstance(node, SplitterNode):
            orientation = "Horizontal" if node.orientation == Qt.Horizontal else "Vertical"
            print(f"{prefix}+- Splitter ({orientation}) [id: ...{str(node.id)[-4:]}] - Children: {len(node.children)}")
            for child in node.children:
                self._print_node(child, indent + 1, container_widget=container_widget, manager=manager, active_widget=active_widget)
        elif isinstance(node, TabGroupNode):
            print(f"{prefix}+- TabGroup [id: ...{str(node.id)[-4:]}] - Tabs: {len(node.children)}")
            
            tab_group_active_widget = None
            if manager and container_widget:
                tab_group_active_widget = self._get_active_widget_for_tab_group(node, container_widget)
            
            for child in node.children:
                self._print_node(child, indent + 1, container_widget=container_widget, manager=manager, active_widget=tab_group_active_widget)
        elif isinstance(node, WidgetNode):
            # Check if this is the active widget
            is_active = active_widget == node.widget if active_widget else False
            active_marker = " [ACTIVE]" if is_active else ""
            print(f"{prefix}+- Widget: '{node.widget.windowTitle()}' [id: ...{str(node.id)[-4:]}]{active_marker}")

    def _get_active_widget_for_tab_group(self, tab_group_node: TabGroupNode, container_widget) -> DockPanel | None:
        """
        Find the currently active widget in a specific tab group.
        Returns the DockPanel that corresponds to the current tab in the QTabWidget for this TabGroupNode.
        """
        from PySide6.QtWidgets import QTabWidget
        
        all_tab_widgets = container_widget.findChildren(QTabWidget)
        
        for tab_widget in all_tab_widgets:
            tab_group_widgets = [child.widget for child in tab_group_node.children if hasattr(child, 'widget')]
            
            for i in range(tab_widget.count()):
                tab_content = tab_widget.widget(i)
                if tab_content:
                    owning_widget = next((w for w in tab_group_widgets if hasattr(w, 'content_container') and w.content_container is tab_content), None)
                    if owning_widget:
                        current_content = tab_widget.currentWidget()
                        if current_content:
                            return next((w for w in tab_group_widgets if hasattr(w, 'content_container') and w.content_container is current_content), None)
        
        return None

    def find_host_info(self, widget: DockPanel) -> tuple[TabGroupNode, AnyNode, QWidget] | tuple[None, None, None]:
        """
        Finds all context for a given widget.
        Returns: (The TabGroupNode hosting the widget, its parent node, the top-level QWidget window)
        """
        for root_window, root_node in self.roots.items():
            group, parent = self._find_widget_in_tree(root_node, widget)
            if group:
                return group, parent, root_window
        return None, None, None

    def _find_widget_in_tree(self, current_node, target_widget, parent=None):
        """Recursive helper to find the TabGroupNode that contains a widget."""
        if isinstance(current_node, TabGroupNode):
            if any(wn.widget is target_widget for wn in current_node.children):
                return current_node, parent

        if isinstance(current_node, SplitterNode):
            for child in current_node.children:
                group, p = self._find_widget_in_tree(child, target_widget, current_node)
                if group:
                    return group, p

        if parent is None and isinstance(current_node, TabGroupNode):
            if any(wn.widget is target_widget for wn in current_node.children):
                return current_node, None

        return None, None

    def get_all_widgets_from_node(self, node: AnyNode) -> list[WidgetNode]:
        """Recursively traverses a node and returns a flat list of all WidgetNodes within it."""
        widgets = []
        self._recursive_get_widgets(node, widgets)
        return widgets

    def _recursive_get_widgets(self, node: AnyNode, widget_list: list):
        if isinstance(node, WidgetNode):
            widget_list.append(node)
        elif isinstance(node, (TabGroupNode, SplitterNode)):
            for child in node.children:
                self._recursive_get_widgets(child, widget_list)

    def find_widget_node(self, root_node: AnyNode, target_widget) -> WidgetNode:
        """
        Recursively searches through the node tree to find the WidgetNode
        that contains the specified target widget.
        """
        if isinstance(root_node, WidgetNode):
            if root_node.widget is target_widget:
                return root_node
        elif isinstance(root_node, (TabGroupNode, SplitterNode)):
            for child in root_node.children:
                result = self.find_widget_node(child, target_widget)
                if result:
                    return result
        return None

    def find_widget_node_with_parent(self, root_node: AnyNode, target_widget) -> tuple[WidgetNode, AnyNode]:
        """
        Recursively searches through the node tree to find the WidgetNode
        that contains the specified target widget, along with its parent node.
        Returns (widget_node, parent_node) or (None, None) if not found.
        """
        return self._find_widget_with_parent_helper(root_node, target_widget, None)
    
    def _find_widget_with_parent_helper(self, node: AnyNode, target_widget, parent: AnyNode) -> tuple[WidgetNode, AnyNode]:
        """Helper method for find_widget_node_with_parent."""
        if isinstance(node, WidgetNode):
            if node.widget is target_widget:
                return node, parent
        elif isinstance(node, (TabGroupNode, SplitterNode)):
            for child in node.children:
                result = self._find_widget_with_parent_helper(child, target_widget, node)
                if result[0]:
                    return result
        return None, None

    def _find_node_with_ancestry(self, root_node: AnyNode, target_node: AnyNode) -> list[AnyNode]:
        """
        Finds the target_node and returns the full ancestry path from root to target.
        Returns list like [root_node, parent_node, target_node] or empty list if not found.
        """
        def search_with_path(current_node: AnyNode, path: list[AnyNode]) -> list[AnyNode]:
            current_path = path + [current_node]
            
            if current_node is target_node:
                return current_path
            
            if isinstance(current_node, (TabGroupNode, SplitterNode)):
                for child in current_node.children:
                    result = search_with_path(child, current_path)
                    if result:
                        return result
            
            return []
        
        return search_with_path(root_node, [])

    def replace_node_in_tree(self, root_node: AnyNode, old_node: AnyNode, new_node: AnyNode) -> bool:
        """
        Recursively searches through the node tree and replaces old_node with new_node.
        Returns True if the replacement was successful, False otherwise.
        """
        if isinstance(root_node, (TabGroupNode, SplitterNode)):
            for i, child in enumerate(root_node.children):
                if child is old_node:
                    root_node.children[i] = new_node
                    return True
                elif isinstance(child, (TabGroupNode, SplitterNode)):
                    if self.replace_node_in_tree(child, old_node, new_node):
                        return True
        return False