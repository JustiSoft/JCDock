import re
from PySide6.QtWidgets import QWidget, QSplitter, QVBoxLayout, QTabWidget, QHBoxLayout, QPushButton, QStyle, \
    QApplication, QGraphicsDropShadowEffect
from PySide6.QtCore import Qt, QRect, QEvent, QPoint, QRectF, QSize, QTimer, QPointF, QLineF, QObject
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPainterPath, QBrush, QRegion, QPixmap, QPen, QIcon, QPolygonF, \
    QPalette, QDragEnterEvent, QDragMoveEvent, QDragLeaveEvent, QDropEvent
from PySide6.QtWidgets import QTableWidget, QTreeWidget, QListWidget, QTextEdit, QPlainTextEdit, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QSlider, QScrollBar

from .docking_state import DockingState
from .tearable_tab_widget import TearableTabWidget
from .title_bar import TitleBar
from .dock_panel import DockPanel
from .docking_overlay import DockingOverlay
from .icon_cache import IconCache


class DockContainer(QWidget):
    def __init__(self, orientation=Qt.Horizontal, margin_size=5, parent=None, manager=None, create_shadow=True,
                 show_title_bar=True, title_bar_color=None):
        super().__init__(parent)

        self._should_draw_shadow = create_shadow and show_title_bar
        self._shadow_effect = None
        self._shadow_padding = 25
        self._blur_radius = 15 if self._should_draw_shadow else 0
        self._shadow_color_unfocused = QColor(0, 0, 0, 60)
        self._shadow_color_focused = QColor(0, 0, 0, 100)
        self._feather_power = 3.0
        self._shadow_color = self._shadow_color_focused
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
            self.setAttribute(Qt.WA_TranslucentBackground, True)
            self.setStyleSheet("DockContainer { background: transparent; }")
            
            self.content_wrapper = QWidget()
            self.content_wrapper.setObjectName("ContentWrapper")
            self.content_wrapper.setStyleSheet("""
                QWidget#ContentWrapper {
                    background-color: #F0F0F0;
                    border: 1px solid #6A8EAE;
                    border-radius: 8px;
                }
            """)
            
            self.container_layout = QVBoxLayout(self)
            shadow_margin = self._shadow_padding if self._should_draw_shadow else 4
            self.container_layout.setContentsMargins(shadow_margin, shadow_margin, shadow_margin, shadow_margin)
            self.container_layout.setSpacing(0)
            self.container_layout.addWidget(self.content_wrapper)
            
            self.main_layout = QVBoxLayout(self.content_wrapper)
        else:
            self.content_wrapper = None
            self.container_layout = None
            self.setStyleSheet("""
                DockContainer {
                    background-color: #F0F0F0;
                    border: 1px solid #6A8EAE;
                    border-radius: 8px;
                }
            """)
            self.main_layout = QVBoxLayout(self)
            
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
        
        self.setAcceptDrops(True)
        
        if self._should_draw_shadow:
            self._setup_shadow_effect()
        
            
    def _setup_shadow_effect(self):
        """
        Sets up the QGraphicsDropShadowEffect for floating containers with geometry validation.
        """
        if not self._shadow_effect and self.content_wrapper:
            widget_size = self.size()
            min_shadow_size = QSize(100, 100)
            
            if (widget_size.width() >= min_shadow_size.width() and 
                widget_size.height() >= min_shadow_size.height() and
                self._blur_radius > 0):
                
                content_width = widget_size.width() - (2 * self._blur_radius)
                content_height = widget_size.height() - (2 * self._blur_radius)
                
                if content_width > 50 and content_height > 50:
                    self._shadow_effect = QGraphicsDropShadowEffect()
                    self._shadow_effect.setBlurRadius(self._blur_radius)
                    self._shadow_effect.setColor(self._shadow_color_focused)
                    self._shadow_effect.setOffset(0, 0)
                    self.content_wrapper.setGraphicsEffect(self._shadow_effect)
                    self.content_wrapper.update()
                else:
                    self._should_draw_shadow = False
                    self._blur_radius = 0
            
    def _remove_shadow_effect(self):
        """
        Removes the shadow effect (for docked containers).
        """
        if self._shadow_effect and self.content_wrapper:
            self.content_wrapper.setGraphicsEffect(None)
            self._shadow_effect = None
            self.content_wrapper.update()
            
    def _update_shadow_focus(self, is_focused):
        """
        Updates shadow color based on focus state with geometry validation.
        """
        if self._shadow_effect and self.content_wrapper:
            color = self._shadow_color_focused if is_focused else self._shadow_color_unfocused
            self._shadow_effect.setColor(color)
            self.content_wrapper.update()
            self.update()
            
    def _deactivate_other_containers(self):
        """
        Deactivates shadows on all other floating containers when this one is activated.
        """
        if not self.manager:
            return
            
        for container in self.manager.model.roots.keys():
            if isinstance(container, DockContainer) and container is not self:
                if container._shadow_effect and container.content_wrapper:
                    container._shadow_effect.setColor(container._shadow_color_unfocused)
                    container.content_wrapper.update()
            
    def enable_shadow(self):
        """
        Enables the shadow effect for floating windows.
        Called when a container becomes floating.
        """
        if self.content_wrapper and self._should_draw_shadow and not self._shadow_effect:
            self._setup_shadow_effect()
            
    def disable_shadow(self):
        """
        Disables the shadow effect for docked windows.
        Called when a container is docked.
        """
        if self._shadow_effect:
            self._remove_shadow_effect()
                
    def _validate_shadow_geometry(self):
        """
        Validates if current widget geometry supports shadow rendering.
        """
        if not self._should_draw_shadow or self._blur_radius <= 0:
            return False
            
        widget_size = self.size()
        min_shadow_size = QSize(100, 100)
        
        if (widget_size.width() < min_shadow_size.width() or 
            widget_size.height() < min_shadow_size.height()):
            return False
            
        content_width = widget_size.width() - (2 * self._blur_radius)
        content_height = widget_size.height() - (2 * self._blur_radius)
        
        return content_width > 50 and content_height > 50

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
            if self._shadow_effect:
                self._shadow_effect.setEnabled(True)
            self._is_maximized = False
            self.title_bar.maximize_button.setIcon(self.title_bar._create_control_icon("maximize"))
        else:
            self._normal_geometry = self.geometry()
            if self._shadow_effect:
                self._shadow_effect.setEnabled(False)
            screen = QApplication.screenAt(self.pos())
            if not screen:
                screen = QApplication.primaryScreen()
            self.setGeometry(screen.availableGeometry())
            self._is_maximized = True
            self.title_bar.maximize_button.setIcon(self.title_bar._create_control_icon("restore"))

    def resizeEvent(self, event):
        """
        Enhanced resize event handler with shadow geometry validation.
        """
        super().resizeEvent(event)
        
        if self._shadow_effect and not self._validate_shadow_geometry():
            self._remove_shadow_effect()
        elif self._should_draw_shadow and not self._shadow_effect and self._validate_shadow_geometry():
            self._setup_shadow_effect()

    def closeEvent(self, event):
        if self.manager:
            if self in self.manager.model.roots:
                self.manager._cleanup_widget_references(self)
        super().closeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self.content_wrapper:
            painter.fillRect(self.rect(), Qt.transparent)
            return
        
        widget_rect = self.rect()
        
        if widget_rect.width() <= 0 or widget_rect.height() <= 0:
            return
            
        safe_paint_rect = widget_rect.intersected(event.rect())
        if safe_paint_rect.isEmpty():
            return
            
        painter.setClipRect(safe_paint_rect)
        
        painter.setClipping(False)

    def mousePressEvent(self, event):
        from .dock_panel import DockPanel

        pos = event.position().toPoint()
        
        if self.content_wrapper:
            content_rect = self.content_wrapper.geometry()
            
            if not content_rect.contains(pos):
                self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
                underlying = QApplication.widgetAt(event.globalPosition().toPoint())
                if underlying and underlying.window() is not self:
                    target_window = underlying.window()
                    if target_window:
                        target_window.raise_()
                        target_window.activateWindow()
                        if self.manager and isinstance(target_window, (DockPanel, DockContainer)):
                            self.manager.bring_to_front(target_window)
                        QApplication.sendEvent(underlying, event)
                self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
                return
        else:
            content_rect = self.rect()

        self.on_activation_request()

        if self.title_bar and not self._is_maximized:
            self.resize_edge = self.get_edge(pos)
            if self.resize_edge:
                self.resizing = True
                self.resize_start_pos = event.globalPosition().toPoint()
                self.resize_start_geom = self.geometry()
                
                if self.manager:
                    self.manager._set_state(DockingState.RESIZING_WINDOW)
                    
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        """
        Handles mouse movement for resizing operations and all cursor logic.
        Enhanced with geometry validation.
        """
        if self.resizing and not self._is_maximized:
            delta = event.globalPosition().toPoint() - self.resize_start_pos
            new_geom = QRect(self.resize_start_geom)

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

            min_width = max(self.minimumWidth(), 100)
            min_height = max(self.minimumHeight(), 100)
            
            if new_geom.width() < min_width:
                new_geom.setWidth(min_width)
            if new_geom.height() < min_height:
                new_geom.setHeight(min_height)
                
            if self._should_draw_shadow:
                shadow_margin = 2 * self._blur_radius
                min_shadow_width = shadow_margin + 50
                min_shadow_height = shadow_margin + 50
                
                if new_geom.width() < min_shadow_width:
                    new_geom.setWidth(min_shadow_width)
                if new_geom.height() < min_shadow_height:
                    new_geom.setHeight(min_shadow_height)
            
            screen = QApplication.screenAt(self.pos())
            if not screen:
                screen = QApplication.primaryScreen()
            screen_geom = screen.availableGeometry()
            
            if new_geom.left() < screen_geom.left():
                new_geom.moveLeft(screen_geom.left())
            if new_geom.top() < screen_geom.top():
                new_geom.moveTop(screen_geom.top())
            if new_geom.right() > screen_geom.right():
                new_geom.moveRight(screen_geom.right())
            if new_geom.bottom() > screen_geom.bottom():
                new_geom.moveBottom(screen_geom.bottom())
                
            if (new_geom.width() > 0 and new_geom.height() > 0 and
                new_geom.width() <= 5000 and new_geom.height() <= 5000):
                self.setGeometry(new_geom)
            return

        if self.title_bar and not self._is_maximized:
            edge = self.get_edge(event.position().toPoint())
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
        else:
            self.unsetCursor()

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.resizing:
            self.resizing = False
            self.resize_edge = None
            
            if self.manager:
                self.manager._set_state(DockingState.IDLE)

        if self.title_bar and self.title_bar.moving:
            self.title_bar.moving = False

        super().mouseReleaseEvent(event)

    def update_content_event_filters(self):
        """
        Lightweight event filter setup now that global filtering handles most coordination.
        Only installs filters where component-specific behavior is needed.
        """
        self.installEventFilter(self)
        
        viewport_widget_types = [QTableWidget, QTreeWidget, QListWidget, QTextEdit, QPlainTextEdit]
        
        for widget_type in viewport_widget_types:
            for widget in self.findChildren(widget_type):
                widget.setMouseTracking(True)
                if hasattr(widget, 'viewport'):
                    viewport = widget.viewport()
                    if viewport:
                        viewport.setMouseTracking(True)

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
                        self._deactivate_other_containers()
                        self._update_shadow_focus(True)
                        self.manager.sync_window_activation(self)
                    finally:
                        QTimer.singleShot(0, lambda: setattr(self.manager, '_is_updating_focus', False))
                    return False

                elif event.type() == QEvent.Type.WindowDeactivate:
                    try:
                        self.manager._is_updating_focus = True
                        self._update_shadow_focus(False)
                    finally:
                        QTimer.singleShot(0, lambda: setattr(self.manager, '_is_updating_focus', False))
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
        Lightweight filter installation now that global filtering handles coordination.
        Only ensures mouse tracking is enabled for event generation.
        """
        if not widget:
            return

        widget.setMouseTracking(True)

        if hasattr(widget, 'viewport'):
            viewport = widget.viewport()
            if viewport:
                viewport.setMouseTracking(True)

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
        Updated to work with content_wrapper architecture.
        """
        if not self.title_bar or self._is_maximized:
            return None

        if self.content_wrapper:
            content_rect = self.content_wrapper.geometry()
            
            if not content_rect.contains(pos):
                return None
                
            adj_pos = pos - content_rect.topLeft()
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

        if self.content_wrapper:
            self.overlay.setGeometry(self.content_wrapper.geometry())
        elif hasattr(self, 'inner_content_widget') and self.inner_content_widget:
            inner_geom = self.inner_content_widget.geometry()
            self.overlay.setGeometry(inner_geom)
        else:
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