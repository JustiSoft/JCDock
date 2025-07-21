import re
from PySide6.QtWidgets import QWidget, QSplitter, QVBoxLayout, QTabWidget, QHBoxLayout, QPushButton, QStyle, \
    QApplication, QGraphicsDropShadowEffect
from PySide6.QtCore import Qt, QRect, QEvent, QPoint, QRectF, QSize, QTimer, QPointF, QLineF, QObject
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPainterPath, QBrush, QRegion, QPixmap, QPen, QIcon, QPolygonF, \
    QPalette
from PySide6.QtWidgets import QTableWidget, QTreeWidget, QListWidget, QTextEdit, QPlainTextEdit, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QSlider, QScrollBar

from .tearable_tab_widget import TearableTabWidget
from .dockable_widget import TitleBar, DockableWidget
from .docking_overlay import DockingOverlay
from .icon_cache import IconCache


class DockContainer(QWidget):
    def __init__(self, orientation=Qt.Horizontal, margin_size=5, parent=None, manager=None, create_shadow=True,
                 show_title_bar=True, title_bar_color=None):
        super().__init__(parent)

        self._should_draw_shadow = create_shadow
        self._shadow_effect = None
        self._shadow_padding = 25
        self._blur_radius = 25 if self._should_draw_shadow else 0
        self._shadow_color_unfocused = QColor(0, 0, 0, 40)
        self._shadow_color_focused = QColor(0, 0, 0, 75)
        self._feather_power = 3.0
        self._shadow_color = self._shadow_color_focused
        self._background_color = QColor("#F0F0F0")

        # Set the color based on whether the parameter was provided.
        if title_bar_color is not None:
            self._title_bar_color = title_bar_color
        else:
            self._title_bar_color = QColor("#C0D3E8")  # Default title bar color

        self.setObjectName("DockContainer")
        self.manager = manager
        self.setAttribute(Qt.WA_TranslucentBackground)

        if show_title_bar:
            self.setWindowTitle("Docked Widgets")
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(self._blur_radius, self._blur_radius, self._blur_radius, self._blur_radius)
        self.main_layout.setSpacing(0)

        self.title_bar = None
        if show_title_bar:
            self.title_bar = TitleBar("Docked Widgets", self, top_level_widget=self)
            self.main_layout.addWidget(self.title_bar, 0)
            self.title_bar.setMouseTracking(True)

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

        self.setMinimumSize(200 + 2 * self._blur_radius, 150 + 2 * self._blur_radius)
        self.resize_margin = 8
        self.resizing = False
        self.resize_edge = None
        self.resize_start_pos = None
        self.resize_start_geom = None

        # State for maximize/restore functionality
        self._is_maximized = False
        self._normal_geometry = None

        self.setMouseTracking(True)
        self.content_area.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        self.installEventFilter(self)
        self.content_area.installEventFilter(self)

        self._filters_installed = False
        
        # Set up shadow effect if needed
        if self._should_draw_shadow:
            self._setup_shadow_effect()
        
    def eventFilter(self, watched, event):
        """
        Handles focus changes for shadow color updates.
        """
        if watched is self:
            if event.type() == QEvent.Type.WindowActivate:
                self._update_shadow_focus(True)
                return False
            elif event.type() == QEvent.Type.WindowDeactivate:
                self._update_shadow_focus(False)
                return False
        return super().eventFilter(watched, event)
            
    def _setup_shadow_effect(self):
        """
        Sets up the QGraphicsDropShadowEffect for floating containers.
        """
        if not self._shadow_effect:
            # Apply shadow effect to the main widget
            self._shadow_effect = QGraphicsDropShadowEffect()
            self._shadow_effect.setBlurRadius(25)
            self._shadow_effect.setColor(QColor(0, 0, 0, 75))
            self._shadow_effect.setOffset(0, 0)
            self.setGraphicsEffect(self._shadow_effect)
            # Force a repaint to ensure proper rendering
            self.update()
            
    def _remove_shadow_effect(self):
        """
        Removes the shadow effect (for docked containers).
        """
        if self._shadow_effect:
            self.setGraphicsEffect(None)
            self._shadow_effect = None
            # Force a repaint to ensure proper rendering
            self.update()
            
    def _update_shadow_focus(self, is_focused):
        """
        Updates shadow color based on focus state.
        """
        if self._shadow_effect:
            color = QColor(0, 0, 0, 75) if is_focused else QColor(0, 0, 0, 40)
            self._shadow_effect.setColor(color)

    def toggle_maximize(self):
        """Toggles the window between a maximized and normal state."""
        if self._is_maximized:
            # Restore to the previous geometry
            shadow_margin = 25 if self._should_draw_shadow else 0
            self.main_layout.setContentsMargins(shadow_margin, shadow_margin, shadow_margin, shadow_margin)
            self.setGeometry(self._normal_geometry)
            # Re-enable shadow when restored
            if self._shadow_effect:
                self._shadow_effect.setEnabled(True)
            self._is_maximized = False
            # Change icon back to 'maximize'
            self.title_bar.maximize_button.setIcon(self.title_bar._create_control_icon("maximize"))
        else:
            # Maximize the window
            self._normal_geometry = self.geometry()  # Save current geometry
            # Disable shadow when maximized
            if self._shadow_effect:
                self._shadow_effect.setEnabled(False)
            self.main_layout.setContentsMargins(0, 0, 0, 0)
            screen = QApplication.screenAt(self.pos())
            if not screen:
                screen = QApplication.primaryScreen()
            self.setGeometry(screen.availableGeometry())
            self._is_maximized = True
            # Change icon to 'restore'
            self.title_bar.maximize_button.setIcon(self.title_bar._create_control_icon("restore"))

    def closeEvent(self, event):
        if self.manager:
            if self in self.manager.model.roots:
                self.manager._cleanup_widget_references(self)
                if self.manager.debug_mode:
                    self.manager.model.pretty_print()
        super().closeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        painter.fillRect(self.rect(), Qt.transparent)

        # When maximized, content rect is the full widget. Otherwise, it's inset for the shadow.
        content_rect = self.rect() if self._is_maximized else self.rect().adjusted(
            self._blur_radius, self._blur_radius,
            -self._blur_radius, -self._blur_radius
        )

        # Draw the container's opaque background and border
        border_color = QColor("#6A8EAE")
        title_bg_color = QColor("#C0D3E8")
        container_bg_color = QColor("#F0F0F0")
        radius = 8.0 if not self._is_maximized else 0.0

        full_path = QPainterPath()
        full_path.addRoundedRect(QRectF(content_rect), radius, radius)

        painter.setClipPath(full_path)

        painter.fillRect(content_rect, container_bg_color)

        if self.title_bar:
            painter.fillRect(self.title_bar.geometry(), title_bg_color)

        painter.setClipping(False)
        painter.setPen(border_color)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(full_path)

    def mousePressEvent(self, event):
        from .dockable_widget import DockableWidget

        pos = event.position().toPoint()
        content_rect = self.rect().adjusted(
            self._blur_radius, self._blur_radius,
            -self._blur_radius, -self._blur_radius
        )

        # Handle click-through for shadows.
        if not content_rect.contains(pos):
            self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            underlying = QApplication.widgetAt(event.globalPosition().toPoint())
            if underlying and underlying.window() is not self:
                target_window = underlying.window()
                if target_window:
                    target_window.raise_()
                    target_window.activateWindow()
                    if self.manager and isinstance(target_window, (DockableWidget, DockContainer)):
                        self.manager.bring_to_front(target_window)
                    QApplication.sendEvent(underlying, event)
            self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
            return

        # Trigger the standard activation logic for this container.
        self.on_activation_request()

        # Check for a resize edge only on floating containers that are not maximized.
        if self.title_bar and not self._is_maximized:
            self.resize_edge = self.get_edge(pos)
            if self.resize_edge:
                self.resizing = True
                self.resize_start_pos = event.globalPosition().toPoint()
                self.resize_start_geom = self.geometry()
                # Since we are resizing, we consume the event.
                return

        # If we are not resizing, pass the event to children (title bar or content).
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        """
        Handles mouse movement for resizing operations and all cursor logic.
        """
        # --- RESIZING LOGIC (omitted for brevity, keep your existing code here) ---
        if self.resizing and not self._is_maximized:
            # (Your existing resizing code that calculates new_geom and calls self.setGeometry)
            delta = event.globalPosition().toPoint() - self.resize_start_pos
            new_geom = QRect(self.resize_start_geom)

            if "right" in self.resize_edge:
                new_geom.setWidth(self.resize_start_geom.width() + delta.x())
            if "left" in self.resize_edge:
                new_width = self.resize_start_geom.width() - delta.x()
                if new_width < self.minimumWidth(): new_width = self.minimumWidth()
                new_geom.setX(self.resize_start_geom.right() - new_width)
                new_geom.setWidth(new_width)
            if "bottom" in self.resize_edge:
                new_geom.setHeight(self.resize_start_geom.height() + delta.y())
            if "top" in self.resize_edge:
                new_height = self.resize_start_geom.height() - delta.y()
                if new_height < self.minimumHeight(): new_height = self.minimumHeight()
                new_geom.setY(self.resize_start_geom.bottom() - new_height)
                new_geom.setHeight(new_height)

            if new_geom.width() < self.minimumWidth(): new_geom.setWidth(self.minimumWidth())
            if new_geom.height() < self.minimumHeight(): new_geom.setHeight(self.minimumHeight())

            self.setGeometry(new_geom)
            return

        # --- CURSOR LOGIC ---
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

        # Add a check to ensure the title bar exists before accessing it.
        if self.title_bar and self.title_bar.moving:
            self.title_bar.moving = False

        super().mouseReleaseEvent(event)

    def update_content_event_filters(self):
        """
        Scans the entire widget hierarchy within this container and ensures the
        event filter is correctly installed on all interactive content widgets
        and their viewports.
        """
        # Define the types of widgets whose viewports are the true source of mouse events.
        viewport_widgets = (QTableWidget, QTreeWidget, QListWidget, QTextEdit, QPlainTextEdit)

        # findChildren is a reliable way to get every single QWidget descendant.
        all_descendants = self.findChildren(QWidget)

        for widget in all_descendants:
            # Install the filter on the widget itself to catch general mouse movement.
            widget.installEventFilter(self)

            # Perform the critical check for viewport-based widgets.
            if isinstance(widget, viewport_widgets):
                # This logic is taken directly from the working DockableWidget.setContent method.
                widget.setMouseTracking(True)
                if hasattr(widget, 'viewport'):
                    viewport = widget.viewport()
                    if viewport:
                        viewport.setMouseTracking(True)
                        viewport.installEventFilter(self)

        # Finally, ensure the container itself is monitored.
        self.installEventFilter(self)

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
            # ... (keep the existing WindowActivate/Deactivate logic here) ...
            if event.type() == QEvent.Type.WindowActivate:
                self._shadow_color = self._shadow_color_focused
                self.update()
            elif event.type() == QEvent.Type.WindowDeactivate:
                self._shadow_color = self._shadow_color_unfocused
                self.update()
            return False

        if event.type() == QEvent.Type.MouseMove:
            # --- NEW JUST-IN-TIME LOGIC ---
            # If filters haven't been installed for this container yet, run the
            # installation now. This catches content added after the initial show.
            if not self._filters_installed:
                self.update_content_event_filters()
                self._filters_installed = True
            # --- END NEW LOGIC ---

            is_moving = self.title_bar.moving if self.title_bar else False
            if self.resizing or is_moving:
                return super().eventFilter(watched, event)

            mapped_event = QMouseEvent(
                event.type(), self.mapFromGlobal(watched.mapToGlobal(event.pos())),
                event.globalPosition(), event.button(),
                event.buttons(), event.modifiers()
            )
            self.mouseMoveEvent(mapped_event)

        return super().eventFilter(watched, event)

    def childEvent(self, event):
        """
        Overrides QWidget.childEvent to automatically install the event filter
        on any new child widget and all of its descendants using a recursive helper.
        """
        if event.type() == QEvent.Type.ChildAdded:
            child = event.child()
            # Ensure the child is a valid widget before proceeding
            if child and child.isWidgetType():
                self._install_event_filter_recursive(child)

        super().childEvent(event)

    def _install_event_filter_recursive(self, widget):
        """
        Recursively installs this container's event filter on a widget and all its
        descendants, with special handling for viewports in scroll areas.
        """
        if not widget:
            return

        # Install on the widget itself and print for debugging.
        widget.installEventFilter(self)

        # CRITICAL: For widgets with a viewport (like QTableView), the viewport is
        # the actual source of mouse events. We must install the filter there too.
        if hasattr(widget, 'viewport'):
            viewport = widget.viewport()
            if viewport:
                viewport.installEventFilter(self)

        # Recurse through all children to catch widgets added to layouts.
        for child in widget.children():
            if isinstance(child, QWidget):
                # We recurse to handle nested children (e.g., a widget inside a layout).
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

    def get_edge(self, pos):
        """
        Determines which edge (if any) the given position is on for resize operations.
        """
        # Only allow resize on floating containers that are not maximized
        if not self.title_bar or self._is_maximized:
            return None

        # Get the content rect (inset by shadow if present)
        content_rect = self.rect().adjusted(
            self._blur_radius, self._blur_radius,
            -self._blur_radius, -self._blur_radius
        )

        # Check if position is within the content rect
        if not content_rect.contains(pos):
            return None

        # Adjust position relative to content rect
        adj_pos = pos - QPoint(self._blur_radius, self._blur_radius)

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
            # The fix is here: Call the correct public method.
            self.manager.request_close_widget(owner_widget)

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
        # Use the TearableTabWidget instead of the standard QTabWidget
        tab_widget = TearableTabWidget()
        tab_widget.set_manager(self.manager)

        # The stylesheet styles the components that are drawn.
        tab_widget.setStyleSheet("""
            QTabWidget::pane { /* The content area of the tab widget */
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
                border-bottom-color: white; /* Make it look connected */
                padding: 6px 10px;
            }
        """)

        tab_widget.setTabsClosable(True)
        tab_widget.setMouseTracking(True)
        tab_widget.tabCloseRequested.connect(self.handle_tab_close)
        # This is the new connection for tracking tab reordering.
        tab_widget.tabBar().tabMoved.connect(self.handle_tab_reorder)

        # This is the main container widget for the corner controls.
        corner_widget = QWidget()
        corner_widget.setStyleSheet("background: transparent;")

        # A vertical layout is used to manage the vertical alignment.
        centering_layout = QVBoxLayout(corner_widget)
        centering_layout.setContentsMargins(0, 0, 5, 0)  # Add right margin for spacing from the window edge
        centering_layout.setSpacing(0)

        # The horizontal layout holds the buttons themselves.
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(10)  # Spacing between the buttons

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

        # Add the buttons to the horizontal layout
        button_layout.addWidget(undock_button)
        button_layout.addWidget(close_button)

        # Add stretch, the button layout, then more stretch to vertically center.
        centering_layout.addStretch()
        centering_layout.addLayout(button_layout)
        centering_layout.addStretch()

        tab_widget.setCornerWidget(corner_widget, Qt.TopRightCorner)
        return tab_widget

    def _reconnect_tab_signals(self, current_item):
        # This method is reliably called by the DockingManager after this container's
        # layout has been fully rendered. This is the perfect moment to ensure
        # our event filters are installed on all content widgets and their viewports.
        self.update_content_event_filters()

        if not current_item: return
        if isinstance(current_item, QTabWidget):
            # Reconnect the tabMoved signal
            try:
                current_item.tabBar().tabMoved.disconnect()
            except RuntimeError:
                pass  # Signal was not connected
            current_item.tabBar().tabMoved.connect(self.handle_tab_reorder)

            try:
                current_item.tabCloseRequested.disconnect()
            except RuntimeError:
                pass
            current_item.tabCloseRequested.connect(self.handle_tab_close)

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

    def update_corner_widget_visibility(self):
        """
        Updates corner widget visibility based on new UI rules.
        """
        if not self.splitter: 
            return
            
        if isinstance(self.splitter, QTabWidget):
            # Root is TabGroupNode - apply Rules A/B
            tab_widget = self.splitter
            tab_count = tab_widget.count()
            corner_widget = tab_widget.cornerWidget()
            
            if corner_widget:
                if tab_count == 1:
                    # Rule A: Single widget state - hide corner widget
                    corner_widget.setVisible(False)
                else:
                    # Rule B: Tabbed state - show corner widget
                    corner_widget.setVisible(True)
                    
                # Apply style updates
                tab_widget.style().unpolish(tab_widget)
                tab_widget.style().polish(tab_widget)
                tab_widget.update()
        else:
            # Root is SplitterNode - apply Rule C to all child tab widgets
            tab_widgets = self.splitter.findChildren(QTabWidget)
            for tab_widget in tab_widgets:
                corner_widget = tab_widget.cornerWidget()
                if corner_widget:
                    # Rule C: Inside splitter - always show corner widget
                    corner_widget.setVisible(True)
                    
                    # Apply style updates
                    tab_widget.style().unpolish(tab_widget)
                    tab_widget.style().polish(tab_widget)
                    tab_widget.update()

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

        if self.manager.debug_mode:
            self.manager.model.pretty_print()

    def set_title(self, new_title: str):
        """
        Updates the title of the dock container.
        This changes both the window's official title and the visible text in the title bar.
        """
        self.setWindowTitle(new_title)
        if self.title_bar:
            self.title_bar.title_label.setText(new_title)

    def show_overlay(self, preset='standard'):
        # Based on the preset command from the manager, configure the overlay.
        if preset == 'main_empty':
            icons = None  # None means all 5 icons.
            color = "lightblue"
            style = 'cluster'
        else:  # The 'standard' container preset.
            icons = ["top", "left", "bottom", "right"]
            color = "lightgreen"
            style = 'spread'

        # Destroy old overlay if it exists to ensure clean state
        if self.overlay:
            self.overlay.destroy_overlay()
            self.overlay = None
            
        self.overlay = DockingOverlay(self, icons=icons, color=color, style=style)

        # To handle the case where the style might change, we re-apply it.
        self.overlay.style = style
        self.overlay.reposition_icons()

        # Calculate the geometry for the overlay based on the actual content area
        if hasattr(self, 'inner_content_widget') and self.inner_content_widget:
            # Use the inner content widget's geometry to ensure overlay is above content
            inner_geom = self.inner_content_widget.geometry()
            self.overlay.setGeometry(inner_geom)
        elif self._should_draw_shadow:
            shadow_margin = 25
            content_rect = self.rect().adjusted(
                shadow_margin, shadow_margin,
                -shadow_margin, -shadow_margin
            )
            self.overlay.setGeometry(content_rect)
        else:
            self.overlay.setGeometry(self.rect())

        self.overlay.show()
        self.overlay.raise_()

    def hide_overlay(self):
        if self.overlay: 
            # Explicitly hide the preview overlay first to prevent stuck blue areas
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