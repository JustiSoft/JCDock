from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget


class OverlayManager:
    """
    Manages overlay lifecycle, cleanup, and destruction.
    Handles all overlay-related operations to prevent memory leaks and phantom overlays.
    """
    
    def __init__(self, manager):
        """
        Initialize the overlay manager.
        
        Args:
            manager: Reference to the DockingManager instance
        """
        self.manager = manager
    
    def cleanup_container_overlays(self, container):
        """
        Targeted cleanup of overlays specifically on a container and its children.
        
        Args:
            container: The container to clean up overlays for
        """
        if not container or self.manager.is_deleted(container):
            return
            
        if hasattr(container, 'overlay') and container.overlay:
            container.overlay.destroy_overlay()
            container.overlay = None
            
        for child in container.findChildren(QWidget):
            if hasattr(child, 'overlay') and child.overlay:
                child.overlay.destroy_overlay()
                child.overlay = None
                
        def force_repaint_recursive(widget):
            if widget and not self.manager.is_deleted(widget):
                widget.update()
                widget.repaint()
                for child in widget.findChildren(QWidget):
                    if not self.manager.is_deleted(child):
                        try:
                            child.update()
                            child.repaint()
                        except TypeError:
                            pass
        
        force_repaint_recursive(container)

    def destroy_all_overlays(self):
        """
        Ultimate brute-force cleanup of ALL overlay widgets in the application.
        This method uses QApplication.allWidgets() to find and destroy every single
        DockingOverlay instance, regardless of where it came from or whether it's orphaned.
        """
        overlays_destroyed = 0
        
        from .docking_overlay import DockingOverlay
        
        # Pass 1: Find DockingOverlay instances
        try:
            all_widgets = QApplication.allWidgets()
            for widget in all_widgets:
                if isinstance(widget, DockingOverlay) and not self.manager.is_deleted(widget):
                    try:
                        widget.hide()
                        widget.close()
                        widget.setParent(None)
                        widget.deleteLater()
                        overlays_destroyed += 1
                    except RuntimeError:
                        pass                        
        except RuntimeError:
            pass
        
        # Pass 2: Search by class name string
        try:
            all_widgets = QApplication.allWidgets()
            for widget in all_widgets:
                widget_class_name = widget.__class__.__name__
                if ('DockingOverlay' in widget_class_name or 
                    'Overlay' in widget_class_name) and not self.manager.is_deleted(widget):
                    try:
                        widget.hide()
                        widget.setParent(None)
                        widget.deleteLater()
                        overlays_destroyed += 1
                    except RuntimeError:
                        pass                        
        except RuntimeError:
            pass
            
        # Pass 3: Look for orphaned overlay-related widgets by characteristics
        try:
            all_widgets = QApplication.allWidgets()
            for widget in all_widgets:
                if not self.manager.is_deleted(widget) and (
                    widget.objectName() == "preview_overlay" or 
                    (hasattr(widget, 'styleSheet') and widget.styleSheet() and 
                     ('rgba(0, 0, 255, 128)' in widget.styleSheet() or 
                      'lightgray' in widget.styleSheet() or  
                      'lightblue' in widget.styleSheet() or 
                      'lightgreen' in widget.styleSheet())) or
                    (widget.parentWidget() is None and 
                     hasattr(widget, 'styleSheet') and widget.styleSheet() and
                     'rgba(' in widget.styleSheet())):
                    try:
                        widget.hide()
                        widget.setParent(None)
                        widget.deleteLater()
                        overlays_destroyed += 1
                    except RuntimeError:
                        pass                        
        except RuntimeError:
            pass
        
        # Clear managed overlay references
        for item in list(self.manager.widgets) + list(self.manager.containers):
            if not self.manager.is_deleted(item) and hasattr(item, 'overlay'):
                item.overlay = None
        
        # Clear the active overlays tracking list
        self.manager.active_overlays.clear()

        # Clear all tab bar drop indicators
        from .tearable_tab_widget import TearableTabBar
        for container in self.manager.containers:
            if not self.manager.is_deleted(container):
                for tab_bar in container.findChildren(TearableTabBar):
                    try:
                        tab_bar.set_drop_indicator_index(-1)
                    except RuntimeError:
                        pass

    def force_cleanup_stuck_overlays(self):
        """
        Emergency cleanup method to find and destroy any stuck overlay widgets
        that may have been missed by normal cleanup processes.
        """
        stuck_overlays_found = 0
        
        try:
            # More aggressive search for stuck overlay widgets
            all_widgets = QApplication.allWidgets()
            for widget in all_widgets:
                should_clean = False
                
                # Check for DockingOverlay instances
                from .docking_overlay import DockingOverlay
                if isinstance(widget, DockingOverlay):
                    should_clean = True
                
                # Check for widgets with blue preview styling (stuck preview overlays)
                elif (hasattr(widget, 'styleSheet') and widget.styleSheet() and 
                      ('rgba(0, 0, 255, 128)' in widget.styleSheet() or 
                       'rgba(0,0,255,128)' in widget.styleSheet().replace(' ', ''))):
                    should_clean = True
                
                # Check for widgets that look like overlay icons
                elif (hasattr(widget, 'text') and 
                      hasattr(widget, 'styleSheet') and 
                      widget.styleSheet() and
                      widget.text() in ['▲', '◀', '▼', '▶', '⧉'] and
                      ('lightgray' in widget.styleSheet() or 
                       'lightblue' in widget.styleSheet() or
                       'lightgreen' in widget.styleSheet())):
                    should_clean = True
                
                # Check for widgets with transparent mouse events (typical of overlays)
                elif (hasattr(widget, 'testAttribute') and 
                      widget.testAttribute(Qt.WA_TransparentForMouseEvents) and
                      hasattr(widget, 'styleSheet') and widget.styleSheet() and
                      'rgba(' in widget.styleSheet()):
                    should_clean = True
                
                if should_clean and not self.manager.is_deleted(widget):
                    try:
                        # Try to hide any child preview overlays first
                        if hasattr(widget, 'preview_overlay') and widget.preview_overlay:
                            widget.preview_overlay.hide()
                            widget.preview_overlay.setParent(None)
                            widget.preview_overlay.deleteLater()
                        
                        # Hide and destroy the widget
                        widget.hide()
                        widget.setParent(None)
                        widget.deleteLater()
                        stuck_overlays_found += 1
                    except RuntimeError:
                        # Widget may have been deleted elsewhere
                        pass
                        
        except RuntimeError:
            # QApplication.allWidgets() can fail under certain conditions
            pass
            
        return stuck_overlays_found

    def clean_orphaned_overlays(self):
        """
        Audits and heals the active_overlays list by removing invalid entries
        and destroying orphaned overlay widgets found in the application.
        """
        from .dock_panel import DockPanel
        from .dock_container import DockContainer
        
        items_to_remove = []
        
        for item in self.manager.active_overlays[:]:
            should_remove = False
            
            if self.manager.is_deleted(item):
                should_remove = True
            elif hasattr(item, 'overlay'):
                if not item.overlay or self.manager.is_deleted(item.overlay):
                    should_remove = True
                else:
                    try:
                        overlay_parent = item.overlay.parentWidget()
                        
                        if isinstance(item, DockPanel):
                            if item.parent_container:
                                if overlay_parent != item.parent_container:
                                    should_remove = True
                            else:
                                if overlay_parent != item:
                                    should_remove = True
                        elif isinstance(item, DockContainer):
                            if overlay_parent != item:
                                should_remove = True
                                
                    except RuntimeError:
                        should_remove = True
            else:
                should_remove = True
                
            if should_remove:
                items_to_remove.append(item)
                
        for item in items_to_remove:
            if item in self.manager.active_overlays:
                self.manager.active_overlays.remove(item)
            if hasattr(item, 'overlay') and item.overlay:
                try:
                    if not self.manager.is_deleted(item.overlay):
                        item.overlay.destroy_overlay()
                    item.overlay = None
                except RuntimeError:
                    pass
                    
        from .docking_overlay import DockingOverlay
        try:
            for widget in QApplication.allWidgets():
                if isinstance(widget, DockingOverlay) and not self.manager.is_deleted(widget):
                    if widget.parentWidget() is None:
                        try:
                            widget.destroy_overlay()
                        except RuntimeError:
                            pass
        except RuntimeError:
            pass