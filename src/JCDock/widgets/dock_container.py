import re
from PySide6.QtWidgets import QWidget, QSplitter, QVBoxLayout, QTabWidget, QHBoxLayout, QPushButton, QStyle, \
    QApplication
from PySide6.QtCore import Qt, QRect, QEvent, QPoint, QRectF, QSize, QTimer, QPointF, QLineF, QObject
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPainterPath, QBrush, QRegion, QPixmap, QPen, QIcon, QPolygonF, \
    QPalette, QDragEnterEvent, QDragMoveEvent, QDragLeaveEvent, QDropEvent, QCursor
from PySide6.QtWidgets import QTableWidget, QTreeWidget, QListWidget, QTextEdit, QPlainTextEdit, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QSlider, QScrollBar
from typing import Optional, Union

from ..core.docking_state import DockingState
from .tearable_tab_widget import TearableTabWidget
from .title_bar import TitleBar
from .dock_panel import DockPanel
from ..interaction.docking_overlay import DockingOverlay
from ..utils.icon_cache import IconCache
from ..utils.resize_cache import ResizeCache
from ..utils.resize_throttler import ResizeThrottler
from ..utils.windows_shadow import apply_native_shadow
from .resize_overlay import ResizeOverlay


class DockContainer(QWidget):
    def __init__(self, orientation=Qt.Horizontal, margin_size=5, parent=None, manager=None,
                 show_title_bar=True, title_bar_color=None, background_color=None, border_color=None,
                 title_text_color=None, icon: Optional[Union[str, QIcon]] = None,
                 is_main_window=False, preserve_title=False, auto_persistent_root=False,
                 apply_shadow=None, window_title=None, default_geometry=(400, 400, 600, 500)):
        super().__init__(parent)

        # Initialize tracking set early before any addWidget calls that trigger childEvent
        self._tracked_widgets = set()
        
        if background_color is not None:
            self._background_color = background_color
        else:
            self._background_color = QColor("#F0F0F0")

        if border_color is not None:
            self._border_color = border_color
        else:
            self._border_color = QColor("#6A8EAE")

        if title_bar_color is not None:
            self._title_bar_color = title_bar_color
        else:
            # Use pleasing dark teal default color for title bars
            self._title_bar_color = QColor("#2F4F4F")  # Dark teal - more pleasing than brown

        if title_text_color is not None:
            self._title_text_color = title_text_color
        else:
            self._title_text_color = QColor("#101010")

        self.setObjectName("DockContainer")
        self.manager = manager
        
        # Store new parameters as instance variables
        self.is_main_window = is_main_window
        self.preserve_title = preserve_title
        self._is_persistent_root = auto_persistent_root
        
        # Auto-register with manager if provided
        if self.manager:
            self.manager._register_dock_area(self)
        
        # Set window title and geometry
        if show_title_bar:
            title = window_title if window_title else "Docked Widgets"
            self.setWindowTitle(title)
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
            self.setStyleSheet(self._generate_stylesheet())
            
            # Set default geometry for floating containers
            self.setGeometry(default_geometry[0], default_geometry[1], default_geometry[2], default_geometry[3])
            
            self.main_layout = QVBoxLayout(self)
        else:
            self.setStyleSheet(self._generate_stylesheet())
            self.main_layout = QVBoxLayout(self)
            
        # Store original title for preserve_title functionality
        self._original_title = self.windowTitle()
            
        # Remove the content_wrapper - no longer needed
        self.content_wrapper = None
        self.container_layout = None
            
        self.main_layout.setContentsMargins(0, 0, 0, 4)
        self.main_layout.setSpacing(0)

        self.title_bar = None
        if show_title_bar:
            title_bar_text = window_title if window_title else "Docked Widgets"
            self.title_bar = TitleBar(title_bar_text, self, top_level_widget=self, 
                                    title_text_color=self._title_text_color, icon=icon)
            self.title_bar.setMouseTracking(True)
            
            self.main_layout.addWidget(self.title_bar, 0)

        self.content_area = QWidget()
        self.content_area.setObjectName("ContentArea")
        self.content_area.setAutoFillBackground(False)
        self.main_layout.addWidget(self.content_area, 1)

        self.inner_content_layout = QVBoxLayout(self.content_area)
        self.inner_content_layout.setContentsMargins(margin_size, margin_size, margin_size, margin_size)
        self.inner_content_layout.setSpacing(0)

        self.splitter = None
        self.overlay = None
        self.parent_container = None
        self.contained_widgets = []

        self.setMinimumSize(200, 150)
        self.resize_margin = 8
        self.resizing = False
        self.resize_edge = None
        self.resize_start_pos = None
        self.resize_start_geom = None

        self._is_maximized = False
        self._normal_geometry = None

        self.setMouseTracking(True)
        self.content_area.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        self.installEventFilter(self)
        self.content_area.installEventFilter(self)

        self._filters_installed = False
        
        # Initialize resize components
        self._resize_overlay = None  # Created on-demand during resize operations
        self._content_updates_disabled = False  # Track content update state
        
        self.setAcceptDrops(True)
        
        # Apply native Windows shadow based on apply_shadow parameter
        if apply_shadow is None:
            # Default behavior: apply shadow if container has title bar
            if show_title_bar:
                apply_native_shadow(self)
        elif apply_shadow is True:
            # Force shadow application regardless of title bar
            apply_native_shadow(self)
        elif apply_shadow is False:
            # Explicitly disable shadow (even for titled containers)
            pass
            
        # Install event filter for floating containers with title bars
        if show_title_bar:
            self.installEventFilter(self)
            
        # Handle close button for main window behavior
        if show_title_bar and self.title_bar and self.title_bar.close_button:
            self.title_bar.close_button.clicked.disconnect()
            self.title_bar.close_button.clicked.connect(self._handle_user_close)

    def _generate_stylesheet(self):
        """Generate dynamic stylesheet using current color properties."""
        return f"""
            DockContainer {{
                background-color: {self._background_color.name()};
                border-left: 1px solid {self._border_color.name()};
                border-right: 1px solid {self._border_color.name()};
                border-bottom: 1px solid {self._border_color.name()};
            }}
        """

    def get_background_color(self):
        """Get the current background color."""
        return self._background_color

    def set_background_color(self, color):
        """Set the background color and update the stylesheet."""
        if isinstance(color, QColor):
            self._background_color = color
        else:
            self._background_color = QColor(color)
        self.setStyleSheet(self._generate_stylesheet())

    def get_border_color(self):
        """Get the current border color."""
        return self._border_color

    def set_border_color(self, color):
        """Set the border color and update the stylesheet."""
        if isinstance(color, QColor):
            self._border_color = color
        else:
            self._border_color = QColor(color)
        self.setStyleSheet(self._generate_stylesheet())

    def get_title_text_color(self):
        """Get the current title text color."""
        return self._title_text_color

    def set_title_text_color(self, color):
        """Set the title text color and update the title bar."""
        if isinstance(color, QColor):
            self._title_text_color = color
        else:
            self._title_text_color = QColor(color)
        if self.title_bar:
            self.title_bar.set_title_text_color(self._title_text_color)

    def set_icon(self, icon: Optional[Union[str, QIcon]]):
        """
        Set or update the dock container's title bar icon.
        Only works if the container has a title bar (show_title_bar=True).
        
        Args:
            icon: Icon source - can be file path, Unicode character, Qt standard icon name, or QIcon object
        """
        if self.title_bar:
            self.title_bar.set_icon(icon)
    
    def get_icon(self) -> Optional[QIcon]:
        """Get the current title bar icon as a QIcon object."""
        if self.title_bar:
            return self.title_bar.get_icon()
        return None
    
    def has_icon(self) -> bool:
        """Check if the dock container currently has a title bar icon."""
        if self.title_bar:
            return self.title_bar.has_icon()
        return False

    def set_drag_transparency(self, opacity=0.4):
        """
        Apply temporary transparency during drag operations to make drop targets more visible.
        
        Args:
            opacity: Opacity level (0.0 = fully transparent, 1.0 = fully opaque)
        """
        if not hasattr(self, '_original_opacity'):
            self._original_opacity = self.windowOpacity()
        self.setWindowOpacity(opacity)

    def restore_normal_opacity(self):
        """
        Restore the container's original opacity after drag operations.
        """
        if hasattr(self, '_original_opacity'):
            self.setWindowOpacity(self._original_opacity)
            delattr(self, '_original_opacity')

    def toggle_maximize(self):
        """Toggles the window between a maximized and normal state."""
        if self._is_maximized:
            self.setGeometry(self._normal_geometry)
            self._is_maximized = False
            self.title_bar.maximize_button.setIcon(self.title_bar._create_control_icon("maximize"))
        else:
            self._normal_geometry = self.geometry()
            screen = QApplication.screenAt(self.pos())
            if not screen:
                screen = QApplication.primaryScreen()
            
            # Use the full available screen geometry without shadow adjustments
            screen_geom = screen.availableGeometry()
            self.setGeometry(screen_geom)
            self._is_maximized = True
            self.title_bar.maximize_button.setIcon(self.title_bar._create_control_icon("restore"))

    def resizeEvent(self, event):
        """
        Standard resize event handler.
        """
        super().resizeEvent(event)

    def closeEvent(self, event):
        """Handle window close events (Alt+F4, system close, etc.)."""
        if self.manager:
            root_node = self.manager.model.roots.get(self)
            if root_node:
                all_widgets_in_container = self.manager.model.get_all_widgets_from_node(root_node)
                for widget_node in all_widgets_in_container:
                    if hasattr(widget_node, 'persistent_id'):
                        self.manager.signals.widget_closed.emit(widget_node.persistent_id)
                
                del self.manager.model.roots[self]
                
                if self in self.manager.containers:
                    self.manager.containers.remove(self)
                
                self.manager.signals.layout_changed.emit()
        
        if self.is_main_window:
            from PySide6.QtWidgets import QApplication
            QApplication.instance().quit()
        
        event.accept()

    def menuBar(self):
        """Provide QMainWindow-like menuBar() method for compatibility."""
        if hasattr(self, '_menu_bar'):
            return self._menu_bar
        return None

    def statusBar(self):
        """Provide QMainWindow-like statusBar() method for compatibility."""
        if hasattr(self, '_status_bar'):
            return self._status_bar
        return None

    def _handle_user_close(self):
        """Handle close button click by actually closing the window and all its contents."""
        if self.manager:
            root_node = self.manager.model.roots.get(self)
            if root_node:
                all_widgets_in_container = self.manager.model.get_all_widgets_from_node(root_node)
                for widget_node in all_widgets_in_container:
                    if hasattr(widget_node, 'persistent_id'):
                        self.manager.signals.widget_closed.emit(widget_node.persistent_id)
                
                del self.manager.model.roots[self]
                
                if self in self.manager.containers:
                    self.manager.containers.remove(self)
                
                self.manager.signals.layout_changed.emit()
        
        if self.is_main_window:
            from PySide6.QtWidgets import QApplication
            QApplication.instance().quit()
        else:
            self.close()

    def paintEvent(self, event):
        # Default paint event is sufficient for opaque containers
        super().paintEvent(event)

    def mousePressEvent(self, event):
        from .dock_panel import DockPanel

        pos = event.position().toPoint()
        
        # Check for resize edges first
        if self.title_bar and not self._is_maximized:
            resize_edge = self.get_edge(pos)
            if resize_edge:
                if self.initiate_resize(resize_edge, event.globalPosition().toPoint()):
                    return
        
        # Since content_wrapper is removed, handle activation directly

        self.on_activation_request()
        super().mousePressEvent(event)
        
    def initiate_resize(self, edge: str, start_pos: QPoint):
        """
        Initiate resize operation from title bar or container edge.
        This consolidates resize initiation logic in one place.
        
        Args:
            edge: Resize edge (e.g., "top", "left", "top_left", etc.)
            start_pos: Global mouse position where resize started
        """
        if self._is_maximized:
            return False
            
        self.resizing = True
        self.resize_edge = edge
        self.resize_start_pos = start_pos
        self.resize_start_geom = self.geometry()
        
        # Create and show resize overlay
        if not self._resize_overlay:
            self._resize_overlay = ResizeOverlay()
        
        self._resize_overlay.set_original_geometry(self.resize_start_geom)
        self._resize_overlay.show_overlay()
        
        # Disable content updates during resize
        self._disable_content_updates()
        
        # Set manager state
        if self.manager:
            self.manager._set_state(DockingState.RESIZING_WINDOW)
            
        return True
        
    def _disable_content_updates(self):
        """Disable updates on content area to prevent flicker during resize."""
        if not self._content_updates_disabled:
            self.content_area.setUpdatesEnabled(False)
            self._content_updates_disabled = True
            
    def _enable_content_updates(self):
        """Re-enable updates on content area after resize completes."""
        if self._content_updates_disabled:
            self.content_area.setUpdatesEnabled(True)
            self._content_updates_disabled = False

    def handle_resize_move(self, global_pos: QPoint):
        """
        Centralized resize handling method using lightweight overlay.
        Only updates the overlay geometry during drag - actual container
        geometry is applied once on mouseRelease.
        
        Args:
            global_pos: Global mouse position
        """
        if not (self.resizing and self._resize_overlay and not self._is_maximized):
            return
            
        # Calculate new geometry based on mouse delta
        delta = global_pos - self.resize_start_pos
        new_geom = QRect(self.resize_start_geom)

        # Calculate new geometry based on resize edge
        if "right" in self.resize_edge:
            new_width = self.resize_start_geom.width() + delta.x()
            new_geom.setWidth(max(new_width, self.minimumWidth()))
        if "left" in self.resize_edge:
            new_width = self.resize_start_geom.width() - delta.x()
            new_width = max(new_width, self.minimumWidth())
            new_geom.setX(self.resize_start_geom.right() - new_width)
            new_geom.setWidth(new_width)
        if "bottom" in self.resize_edge:
            new_height = self.resize_start_geom.height() + delta.y()
            new_geom.setHeight(max(new_height, self.minimumHeight()))
        if "top" in self.resize_edge:
            new_height = self.resize_start_geom.height() - delta.y()
            new_height = max(new_height, self.minimumHeight())
            new_geom.setY(self.resize_start_geom.bottom() - new_height)
            new_geom.setHeight(new_height)

        # Apply basic constraints (screen boundaries)
        self._apply_screen_constraints(new_geom)
        
        # Update only the lightweight overlay - no expensive container resize
        if not new_geom.isEmpty():
            self._resize_overlay.update_overlay_geometry(new_geom)
            
    def _apply_screen_constraints(self, geometry: QRect):
        """Apply basic screen boundary constraints to geometry."""
        screen = QApplication.screenAt(geometry.center())
        if not screen:
            screen = QApplication.primaryScreen()
            
        desktop_geom = screen.availableGeometry()
        
        # Keep at least 50px visible on screen
        if geometry.right() < desktop_geom.left() + 50:
            geometry.moveLeft(desktop_geom.left() + 50 - geometry.width())
        if geometry.left() > desktop_geom.right() - 50:
            geometry.moveLeft(desktop_geom.right() - 50)
        if geometry.bottom() < desktop_geom.top() + 50:
            geometry.moveTop(desktop_geom.top() + 50 - geometry.height())
        if geometry.top() > desktop_geom.bottom() - 50:
            geometry.moveTop(desktop_geom.bottom() - 50)

    def mouseMoveEvent(self, event: QMouseEvent):
        """
        Handles mouse movement on the container itself.
        Only handles resize operations - cursor updates are handled by eventFilter.
        """
        if self.resizing:
            # Use the consistent global source (OS-level cursor position)
            global_pos = QCursor.pos()
            self.handle_resize_move(global_pos)
            return

        # For hover states, let the eventFilter handle cursor updates
        # This prevents duplicate cursor updates
        super().mouseMoveEvent(event)

    def _update_cursor_for_hover(self, global_pos: QPoint):
        """
        Centralized cursor update method that handles all cursor states based on mouse position.
        This is the single source of truth for cursor updates during hover states.
        
        Args:
            global_pos: Global mouse position
        """
        if not self.title_bar or self._is_maximized:
            self.unsetCursor()
            return
            
        # Convert global position to local coordinates
        local_pos = self.mapFromGlobal(global_pos)
        
        # Determine if cursor is over a resize edge
        edge = self.get_edge(local_pos)
        
        # Track edge transitions to avoid duplicate cursor updates
        if not hasattr(self, '_last_edge'):
            self._last_edge = None
        
        if edge != self._last_edge:
            self._last_edge = edge
            # Only update cursor when edge actually changes
            self._update_cursor_for_edge(edge)

    def _update_cursor_for_edge(self, edge: str):
        """
        Update cursor based on resize edge.
        
        Args:
            edge: Resize edge or None
        """
        if edge:
            if edge in ["top", "bottom"]:
                self.setCursor(Qt.SizeVerCursor)
            elif edge in ["left", "right"]:
                self.setCursor(Qt.SizeHorCursor)
            elif edge in ["top_left", "bottom_right"]:
                self.setCursor(Qt.SizeFDiagCursor)
            elif edge in ["top_right", "bottom_left"]:
                self.setCursor(Qt.SizeBDiagCursor)
        else:
            self.unsetCursor()

    def mouseReleaseEvent(self, event):
        if self.resizing:
            self._finish_resize()

        if self.title_bar and self.title_bar.moving:
            self.title_bar.moving = False

        super().mouseReleaseEvent(event)
        
    def _finish_resize(self):
        """
        Finish resize operation by committing the overlay geometry to the actual container.
        This is the single expensive operation that happens at the end of resize.
        """
        if not self._resize_overlay:
            return
            
        # Get final geometry from overlay
        final_geometry = self._resize_overlay.geometry()
        
        # Hide and cleanup overlay first
        self._resize_overlay.hide_overlay()
        self._resize_overlay.deleteLater()
        self._resize_overlay = None
        
        # Apply final geometry to the actual container (single expensive operation)
        self.setGeometry(final_geometry)
        
        # Re-enable content updates
        self._enable_content_updates()
        
        # Reset resize state
        self.resizing = False
        self.resize_edge = None
        
        # Reset cursor
        self.unsetCursor()
        
        # Reset manager state
        if self.manager:
            self.manager._set_state(DockingState.IDLE)

    def update_content_event_filters(self):
        """
        Cached event filter setup to prevent redundant operations.
        Only processes widgets that haven't been tracked before.
        """
        self.installEventFilter(self)
        
        viewport_widget_types = [QTableWidget, QTreeWidget, QListWidget, QTextEdit, QPlainTextEdit]
        
        for widget_type in viewport_widget_types:
            for widget in self.findChildren(widget_type):
                # Skip widgets we've already processed
                if widget in self._tracked_widgets:
                    continue
                    
                widget.setMouseTracking(True)
                self._tracked_widgets.add(widget)
                
                if hasattr(widget, 'viewport'):
                    viewport = widget.viewport()
                    if viewport and viewport not in self._tracked_widgets:
                        viewport.setMouseTracking(True)
                        self._tracked_widgets.add(viewport)

    def showEvent(self, event):
        """
        Overrides QWidget.showEvent to re-scan for widgets and ensure all
        event filters are correctly installed every time the container becomes visible.
        """
        self.update_content_event_filters()
        super().showEvent(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """
        Filters events from descendants. It uses a just-in-time check to ensure
        filters are installed before processing the first mouse move event.
        """
        if watched is self:
            if self.manager and not self.manager._is_updating_focus:
                if event.type() == QEvent.Type.WindowActivate:
                    try:
                        self.manager._is_updating_focus = True
                        self.manager.sync_window_activation(self)
                    finally:
                        QTimer.singleShot(0, lambda: setattr(self.manager, '_is_updating_focus', False))
                    return False

                elif event.type() == QEvent.Type.WindowDeactivate:
                    # Window deactivation no longer needs shadow updates
                    return False
            return False

        if event.type() == QEvent.Type.MouseMove:
            # Get the definitive global position from the cursor (OS-level)
            global_pos = QCursor.pos()
            
            # Scan for missing child widgets and install filters on them (late installation)
            widget_name = watched.objectName() if watched.objectName() else f"<{type(watched).__name__}>"
            local_pos = self.mapFromGlobal(global_pos)
            
            # Only do late installation check on first few moves to reduce overhead
            if not hasattr(self, '_move_count'):
                self._move_count = 0
            if self._move_count < 5:
                if widget_name == 'ContentArea':
                    all_children = self.findChildren(QWidget)
                    for child in all_children:
                        if child not in self._tracked_widgets:
                            child.installEventFilter(self)
                            child.setMouseTracking(True)
                            self._tracked_widgets.add(child)
                            
                            # Handle viewport if it exists
                            if hasattr(child, 'viewport'):
                                viewport = child.viewport()
                                if viewport and viewport not in self._tracked_widgets:
                                    viewport.installEventFilter(self)
                                    viewport.setMouseTracking(True)
                                    self._tracked_widgets.add(viewport)
                self._move_count += 1
            
            if self.resizing:
                # Handle resize geometry updates
                self.handle_resize_move(global_pos)
                # Also update cursor immediately during resize
                self._update_cursor_for_hover(global_pos)
                return True  # Consume the event
            else:
                # Handle hover cursor updates over child widgets
                self._update_cursor_for_hover(global_pos)
                return False  # Pass the event to the child
            

        return super().eventFilter(watched, event)

    def childEvent(self, event):
        """
        Overrides QWidget.childEvent to automatically install the event filter
        on any new child widget and all of its descendants using a recursive helper.
        """
        if event.type() == QEvent.Type.ChildAdded:
            child = event.child()
            if child and child.isWidgetType():
                self._install_event_filter_recursive(child)

        super().childEvent(event)

    def _install_event_filter_recursive(self, widget):
        """
        Comprehensive recursive event filter installation.
        Installs event filters on widgets, their viewports, and all children.
        """
        if not widget or widget in self._tracked_widgets:
            return

        # Install event filter and enable mouse tracking
        widget.installEventFilter(self)
        widget.setMouseTracking(True)
        self._tracked_widgets.add(widget)

        # Handle viewport widgets specifically
        if hasattr(widget, 'viewport'):
            viewport = widget.viewport()
            if viewport and viewport not in self._tracked_widgets:
                viewport.installEventFilter(self)
                viewport.setMouseTracking(True)
                self._tracked_widgets.add(viewport)

        # Recursively process all children
        children = widget.findChildren(QWidget)
        for child in children:
            if child not in self._tracked_widgets:
                self._install_event_filter_recursive(child)

    def on_activation_request(self):
        """
        This is the standard, default action to take when a widget requests activation,
        for example, by having its title bar clicked.
        """
        self.raise_()
        self.setFocus()
        if self.manager:
            self.manager.bring_to_front(self)

    def get_edge(self, pos, test_rect=None):
        """
        Determines which edge (if any) the given position is on for resize operations.
        
        Args:
            pos: Position to test
            test_rect: Optional rectangle to test against. If None, uses widget's rect.
        """
        if not self.title_bar or self._is_maximized:
            return None

        # Use provided test_rect or default to widget's own rectangle
        if test_rect is not None:
            content_rect = test_rect
        else:
            widget_rect = self.rect()
            if widget_rect.width() <= 0 or widget_rect.height() <= 0:
                return None
            content_rect = widget_rect
        
        adj_pos = pos

        margin = self.resize_margin
        on_left = 0 <= adj_pos.x() < margin
        on_right = content_rect.width() - margin < adj_pos.x() <= content_rect.width()
        on_top = 0 <= adj_pos.y() < margin
        on_bottom = content_rect.height() - margin < adj_pos.y() <= content_rect.height()


        if on_top:
            if on_left: return "top_left"
            if on_right: return "top_right"
            return "top"
        if on_bottom:
            if on_left: return "bottom_left"
            if on_right: return "bottom_right"
            return "bottom"
        if on_left: return "left"
        if on_right: return "right"
        return None

    def handle_tab_close(self, index, tab_widget=None):
        if tab_widget is None:
            tab_widget = self.sender()
        if not isinstance(tab_widget, QTabWidget): return
        content_to_remove = tab_widget.widget(index)
        owner_widget = next((w for w in self.contained_widgets if w.content_container is content_to_remove), None)
        if self.manager and owner_widget:
            self.manager.request_close_widget(owner_widget)

    def handle_tab_changed(self, index):
        """
        Called when the current tab changes in a tab widget.
        Invalidates the hit-test cache to prevent stale geometry issues.
        """
        if self.manager and hasattr(self.manager, 'hit_test_cache'):
            self.manager.hit_test_cache.invalidate()
        
        if self.manager and index >= 0:
            sender_tab_widget = self.sender()
            if isinstance(sender_tab_widget, QTabWidget):
                current_content = sender_tab_widget.currentWidget()
                if current_content:
                    active_widget = next((w for w in self.contained_widgets 
                                        if w.content_container is current_content), None)
                    if active_widget:
                        self.manager.activate_widget(active_widget)
        
        if self.manager and hasattr(self.manager, '_debug_report_layout_state'):
            self.manager._debug_report_layout_state()

    def handle_undock_tab_group(self, tab_widget):
        if self.manager:
            self.manager.undock_tab_group(tab_widget)

    def handle_close_all_tabs(self, tab_widget):
        if self.manager:
            self.manager.close_tab_group(tab_widget)

    def _create_corner_button_icon(self, icon_type: str, color=QColor("#303030")):
        """
        Creates cached corner button icons for improved performance.
        """
        return IconCache.get_corner_button_icon(icon_type, color.name(), 18)

    def _create_tab_widget_with_controls(self):
        tab_widget = TearableTabWidget()
        tab_widget.set_manager(self.manager)

        tab_widget.setStyleSheet("""
            /* === Base Pane Style === */
            QTabWidget::pane {
                border: 1px solid #C4C4C3;
                background: white;
            }

            /* === Conditional Pane Border Removal === */
            /* Correct: Only remove side and bottom borders. */
            TearableTabWidget[borderRightVisible="false"]::pane {
                border-right: none;
            }
            TearableTabWidget[borderLeftVisible="false"]::pane {
                border-left: none;
            }
            TearableTabWidget[borderBottomVisible="false"]::pane {
                border-bottom: none;
            }

            /* === Base Tab and TabBar Style === */
            QTabBar::tab {
                background: #E0E0E0;
                border: 1px solid #C4C4C3;
                padding: 6px 10px;
            }
            QTabBar::tab:selected {
                background: white;
                border-bottom-color: white; /* Merges with the pane */
            }

            /* === Conditional Border Removal for Sub-Controls === */

            /* For VERTICAL stacking: Remove top border from all tabs of the bottom widget. */
            TearableTabWidget[borderTopVisible="false"] QTabBar::tab {
                border-top: none;
            }

            /* For HORIZONTAL stacking: Only remove the border that overlaps with splitter. */
            TearableTabWidget[borderLeftVisible="false"] QTabBar::tab {
                border-left: none !important;
            }
            
            /* FINAL CORRECTION: Remove the outer border from the TAB BAR WIDGET itself. */
            TearableTabWidget[borderLeftVisible="false"] TearableTabBar {
                border-left: none;
            }
            TearableTabWidget[borderRightVisible="false"] TearableTabBar {
                border-right: none;
            }
        """)

        tab_widget.setTabsClosable(True)
        tab_widget.setMouseTracking(True)
        tab_widget.tabCloseRequested.connect(self.handle_tab_close)
        tab_widget.tabBar().tabMoved.connect(self.handle_tab_reorder)
        tab_widget.currentChanged.connect(self.handle_tab_changed)

        corner_widget = QWidget()
        corner_widget.setStyleSheet("background: #F0F0F0;")

        centering_layout = QVBoxLayout(corner_widget)
        centering_layout.setContentsMargins(0, 0, 5, 0)
        centering_layout.setSpacing(0)

        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(10)

        button_style = """
            QPushButton { border: none; background-color: transparent; border-radius: 3px; }
            QPushButton:hover { background-color: #D0D0D0; }
        """
        undock_button = QPushButton()
        undock_button.setObjectName("undockButton")
        undock_button.setIcon(self._create_corner_button_icon("restore"))
        undock_button.setFixedSize(18, 18)
        undock_button.setIconSize(QSize(18, 18))
        undock_button.setToolTip("Undock this tab group")
        undock_button.setFlat(True)
        undock_button.setStyleSheet(button_style)
        undock_button.clicked.connect(lambda: self.handle_undock_tab_group(tab_widget))

        close_button = QPushButton()
        close_button.setObjectName("closeAllButton")
        close_button.setIcon(self._create_corner_button_icon("close"))
        close_button.setFixedSize(18, 18)
        close_button.setIconSize(QSize(18, 18))
        close_button.setToolTip("Close this tab group")
        close_button.setFlat(True)
        close_button.setStyleSheet(button_style)
        close_button.clicked.connect(lambda: self.handle_close_all_tabs(tab_widget))

        button_layout.addWidget(undock_button)
        button_layout.addWidget(close_button)

        centering_layout.addStretch()
        centering_layout.addLayout(button_layout)
        centering_layout.addStretch()

        tab_widget.setCornerWidget(corner_widget, Qt.TopRightCorner)
        return tab_widget

    def _reconnect_tab_signals(self, current_item):
        self.update_content_event_filters()

        if not current_item: return
        if isinstance(current_item, QTabWidget):
            try:
                current_item.tabBar().tabMoved.disconnect()
            except RuntimeError:
                pass
            current_item.tabBar().tabMoved.connect(self.handle_tab_reorder)

            try:
                current_item.tabCloseRequested.disconnect()
            except RuntimeError:
                pass
            current_item.tabCloseRequested.connect(self.handle_tab_close)

            try:
                current_item.currentChanged.disconnect()
            except RuntimeError:
                pass
            current_item.currentChanged.connect(self.handle_tab_changed)

            corner_widget = current_item.cornerWidget()
            if corner_widget:
                undock_button = corner_widget.findChild(QPushButton, "undockButton")
                close_button = corner_widget.findChild(QPushButton, "closeAllButton")
                if undock_button:
                    try:
                        undock_button.clicked.disconnect()
                    except RuntimeError:
                        pass
                    undock_button.clicked.connect(lambda: self.handle_undock_tab_group(current_item))
                if close_button:
                    try:
                        close_button.clicked.disconnect()
                    except RuntimeError:
                        pass
                    close_button.clicked.connect(lambda: self.handle_close_all_tabs(current_item))
        elif isinstance(current_item, QSplitter):
            for i in range(current_item.count()):
                self._reconnect_tab_signals(current_item.widget(i))


    def get_target_at(self, global_pos):
        if not self.splitter: return None
        target = self._find_target_by_traversal(global_pos, self.splitter)
        if target: return target
        if self.rect().contains(self.mapFromGlobal(global_pos)): return self
        return None

    def _find_target_by_traversal(self, global_pos, current_widget):
        if not current_widget or not current_widget.isVisible(): return None
        top_left_global = current_widget.mapToGlobal(QPoint(0, 0))
        global_rect = QRect(top_left_global, current_widget.size())
        if not global_rect.contains(global_pos): return None
        if isinstance(current_widget, QTabWidget):
            current_tab_content = current_widget.currentWidget()
            return next((w for w in self.contained_widgets if w.content_container is current_tab_content), None)
        if isinstance(current_widget, QSplitter):
            for i in range(current_widget.count() - 1, -1, -1):
                child_widget = current_widget.widget(i)
                result = self._find_target_by_traversal(global_pos, child_widget)
                if result: return result
        return None

    def update_tab_icon(self, widget):
        """
        Update the tab icon for a specific widget within this container.
        
        Args:
            widget: The DockPanel widget whose tab icon should be updated
        """
        if not widget or not hasattr(widget, 'content_container'):
            return
            
        tab_widget = self._find_tab_widget_containing(widget.content_container)
        if tab_widget:
            tab_index = self._find_tab_index(tab_widget, widget.content_container)
            if tab_index != -1:
                icon = widget.get_icon() if hasattr(widget, 'get_icon') else None
                if icon:
                    tab_widget.setTabIcon(tab_index, icon)
                else:
                    # Clear the icon by setting an empty QIcon
                    tab_widget.setTabIcon(tab_index, QIcon())

    def update_tab_text(self, widget):
        """
        Update the tab text for a specific widget within this container.
        
        Args:
            widget: The DockPanel widget whose tab text should be updated
        """
        if not widget or not hasattr(widget, 'content_container'):
            return
            
        tab_widget = self._find_tab_widget_containing(widget.content_container)
        if tab_widget:
            tab_index = self._find_tab_index(tab_widget, widget.content_container)
            if tab_index != -1:
                tab_widget.setTabText(tab_index, widget.windowTitle())

    def _find_tab_widget_containing(self, content_container):
        """
        Find the QTabWidget that contains the specified content container.
        
        Args:
            content_container: The content container to search for
            
        Returns:
            QTabWidget: The tab widget containing this content, or None if not found
        """
        if not self.splitter:
            return None
            
        if isinstance(self.splitter, QTabWidget):
            # Check if this tab widget contains the content
            for i in range(self.splitter.count()):
                if self.splitter.widget(i) is content_container:
                    return self.splitter
        elif isinstance(self.splitter, QSplitter):
            # Recursively search through all child tab widgets
            return self._find_tab_widget_in_splitter(self.splitter, content_container)
            
        return None

    def _find_tab_widget_in_splitter(self, splitter, content_container):
        """
        Recursively search for a tab widget containing the content container in a splitter.
        
        Args:
            splitter: The QSplitter to search in
            content_container: The content container to find
            
        Returns:
            QTabWidget: The tab widget containing the content, or None if not found
        """
        for i in range(splitter.count()):
            child = splitter.widget(i)
            if isinstance(child, QTabWidget):
                # Check if this tab widget contains the content
                for j in range(child.count()):
                    if child.widget(j) is content_container:
                        return child
            elif isinstance(child, QSplitter):
                # Recursively search nested splitters
                result = self._find_tab_widget_in_splitter(child, content_container)
                if result:
                    return result
        return None

    def _find_tab_index(self, tab_widget, content_container):
        """
        Find the index of a content container within a tab widget.
        
        Args:
            tab_widget: The QTabWidget to search in
            content_container: The content container to find
            
        Returns:
            int: The tab index, or -1 if not found
        """
        for i in range(tab_widget.count()):
            if tab_widget.widget(i) is content_container:
                return i
        return -1

    def handle_tab_reorder(self, from_index, to_index):
        """
        Called when a tab is moved in a tab bar. Updates the layout model.
        """
        tab_bar = self.sender()
        if not tab_bar or not self.manager:
            return

        tab_widget = tab_bar.parentWidget()
        if not isinstance(tab_widget, QTabWidget):
            return

        if tab_widget.count() == 0:
            return

        content_widget = tab_widget.widget(to_index)
        owner_widget = next((w for w in self.contained_widgets if w.content_container is content_widget), None)
        if not owner_widget:
            return

        tab_group_node, _, _ = self.manager.model.find_host_info(owner_widget)
        if not tab_group_node:
            return

        widget_node_to_move = tab_group_node.children.pop(from_index)
        tab_group_node.children.insert(to_index, widget_node_to_move)


    def set_title(self, new_title: str):
        """
        Updates the title of the dock container.
        This changes both the window's official title and the visible text in the title bar.
        If preserve_title is True, title changes are ignored.
        """
        if self.preserve_title:
            return  # Prevent title changes when preserve_title is True
            
        self.setWindowTitle(new_title)
        if self.title_bar:
            self.title_bar.title_label.setText(new_title)
            self.title_bar.update()
            self.title_bar.repaint()
            self.update()
            QApplication.processEvents()

    def _generate_dynamic_title(self):
        """
        Generates a dynamic title based on the contained widgets.
        """
        if not self.contained_widgets:
            return "Empty Container"
        
        if len(self.contained_widgets) == 1:
            widget = self.contained_widgets[0]
            return widget.windowTitle()
        
        widget_names = [w.windowTitle() for w in self.contained_widgets]
        title = ", ".join(widget_names)
        
        max_length = 50
        if len(title) > max_length:
            title = title[:max_length - 3] + "..."
        
        return title
    
    def update_dynamic_title(self):
        """
        Updates the container title based on current widget contents.
        Only updates if the container has a title bar (floating containers).
        For single-widget containers, uses the widget's icon; for multi-widget containers, preserves existing icon.
        If preserve_title is True, dynamic title updates are ignored.
        """
        if self.preserve_title:
            return  # Prevent dynamic title updates when preserve_title is True
            
        if self.title_bar:
            new_title = self._generate_dynamic_title()
            
            # Handle icon based on number of widgets
            if len(self.contained_widgets) == 1:
                # Single widget: let the widget set its icon on the container
                self.set_title(new_title)
                # Trigger the widget to update the container's icon
                widget = self.contained_widgets[0]
                if hasattr(widget, '_notify_parent_container_icon_changed'):
                    widget._notify_parent_container_icon_changed()
            else:
                # Multiple widgets: preserve existing icon
                current_icon = self.get_icon()
                self.set_title(new_title)
                if current_icon:
                    self.set_icon(current_icon)
            
            # Delayed title update with same logic
            def delayed_update():
                if len(self.contained_widgets) == 1:
                    self.set_title(new_title)
                    single_widget = self.contained_widgets[0]
                    if hasattr(single_widget, '_notify_parent_container_icon_changed'):
                        single_widget._notify_parent_container_icon_changed()
                else:
                    # Multiple widgets: preserve existing icon
                    delayed_current_icon = self.get_icon()
                    self.set_title(new_title)
                    if delayed_current_icon:
                        self.set_icon(delayed_current_icon)
            
            QTimer.singleShot(50, delayed_update)

    def show_overlay(self, preset='standard'):
        if preset == 'main_empty':
            icons = None
            color = "lightblue"
            style = 'cluster'
        else:
            icons = ["top", "left", "bottom", "right"]
            color = "lightgreen"
            style = 'spread'

        if self.overlay:
            self.overlay.destroy_overlay()
            self.overlay = None
            
        self.overlay = DockingOverlay(self, icons=icons, color=color, style=style)

        self.overlay.style = style
        self.overlay.reposition_icons()

        # Use the widget's own rectangle since content_wrapper is removed
        self.overlay.setGeometry(self.rect())

        self.overlay.show()
        self.overlay.raise_()

    def hide_overlay(self):
        if self.overlay: 
            if hasattr(self.overlay, 'preview_overlay'):
                self.overlay.preview_overlay.hide()
            self.overlay.hide()

    def get_dock_location(self, global_pos):
        if self.overlay:
            pos_in_overlay = self.overlay.mapFromGlobal(global_pos)
            return self.overlay.get_dock_location(pos_in_overlay)
        return None

    def show_preview(self, location):
        if self.overlay: self.overlay.show_preview(location)

    def dragEnterEvent(self, event: QDragEnterEvent):
        """
        Handles drag enter events for Qt-native drag and drop.
        Accepts the drag if it contains a valid JCDock widget.
        """
        if self._is_valid_widget_drag(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent):
        """
        Handles drag move events for Qt-native drag and drop.
        This is the only place responsible for showing overlays during a native drag.
        """
        if not self._is_valid_widget_drag(event):
            event.ignore()
            return

        event.acceptProposedAction()
        
        if not self.manager:
            return

        local_pos = event.position().toPoint() if hasattr(event, 'position') else event.pos()
        global_pos = self.mapToGlobal(local_pos)
        
        self.manager.handle_qdrag_move(global_pos)

    def dragLeaveEvent(self, event: QDragLeaveEvent):
        """
        Handles drag leave events for Qt-native drag and drop.
        Hides overlays when drag leaves this container.
        """
        self.hide_overlay()
        event.accept()

    def dropEvent(self, event: QDropEvent):
        """
        Handles drop events for Qt-native drag and drop.
        Uses the manager's centralized target information.
        """
        if not self._is_valid_widget_drag(event):
            event.ignore()
            return

        if not self.manager:
            event.ignore()
            return

        widget_id = self._extract_widget_id(event)
        if not widget_id:
            event.ignore()
            return

        if self.manager.last_dock_target:
            target, location = self.manager.last_dock_target
            
            if len(self.manager.last_dock_target) == 3:
                target_tab_widget, action, index = self.manager.last_dock_target
                success = self.manager.dock_widget_from_drag(widget_id, target_tab_widget, "insert")
            else:
                success = self.manager.dock_widget_from_drag(widget_id, target, location)
                
            if success:
                event.setDropAction(Qt.MoveAction)
                event.accept()
            else:
                event.ignore()
        else:
            event.ignore()

    def _is_valid_widget_drag(self, event):
        """
        Checks if the drag event contains a valid JCDock widget.
        """
        mime_data = event.mimeData()
        return mime_data.hasFormat("application/x-jcdock-widget")

    def _extract_widget_id(self, event):
        """
        Extracts the widget persistent ID from the drag event's MIME data.
        """
        mime_data = event.mimeData()
        
        if mime_data.hasFormat("application/x-jcdock-widget"):
            return mime_data.data("application/x-jcdock-widget").data().decode('utf-8')
        
        return None

    def update_corner_widget_visibility(self):
        """
        Updates corner widget visibility based on container layout rules.
        """
        if isinstance(self.splitter, QTabWidget):
            tab_widget = self.splitter
            corner_widget = tab_widget.cornerWidget()
            if corner_widget:
                tab_count = tab_widget.count()
                is_persistent = self.manager._is_persistent_root(self) if self.manager else False
                
                corner_widget.setVisible(True)
                
                close_button = corner_widget.findChild(QPushButton, "closeAllButton")
                if close_button:
                    if not is_persistent:
                        close_button.setVisible(False)
                    else:
                        close_button.setVisible(True)
                
                undock_button = corner_widget.findChild(QPushButton, "undockButton")
                if undock_button:
                    undock_button.setVisible(True)
                
                tab_widget.style().unpolish(tab_widget)
                tab_widget.style().polish(tab_widget)
                tab_widget.update()
        
        elif isinstance(self.splitter, QSplitter):
            tab_widgets = self.splitter.findChildren(QTabWidget)
            for tab_widget in tab_widgets:
                corner_widget = tab_widget.cornerWidget()
                if corner_widget:
                    corner_widget.setVisible(True)
                    
                    tab_widget.style().unpolish(tab_widget)
                    tab_widget.style().polish(tab_widget)
                    tab_widget.update()
    
    @property
    def is_persistent_root(self) -> bool:
        """Check if this container is a persistent root that should never be closed."""
        return self._is_persistent_root
    
    def set_persistent_root(self, is_persistent: bool = True):
        """Set whether this container is a persistent root that should never be closed."""
        self._is_persistent_root = is_persistent