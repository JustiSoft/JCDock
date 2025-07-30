import re
from PySide6.QtWidgets import QWidget, QSplitter, QVBoxLayout, QTabWidget, QHBoxLayout, QPushButton, QStyle, \
    QApplication
from PySide6.QtCore import Qt, QRect, QEvent, QPoint, QRectF, QSize, QTimer, QPointF, QLineF, QObject
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPainterPath, QBrush, QRegion, QPixmap, QPen, QIcon, QPolygonF, \
    QPalette, QDragEnterEvent, QDragMoveEvent, QDragLeaveEvent, QDropEvent
from PySide6.QtWidgets import QTableWidget, QTreeWidget, QListWidget, QTextEdit, QPlainTextEdit, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QSlider, QScrollBar

from ..core.docking_state import DockingState
from .tearable_tab_widget import TearableTabWidget
from .title_bar import TitleBar
from .dock_panel import DockPanel
from ..interaction.docking_overlay import DockingOverlay
from ..utils.icon_cache import IconCache
from ..utils.resize_cache import ResizeCache
from ..utils.resize_throttler import ResizeThrottler
from ..utils.windows_shadow import apply_native_shadow


class DockContainer(QWidget):
    def __init__(self, orientation=Qt.Horizontal, margin_size=5, parent=None, manager=None,
                 show_title_bar=True, title_bar_color=None):
        super().__init__(parent)

        # Initialize tracking set early before any addWidget calls that trigger childEvent
        self._tracked_widgets = set()
        
        self._background_color = QColor("#F0F0F0")

        if title_bar_color is not None:
            self._title_bar_color = title_bar_color
        else:
            self._title_bar_color = QColor("#C0D3E8")

        self.setObjectName("DockContainer")
        self.manager = manager
        
        self._is_persistent_root = False
        
        if show_title_bar:
            self.setWindowTitle("Docked Widgets")
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
            self.setStyleSheet("""
                DockContainer {
                    background-color: #F0F0F0;
                    border: 1px solid #6A8EAE;
                }
            """)
            
            self.main_layout = QVBoxLayout(self)
        else:
            self.setStyleSheet("""
                DockContainer {
                    background-color: #F0F0F0;
                    border: 1px solid #6A8EAE;
                }
            """)
            self.main_layout = QVBoxLayout(self)
            
        # Remove the content_wrapper - no longer needed
        self.content_wrapper = None
        self.container_layout = None
            
        self.main_layout.setContentsMargins(2, 2, 2, 4)
        self.main_layout.setSpacing(0)

        self.title_bar = None
        if show_title_bar:
            self.title_bar = TitleBar("Docked Widgets", self, top_level_widget=self)
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
        
        # Initialize resize optimization components
        self._resize_cache = ResizeCache()
        self._resize_throttler = None  # Initialized when resize starts
        self._cursor_update_timer = None  # For debounced cursor updates
        
        self.setAcceptDrops(True)
        
        # Apply native Windows shadow for containers with title bars
        if show_title_bar:
            apply_native_shadow(self)

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
        if self.manager:
            if self in self.manager.model.roots:
                self.manager._cleanup_widget_references(self)
        super().closeEvent(event)

    def paintEvent(self, event):
        # Default paint event is sufficient for opaque containers
        super().paintEvent(event)

    def mousePressEvent(self, event):
        from .dock_panel import DockPanel

        pos = event.position().toPoint()
        
        # Check for resize edges first
        if self.title_bar and not self._is_maximized:
            self.resize_edge = self.get_edge(pos)
            if self.resize_edge:
                self.resizing = True
                self.resize_start_pos = event.globalPosition().toPoint()
                self.resize_start_geom = self.geometry()
                
                # Initialize resize optimization components
                self._resize_cache.cache_resize_constraints(self, False, 0)
                
                # Set up performance monitoring if available
                if (self.manager and hasattr(self.manager, 'performance_monitor') and 
                    self.manager.performance_monitor):
                    self._resize_cache.set_performance_monitor(self.manager.performance_monitor)
                
                # Initialize throttler for this resize operation
                self._resize_throttler = ResizeThrottler(self, interval_ms=16)
                if (self.manager and hasattr(self.manager, 'performance_monitor') and 
                    self.manager.performance_monitor):
                    self._resize_throttler.set_performance_monitor(self.manager.performance_monitor)
                
                if self.manager:
                    self.manager._set_state(DockingState.RESIZING_WINDOW)
                    
                return
        
        # Since content_wrapper is removed, handle activation directly

        self.on_activation_request()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        """
        Optimized mouse movement handler for resizing operations.
        Uses caching and throttling to eliminate expensive operations during resize.
        """
        if self.resizing and not self._is_maximized and self._resize_throttler:
            # Use optimized resize handling with caching and throttling
            delta = event.globalPosition().toPoint() - self.resize_start_pos
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

            # Validate screen boundaries if widget moved to different screen
            if not self._resize_cache.validate_cached_screen(self):
                self._resize_cache.update_screen_cache(self)

            # Apply cached constraints (replaces expensive inline calculations)
            constrained_geom = self._resize_cache.apply_constraints_to_geometry(new_geom)
            
            if not constrained_geom.isEmpty():
                # Use throttler to batch geometry updates
                self._resize_throttler.request_resize(constrained_geom)
            return

        # Handle cursor updates for resize edges (optimized with caching)
        if self.title_bar and not self._is_maximized:
            pos = event.position().toPoint()
            
            # Check cached edge first
            cached_edge = self._resize_cache.get_cached_edge(pos)
            if cached_edge is not None:
                edge = cached_edge
            else:
                # Calculate edge and cache it
                edge = self.get_edge(pos)
                self._resize_cache.cache_edge_detection(pos, edge)
            
            self._update_cursor_for_edge(edge)
        else:
            self.unsetCursor()

        super().mouseMoveEvent(event)

    def _update_cursor_for_edge(self, edge: str):
        """
        Update cursor based on resize edge with debouncing to prevent flicker.
        
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
            # Flush any pending resize operations immediately
            if self._resize_throttler:
                self._resize_throttler.flush_pending()
                self._resize_throttler.cleanup()
                self._resize_throttler = None
            
            # Clear resize cache
            self._resize_cache.clear_cache()
            
            self.resizing = False
            self.resize_edge = None
            
            if self.manager:
                self.manager._set_state(DockingState.IDLE)

        if self.title_bar and self.title_bar.moving:
            self.title_bar.moving = False

        super().mouseReleaseEvent(event)

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
            is_moving = self.title_bar.moving if self.title_bar else False
            if self.resizing or is_moving:
                mapped_event = QMouseEvent(
                    event.type(), self.mapFromGlobal(watched.mapToGlobal(event.pos())),
                    event.globalPosition(), event.button(),
                    event.buttons(), event.modifiers()
                )
                self.mouseMoveEvent(mapped_event)
                return True
            

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
        Cached filter installation to prevent redundant operations.
        Only processes widgets that haven't been tracked before.
        """
        if not widget or widget in self._tracked_widgets:
            return

        widget.setMouseTracking(True)
        self._tracked_widgets.add(widget)

        if hasattr(widget, 'viewport'):
            viewport = widget.viewport()
            if viewport and viewport not in self._tracked_widgets:
                viewport.setMouseTracking(True)
                self._tracked_widgets.add(viewport)

    def on_activation_request(self):
        """
        This is the standard, default action to take when a widget requests activation,
        for example, by having its title bar clicked.
        """
        self.raise_()
        self.setFocus()
        if self.manager:
            self.manager.bring_to_front(self)

    def get_edge(self, pos):
        """
        Determines which edge (if any) the given position is on for resize operations.
        """
        if not self.title_bar or self._is_maximized:
            return None

        # Use the full widget rectangle as the content area
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
            QTabWidget::pane {
                border: 1px solid #C4C4C3;
                background: white;
            }

            QTabBar::tab:!selected {
                background: #E0E0E0;
                border: 1px solid #C4C4C3;
                padding: 6px 10px;
            }

            QTabBar::tab:selected {
                background: white;
                border: 1px solid #C4C4C3;
                border-bottom-color: white;
                padding: 6px 10px;
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
        """
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
        """
        if self.title_bar:
            new_title = self._generate_dynamic_title()
            self.set_title(new_title)
            QTimer.singleShot(50, lambda: self.set_title(new_title))

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