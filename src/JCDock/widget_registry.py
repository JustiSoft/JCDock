"""
Central widget registry for the JCDock system.

This module provides a global registry that acts as the definitive source of truth
for all known dockable widget types.
"""

from typing import Dict, Type, Any, Optional
from dataclasses import dataclass
from PySide6.QtWidgets import QWidget


@dataclass
class WidgetRegistration:
    """Information package for a registered widget type."""
    widget_class: Type[QWidget]
    default_title: str


class WidgetRegistry:
    """Central registry for dockable widget types."""
    
    def __init__(self):
        self._registry: Dict[str, WidgetRegistration] = {}
    
    def register(self, key: str, widget_class: Type[QWidget], default_title: str) -> None:
        """Register a widget type with the given key and default title."""
        if key in self._registry:
            raise ValueError(f"Widget key '{key}' is already registered")
        
        self._registry[key] = WidgetRegistration(
            widget_class=widget_class,
            default_title=default_title
        )
    
    def get_registration(self, key: str) -> Optional[WidgetRegistration]:
        """Get registration information for a widget key."""
        return self._registry.get(key)
    
    def is_registered(self, key: str) -> bool:
        """Check if a widget key is registered."""
        return key in self._registry
    
    def get_all_keys(self) -> list[str]:
        """Get all registered widget keys."""
        return list(self._registry.keys())


_global_registry = WidgetRegistry()


def get_registry() -> WidgetRegistry:
    """Get the global widget registry instance."""
    return _global_registry


def dockable(key: str, title: str = None):
    """
    Decorator to register a widget class as dockable.
    
    Args:
        key: Unique string identifier for the widget type
        title: Default title for the widget (uses key if not provided)
    """
    def decorator(widget_class: Type[QWidget]) -> Type[QWidget]:
        default_title = title if title is not None else key
        _global_registry.register(key, widget_class, default_title)
        return widget_class
    
    return decorator