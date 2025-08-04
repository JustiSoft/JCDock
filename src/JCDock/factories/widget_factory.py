from typing import Callable, Optional, Dict, Any
from PySide6.QtCore import QPoint, QRect, QSize
from PySide6.QtWidgets import QWidget

from ..widgets.dock_panel import DockPanel
from ..widgets.dock_container import DockContainer
from ..model.dock_model import WidgetNode, TabGroupNode
from ..core.widget_registry import get_registry


class WidgetFactory:
    """
    Factory class responsible for creating dockable widgets and floating windows.
    Handles widget creation, positioning, and registration with the docking system.
    """
    
    def __init__(self, manager):
        """
        Initialize the widget factory.
        
        Args:
            manager: Reference to the DockingManager instance
        """
        self.manager = manager
    
    def create_panel_from_key(self, key: str) -> DockPanel:
        """
        Internal factory method that creates a fully-wrapped DockPanel from a registered key.
        This is the single, internal authority for creating DockPanels from the registry.
        
        Args:
            key: String key for the registered widget type
            
        Returns:
            Fully prepared DockPanel with the widget instance inside
            
        Raises:
            ValueError: If the key is not registered
        """
        registry = get_registry()
        registration = registry.get_registration(key)
        
        if registration is None:
            raise ValueError(f"Widget key '{key}' is not registered. Use @persistable decorator to register widget types.")
        
        # Create widget instance based on registration type
        if registration.reg_type == 'class':
            widget_instance = registration.widget_class()
        elif registration.reg_type == 'factory':
            widget_instance = registration.factory_func()
        else:
            raise ValueError(f"Unknown registration type '{registration.reg_type}' for widget key '{key}'")
        
        panel = DockPanel(registration.default_title, parent=None, manager=self.manager)
        
        panel.setContent(widget_instance)
        
        panel.persistent_id = key
        
        return panel

    def create_floating_widget_from_key(self, key: str, position=None, size=None) -> DockContainer:
        """
        Create a floating widget from a registered key (By Type path).
        This is the first public API for the simplified widget creation system.
        
        Args:
            key: String key for the registered widget type
            position: Optional position for the floating window (defaults to cascaded position)
            size: Optional size for the floating window (defaults to 400x300)
            
        Returns:
            DockContainer containing the new widget
            
        Raises:
            ValueError: If the key is not registered
        """
        panel = self.create_panel_from_key(key)
        
        size = self._normalize_size(size)
        position = self._calculate_position(position)
        
        title_height = 30
        adjusted_size = QSize(size.width(), size.height() + title_height)
        
        geometry = QRect(position, adjusted_size)
        
        container = self.create_floating_window([panel], geometry)
        
        self.manager._register_widget(panel)
        
        self.manager.floating_widget_count += 1
        
        return container

    def add_as_floating_widget(self, widget_instance: QWidget, persistent_key: str, title: str = None, 
                              position=None, size=None, 
                              state_provider: Optional[Callable[[QWidget], Dict[str, Any]]] = None,
                              state_restorer: Optional[Callable[[QWidget, Dict[str, Any]], None]] = None) -> DockContainer:
        """
        Make an existing widget instance dockable as a floating window (By Instance path).
        This is the second public API for the simplified widget creation system.
        
        Args:
            widget_instance: The existing widget object to make dockable
            persistent_key: Key that must exist in the registry for layout persistence
            title: Optional title for the widget (uses registry default if not provided)
            position: Optional position for the floating window (defaults to cascaded position)  
            size: Optional size for the floating window (defaults to 400x300)
            state_provider: Optional function to extract state from widget for persistence
            state_restorer: Optional function to restore state to widget from saved data
            
        Returns:
            DockContainer containing the dockable widget
            
        Raises:
            ValueError: If the persistent_key is not registered
        """
        registry = get_registry()
        if not registry.is_registered(persistent_key):
            raise ValueError(f"Persistent key '{persistent_key}' is not registered. "
                           f"The system must know how to recreate this widget type for layout loading. "
                           f"Use @persistable decorator to register the widget type first.")
        
        registration = registry.get_registration(persistent_key)
        if title is None:
            title = registration.default_title
        
        panel = DockPanel(title, parent=None, manager=self.manager)
        
        panel.setContent(widget_instance)
        
        panel.persistent_id = persistent_key
        
        size = self._normalize_size(size)
        position = self._calculate_position(position)
        
        title_height = 30
        adjusted_size = QSize(size.width(), size.height() + title_height)
        
        geometry = QRect(position, adjusted_size)
        
        container = self.create_floating_window([panel], geometry)
        
        self.manager._register_widget(panel)
        
        # Store state handlers if provided
        if state_provider is not None or state_restorer is not None:
            self.manager.register_instance_state_handlers(persistent_key, state_provider, state_restorer)
        
        self.manager.floating_widget_count += 1
        
        return container

    def create_simple_floating_widget(self, content_widget: QWidget, title: str = "Widget", 
                                     x: int = 300, y: int = 300, width: int = 400, height: int = 300) -> tuple[DockContainer, DockPanel]:
        """
        Create a simple floating widget without requiring registry registration or QRect.
        This is the simplest possible API for basic use cases.
        
        ⚠️  WARNING: This method is for convenience only and is NOT PERSISTENT across application sessions.
        The generated persistent ID is unstable and based on object memory addresses, which means
        widgets created with this method will NOT be restored when loading saved layouts.
        
        For persistent widgets, use create_floating_widget_from_key() or add_as_floating_widget()
        with a registered widget type instead.
        
        Args:
            content_widget: The widget to make dockable
            title: Title for the widget window
            x, y: Position of the floating window  
            width, height: Size of the floating window
            
        Returns:
            Tuple of (DockContainer, DockPanel) - container and the dockable panel for further operations
        """
        panel = DockPanel(title, manager=self.manager, persistent_id=f"simple_{id(content_widget)}")
        panel.setContent(content_widget)
        
        self.manager._register_widget(panel)
        
        geometry = QRect(x, y, width, height)
        container = self.create_floating_window([panel], geometry)
        
        return container, panel

    def create_floating_window(self, widgets: list[DockPanel], geometry: QRect, was_maximized=False,
                               normal_geometry=None):
        """
        Creates a new floating window containing the specified widgets.
        
        Args:
            widgets: List of DockPanel widgets to include
            geometry: Window geometry
            was_maximized: Whether the window should start maximized
            normal_geometry: Normal geometry for maximized windows
            
        Returns:
            DockContainer: The created floating window
        """
        if not widgets: 
            return None
        
        validated_geometry = self.manager._validate_window_geometry(geometry)
        
        # Extract icon from the first widget to preserve it in the floating container
        widget_icon = widgets[0].get_icon() if widgets else None
        
        new_container = DockContainer(manager=self.manager, parent=None, icon=widget_icon)
        new_container.setGeometry(validated_geometry)

        if was_maximized:
            new_container._is_maximized = True
            if normal_geometry:
                validated_normal_geometry = self.manager._validate_window_geometry(normal_geometry)
                new_container._normal_geometry = validated_normal_geometry
            new_container.main_layout.setContentsMargins(0, 0, 0, 0)
            new_container.title_bar.maximize_button.setIcon(
                new_container.title_bar._create_control_icon("restore")
            )

        widget_nodes = [WidgetNode(w) for w in widgets]
        tab_group_node = TabGroupNode(children=widget_nodes)
        self.manager.model.roots[new_container] = tab_group_node
        
        for widget in widgets:
            widget.parent_container = new_container
            
        self.manager.add_widget_handlers(new_container)
        self.manager.containers.append(new_container)
        self.manager.bring_to_front(new_container)
        self.manager._render_layout(new_container)
        
        # Shadow functionality removed

        new_container.show()
        
        return new_container
    
    def _normalize_size(self, size) -> QSize:
        """
        Normalizes size input to QSize object.
        
        Args:
            size: Size input (QSize, tuple/list with 2+ elements, or None)
            
        Returns:
            QSize: Normalized size (defaults to 400x300)
        """
        if size is None:
            return QSize(400, 300)
        elif not isinstance(size, QSize):
            if hasattr(size, '__iter__') and len(size) >= 2:
                return QSize(int(size[0]), int(size[1]))
            else:
                return QSize(400, 300)
        return size
    
    def _calculate_position(self, position) -> QPoint:
        """
        Calculates window position, using cascading if position is None.
        
        Args:
            position: Position input (QPoint, tuple/list with 2+ elements, or None)
            
        Returns:
            QPoint: Calculated position
        """
        if position is None:
            count = self.manager.floating_widget_count
            if self.manager.main_window:
                main_pos = self.manager.main_window.pos()
                return QPoint(main_pos.x() + 150 + (count % 7) * 40,
                              main_pos.y() + 150 + (count % 7) * 40)
            else:
                return QPoint(150 + (count % 7) * 40, 150 + (count % 7) * 40)
        elif not isinstance(position, QPoint):
            if hasattr(position, '__iter__') and len(position) >= 2:
                return QPoint(int(position[0]), int(position[1]))
            else:
                # Fall back to cascading
                count = self.manager.floating_widget_count
                if self.manager.main_window:
                    main_pos = self.manager.main_window.pos()
                    return QPoint(main_pos.x() + 150 + (count % 7) * 40,
                                  main_pos.y() + 150 + (count % 7) * 40)
                else:
                    return QPoint(150 + (count % 7) * 40, 150 + (count % 7) * 40)
        return position