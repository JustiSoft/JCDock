from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from typing import Union
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget
from .dockable_widget import DockableWidget

# Define a type hint for any possible node
AnyNode = Union['SplitterNode', 'TabGroupNode', 'WidgetNode']

# --- Node Definitions ---

@dataclass
class WidgetNode:
    """Represents a single, concrete DockableWidget in the layout."""
    widget: DockableWidget
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
        # The keys are the top-level floating widgets (DockableWidget or DockContainer).
        # The values are the root nodes of their internal layout trees.
        self.roots: dict[QWidget, AnyNode] = {}

    def register_widget(self, widget: DockableWidget):
        """Registers a new floating widget, giving it a simple default layout."""
        if widget in self.roots:
            return # Already registered

        # A new floating widget is represented as a single tab in a tab group.
        widget_node = WidgetNode(widget=widget)
        tab_group_node = TabGroupNode(children=[widget_node])
        self.roots[widget] = tab_group_node

    def unregister_widget(self, widget: QWidget):
        """Removes a top-level widget (and its entire layout) from the model."""
        if widget in self.roots:
            del self.roots[widget]

    def pretty_print(self):
        """Outputs the current state of the entire layout model to the console."""
        print("\n--- DOCKING LAYOUT STATE ---")
        if not self.roots:
            print("  (No registered windows)")
            print("----------------------------\n")
            return

        for i, (widget, root_node) in enumerate(self.roots.items()):
            window_title = widget.windowTitle() if widget.windowTitle() else "Container"
            print(f"\n[Window {i+1}: '{window_title}' ({type(widget).__name__}) ID: {widget.objectName()}]")
            self._print_node(root_node, indent=1)
        print("----------------------------\n")

    def _print_node(self, node: AnyNode, indent: int):
        """Recursively prints a node and its children."""
        prefix = "  " * indent
        if isinstance(node, SplitterNode):
            orientation = "Horizontal" if node.orientation == Qt.Horizontal else "Vertical"
            print(f"{prefix}↳ Splitter ({orientation}) [id: ...{str(node.id)[-4:]}] - Children: {len(node.children)}")
            for child in node.children:
                self._print_node(child, indent + 1)
        elif isinstance(node, TabGroupNode):
            print(f"{prefix}↳ TabGroup [id: ...{str(node.id)[-4:]}] - Tabs: {len(node.children)}")
            for child in node.children:
                self._print_node(child, indent + 1)
        elif isinstance(node, WidgetNode):
            print(f"{prefix}↳ Widget: '{node.widget.windowTitle()}' [id: ...{str(node.id)[-4:]}]")

    def find_host_info(self, widget: DockableWidget) -> tuple[TabGroupNode, AnyNode, QWidget] | tuple[None, None, None]:
        """
        Finds all context for a given widget.
        Returns: (The TabGroupNode hosting the widget, its parent node, the top-level QWidget window)
        """
        for root_window, root_node in self.roots.items():
            # Search inside the window's tree
            group, parent = self._find_widget_in_tree(root_node, widget)
            if group:
                return group, parent, root_window
        return None, None, None

    def _find_widget_in_tree(self, current_node, target_widget, parent=None):
        """Recursive helper to find the TabGroupNode that contains a widget."""
        # Base case: we found the tab group that holds our target widget.
        if isinstance(current_node, TabGroupNode):
            if any(wn.widget is target_widget for wn in current_node.children):
                return current_node, parent

        # Recursive step: search inside a splitter.
        if isinstance(current_node, SplitterNode):
            for child in current_node.children:
                group, p = self._find_widget_in_tree(child, target_widget, current_node)
                if group:
                    return group, p

        # This handles the case of a simple floating widget where the root node is the tab group.
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