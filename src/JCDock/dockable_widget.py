# dockable_widget.py

from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QPushButton, QHBoxLayout, QStyle, QApplication, QGraphicsDropShadowEffect
from PySide6.QtCore import Qt, QPoint, QRect, QEvent, QRectF
from PySide6.QtGui import QColor, QPainter, QBrush, QMouseEvent, QPainterPath, QPalette, QRegion, QPen, QIcon, QPixmap

from .docking_overlay import DockingOverlay
from .icon_cache import IconCache


class TitleBar(QWidget):
    def __init__(self, title, parent=None, top_level_widget=None):
        super().__init__(parent)
        self._top_level_widget = top_level_widget if top_level_widget is not None else parent
        self.setObjectName(f"TitleBar_{title.replace(' ', '_')}")
        self.setAutoFillBackground(False)
        self.setFixedHeight(35)
        self.setMouseTracking(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 4, 0)
        layout.setSpacing(4)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("background: transparent; color: #101010;")
        self.title_label.setAttribute(Qt.WA_TransparentForMouseEvents)

        layout.addWidget(self.title_label, 1)

        button_style = """
            QPushButton { background-color: transparent; border: none; }
            QPushButton:hover { background-color: #D0D0D0; border-radius: 4px; }
            QPushButton:pressed { background-color: #B8B8B8; }
        """

        self.minimize_button = QPushButton()
        self.minimize_button.setIcon(self._create_control_icon("minimize"))
        self.minimize_button.setFixedSize(24, 24)
        self.minimize_button.setStyleSheet(button_style)
        self.minimize_button.clicked.connect(self._top_level_widget.showMinimized)
        layout.addWidget(self.minimize_button)

        self.maximize_button = QPushButton()
        self.maximize_button.setIcon(self._create_control_icon("maximize"))
        self.maximize_button.setFixedSize(24, 24)
        self.maximize_button.setStyleSheet(button_style)
        if hasattr(self._top_level_widget, 'toggle_maximize'):
            self.maximize_button.clicked.connect(self._top_level_widget.toggle_maximize)
        layout.addWidget(self.maximize_button)

        self.close_button = QPushButton()
        self.close_button.setIcon(self._create_control_icon("close"))
        self.close_button.setFixedSize(24, 24)
        self.close_button.setStyleSheet(button_style)

        # This is the fix: The button now calls the correct manager method based on the window type.
        self.close_button.clicked.connect(self.on_close_button_clicked)

        layout.addWidget(self.close_button)

        self.moving = False
        self.offset = QPoint()

    def on_close_button_clicked(self):
        """
        Determines whether to close a single widget or a whole container.
        """
        # Local import to avoid circular dependency at module level
        from .dock_container import DockContainer

        manager = getattr(self._top_level_widget, 'manager', None)
        if not manager:
            self._top_level_widget.close()
            return

        if isinstance(self._top_level_widget, DockContainer):
            manager.request_close_container(self._top_level_widget)
        else:  # It's a DockableWidget
            manager.request_close_widget(self._top_level_widget)

    def mouseMoveEvent(self, event):
        # If the title bar is in "moving" mode, it has two jobs:
        # 1. Move the window.
        # 2. Ask the docking manager to check for docking opportunities.
        if self.moving:
            # 1. Move the window based on the mouse drag.
            new_widget_global = event.globalPosition().toPoint() - self.offset
            self._top_level_widget.move(new_widget_global)

            # 2. Delegate the complex docking logic to the manager.
            if self._top_level_widget.manager:
                self._top_level_widget.manager.handle_drag_move(self._top_level_widget, event)

            # The event is fully handled, so we prevent further processing.
            return

        # If not moving, pass the event to the default handler to process
        # other things like hover events for tooltips, etc.
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        # Do not start a drag if clicking on any of the control buttons.
        if (self.close_button.geometry().contains(event.pos()) or
                self.maximize_button.geometry().contains(event.pos()) or
                self.minimize_button.geometry().contains(event.pos())):
            super().mousePressEvent(event)
            return

        if event.button() == Qt.LeftButton:
            pos = event.pos()
            margin = self._top_level_widget.resize_margin
            on_left = 0 <= pos.x() < margin
            on_right = self.width() - margin < pos.x() <= self.width()
            on_top = 0 <= pos.y() < margin

            edge = None
            if on_top:
                if on_left:
                    edge = "top_left"
                elif on_right:
                    edge = "top_right"
                else:
                    edge = "top"
            elif on_left:
                edge = "left"
            elif on_right:
                edge = "right"

            if edge:
                self._top_level_widget.resizing = True
                self._top_level_widget.resize_edge = edge
                self._top_level_widget.resize_start_pos = event.globalPosition().toPoint()
                self._top_level_widget.resize_start_geom = self._top_level_widget.geometry()
            else:
                # A click on the title bar is an activation request for its parent window.
                if hasattr(self._top_level_widget, 'on_activation_request'):
                    self._top_level_widget.on_activation_request()

                self.moving = True
                self.offset = event.globalPosition().toPoint() - self._top_level_widget.pos()
                self.grabMouse()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            # If we were moving, stop the move and release the mouse capture.
            if self.moving:
                self.moving = False
                self.releaseMouse()

            # Reset resizing flags on the parent.
            if self._top_level_widget.resizing:
                self._top_level_widget.resizing = False
                self._top_level_widget.resize_edge = None

    def _create_control_icon(self, icon_type: str, color=QColor("#303030")):
        """
        Creates cached window control icons for improved performance.
        """
        return IconCache.get_control_icon(icon_type, color.name(), 24)

class DockableWidget(QWidget):
    def __init__(self, title, parent=None, manager=None, persistent_id=None, title_bar_color=None):
        super().__init__(parent)

        self.content_widget = None
        self.parent_container = None
        self.resizing = False
        self._content_margin_size = 5

        self.persistent_id = persistent_id
        self._shadow_effect = None
        self._shadow_padding = 25

        if title_bar_color is not None:
            self._title_bar_color = title_bar_color
        else:
            self._title_bar_color = QColor("#E0E1E2")

        self.setObjectName(f"DockableWidget_{title.replace(' ', '_')}")
        self.setWindowTitle(title)
        self.manager = manager

        self.setAttribute(Qt.WA_TranslucentBackground)
        # This call is now safe because the attributes above exist.
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)

        self.setFocusPolicy(Qt.StrongFocus)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.title_bar = TitleBar(title, self, top_level_widget=self)
        self.main_layout.addWidget(self.title_bar)

        self.content_container = QWidget()
        self.content_container.setObjectName("ContentContainer")
        self.content_container.setMouseTracking(True)
        self.main_layout.addWidget(self.content_container)

        self.content_layout = QVBoxLayout(self.content_container)
        self.overlay = None

        self.setMinimumSize(300, 200)
        self.resize(300, 200)

        self.resize_margin = 8
        self.resize_edge = None
        self.resize_start_pos = None
        self.resize_start_geom = None

        self._is_maximized = False
        self._normal_geometry = None

        self.is_tabbed = False
        self.setMouseTracking(True)
        self.installEventFilter(self)

    def set_title_bar_color(self, new_color: QColor):
        """
        Sets the background color of the widget's title bar.
        """
        self._title_bar_color = new_color
        self.update()  # Trigger a repaint to show the new color
        
    def _setup_shadow_effect(self):
        """
        Sets up the QGraphicsDropShadowEffect for floating windows.
        """
        if not self._shadow_effect:
            # Add margins to make space for the shadow
            self.main_layout.setContentsMargins(self._shadow_padding, self._shadow_padding, self._shadow_padding, self._shadow_padding)
            # Apply shadow effect to the main widget (keep translucent background like containers)
            self._shadow_effect = QGraphicsDropShadowEffect()
            self._shadow_effect.setBlurRadius(25)
            self._shadow_effect.setColor(QColor(0, 0, 0, 75))
            self._shadow_effect.setOffset(0, 0)
            self.setGraphicsEffect(self._shadow_effect)
            # Force a repaint to ensure proper rendering
            self.update()
            
    def _remove_shadow_effect(self):
        """
        Removes the shadow effect (for docked widgets).
        """
        if self._shadow_effect:
            # Remove margins when shadow is removed
            self.main_layout.setContentsMargins(0, 0, 0, 0)
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
            self.setGeometry(self._normal_geometry)
            # Re-enable shadow when restored and restore margins
            if self._shadow_effect:
                self._shadow_effect.setEnabled(True)
                self.main_layout.setContentsMargins(self._shadow_padding, self._shadow_padding, self._shadow_padding, self._shadow_padding)
            self._is_maximized = False
            # Change icon back to 'maximize'
            self.title_bar.maximize_button.setIcon(self.title_bar._create_control_icon("maximize"))
        else:
            # Maximize the window
            self._normal_geometry = self.geometry()  # Save current geometry
            # Disable shadow when maximized and remove margins
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

    def on_activation_request(self):
        self.raise_()
        if self.manager:
            self.manager.bring_to_front(self)

    def mouseReleaseEvent(self, event):
        # This method is now only responsible for stopping a resize operation.
        if self.resizing:
            self.resizing = False
            self.resize_edge = None

        # The 'moving' state is now correctly handled by the TitleBar's release event.
        super().mouseReleaseEvent(event)

    def mousePressEvent(self, event):
        # Local import to prevent circular dependency
        from .dock_container import DockContainer

        content_rect = self.rect()
        pos = event.position().toPoint()


        # On any standard press, trigger the activation logic.
        self.on_activation_request()

        # Check for resize edges only if the widget is not docked and not maximized.
        if not self.parent_container and not self._is_maximized:
            self.resize_edge = self.get_edge(pos)
            if self.resize_edge:
                self.resizing = True
                self.resize_start_pos = event.globalPosition().toPoint()
                self.resize_start_geom = self.geometry()
            else:
                # If not resizing, pass the event to children (like the TitleBar).
                super().mousePressEvent(event)
        else:
            # If docked or maximized, never check for resize. Pass the event to children.
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):

        def set_viewport_transparency(is_transparent):
            if self.content_widget and hasattr(self.content_widget, 'viewport'):
                viewport = self.content_widget.viewport()
                if viewport and viewport.testAttribute(Qt.WA_TransparentForMouseEvents) != is_transparent:
                    viewport.setAttribute(Qt.WA_TransparentForMouseEvents, is_transparent)

        def reset_content_cursor():
            if self.content_widget:
                self.content_widget.unsetCursor()
                if hasattr(self.content_widget, 'viewport') and self.content_widget.viewport():
                    self.content_widget.viewport().unsetCursor()

        if not self.parent_container and not self._is_maximized:
            if self.resizing:
                set_viewport_transparency(True)
                delta = event.globalPosition().toPoint() - self.resize_start_pos
                new_geom = QRect(self.resize_start_geom)
                if "right" in self.resize_edge: new_geom.setWidth(self.resize_start_geom.width() + delta.x())
                if "left" in self.resize_edge:
                    new_width = self.resize_start_geom.width() - delta.x()
                    if new_width < self.minimumWidth(): new_width = self.minimumWidth()
                    new_geom.setX(self.resize_start_geom.right() - new_width)
                    new_geom.setWidth(new_width)
                if "bottom" in self.resize_edge: new_geom.setHeight(self.resize_start_geom.height() + delta.y())
                if "top" in self.resize_edge:
                    new_height = self.resize_start_geom.height() - delta.y()
                    if new_height < self.minimumHeight(): new_height = self.minimumHeight()
                    new_geom.setY(self.resize_start_geom.bottom() - new_height)
                    new_geom.setHeight(new_height)
                if new_geom.width() < self.minimumWidth(): new_geom.setWidth(self.minimumWidth())
                if new_geom.height() < self.minimumHeight(): new_geom.setHeight(self.minimumHeight())
                self.setGeometry(new_geom)
            else:
                edge = self.get_edge(event.position().toPoint())
                if edge:
                    if edge in ["top", "bottom"]: self.setCursor(Qt.SizeVerCursor)
                    elif edge in ["left", "right"]: self.setCursor(Qt.SizeHorCursor)
                    elif edge in ["top_left", "bottom_right"]: self.setCursor(Qt.SizeFDiagCursor)
                    elif edge in ["top_right", "bottom_left"]: self.setCursor(Qt.SizeBDiagCursor)
                    set_viewport_transparency(False)
                else:
                    set_viewport_transparency(False)
                    self.unsetCursor()
                    reset_content_cursor()
        else:
            set_viewport_transparency(False)
            self.unsetCursor()
            reset_content_cursor()

        super().mouseMoveEvent(event)

    def _reinstall_content_filters(self):

        if self.content_widget:
            self.content_widget.installEventFilter(self)
            if hasattr(self.content_widget, 'viewport'):
                viewport = self.content_widget.viewport()
                if viewport:
                    viewport.installEventFilter(self)

    def changeEvent(self, event):

        if event.type() == QEvent.Type.ParentChange:
            self._reinstall_content_filters()
        super().changeEvent(event)

    def eventFilter(self, watched, event):
        """
        Filters events from self and child widgets to handle focus and resizing.
        """
        if watched is self:
            if event.type() == QEvent.Type.WindowActivate:
                self._update_shadow_focus(True)
                return False
            elif event.type() == QEvent.Type.WindowDeactivate:
                self._update_shadow_focus(False)
                return False
                
        if not self.parent_container:
            is_content_source = (watched is self.content_widget)
            if not is_content_source and self.content_widget and hasattr(self.content_widget, 'viewport'):
                if watched is self.content_widget.viewport():
                    is_content_source = True

            if is_content_source:
                if event.type() == QEvent.Type.MouseMove:
                    if not self.resizing and not self.title_bar.moving:
                        mapped_event = QMouseEvent(
                            event.type(), self.mapFrom(watched, event.pos()),
                            event.globalPosition(), event.button(),
                            event.buttons(), event.modifiers()
                        )
                        self.mouseMoveEvent(mapped_event)
                        return False
                elif event.type() == QEvent.Type.Enter:
                    if not self.resizing and not self.title_bar.moving:
                        edge = self.get_edge(self.mapFrom(watched, event.pos()) if hasattr(event, 'pos') else QPoint(0, 0))
                        if not edge:
                            self.unsetCursor()
                            if self.content_widget:
                                self.content_widget.unsetCursor()
                                if hasattr(self.content_widget, 'viewport') and self.content_widget.viewport():
                                    self.content_widget.viewport().unsetCursor()

        return super().eventFilter(watched, event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        painter.fillRect(self.rect(), Qt.transparent)

        # Calculate inner content rectangle, respecting shadow margins when active
        if self._shadow_effect and not self._is_maximized:
            content_rect = self.rect().adjusted(
                self._shadow_padding, self._shadow_padding,
                -self._shadow_padding, -self._shadow_padding
            )
        else:
            content_rect = self.rect()

        border_color = QColor("#A9A9A9")
        # Use the instance attribute for the title bar background color
        title_bg_color = self._title_bar_color
        content_bg_color = self.original_bg_color if hasattr(self,
                                                             'original_bg_color') and self.original_bg_color else QColor(
            "white")
        radius = 8.0 if not self._is_maximized else 0

        full_path = QPainterPath()
        full_path.addRoundedRect(QRectF(content_rect), radius, radius)

        # Use clipping to restore the rounded corner appearance
        painter.setClipPath(full_path)
        painter.fillRect(content_rect, content_bg_color)
        
        # Adjust title bar geometry to use content_rect coordinates
        if self._shadow_effect and not self._is_maximized:
            title_bar_rect = QRect(
                content_rect.x(),
                content_rect.y(),
                content_rect.width(),
                self.title_bar.height()
            )
        else:
            title_bar_rect = self.title_bar.geometry()
        painter.fillRect(title_bar_rect, title_bg_color)

        painter.setClipping(False)
        painter.setPen(border_color)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(full_path)

    def setContent(self, widget, margin_size=5):
        self._content_margin_size = margin_size
        self.content_widget = widget
        self.content_widget.setObjectName(f"ActualContent_{self.windowTitle().replace(' ', '_')}")
        self.original_bg_color = widget.palette().color(widget.backgroundRole())
        self.content_container.setStyleSheet("background: transparent;")
        widget.setAutoFillBackground(False)
        widget.setStyleSheet("background: transparent;")
        self.content_layout.setContentsMargins(margin_size, margin_size, margin_size, margin_size)
        self.content_layout.addWidget(widget)
        if self.content_widget:
            self.content_widget.setMouseTracking(True)
            self.content_widget.installEventFilter(self)
            if hasattr(widget, 'viewport'):
                viewport = widget.viewport()
                if viewport:
                    viewport.setMouseTracking(True)
                    viewport.installEventFilter(self)
        self.update()

    def getContent(self) -> QWidget | None:
        """
        Returns the content widget that is displayed inside this dockable widget.
        This provides a consistent API with Qt's QDockWidget.
        """
        return getattr(self, 'content_widget', None)

    def get_edge(self, pos):
        # Calculate the content rectangle, respecting shadow margins when active
        if self._shadow_effect and not self._is_maximized:
            content_rect = self.rect().adjusted(
                self._shadow_padding, self._shadow_padding,
                -self._shadow_padding, -self._shadow_padding
            )
        else:
            content_rect = self.rect()

        # Check only if cursor is within the visible content rect
        if not content_rect.contains(pos):
            return None

        # Adjust position relative to content rect when shadow is active
        if self._shadow_effect and not self._is_maximized:
            adj_pos = pos - QPoint(self._shadow_padding, self._shadow_padding)
        else:
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

    def showEvent(self, event):
        """
        On show, reinstall the event filters on the content widget. This is
        critical for when this widget becomes a floating window after being
        simplified from a container, as its event handling needs to be refreshed.
        """
        self._reinstall_content_filters()
        # The existing show() method in the provided code handles auto-positioning.
        # We call the superclass's showEvent to ensure default Qt behavior.
        super().showEvent(event)

    def show_overlay(self):
        overlay_parent = self.parent_container if self.parent_container else self
        visible_widget = self.content_container
        if not self.overlay or self.overlay.parent() is not overlay_parent:
            if self.overlay: self.overlay.deleteLater()
            self.overlay = DockingOverlay(overlay_parent)
        global_pos = visible_widget.mapToGlobal(QPoint(0, 0))
        parent_local_pos = overlay_parent.mapFromGlobal(global_pos)
        self.overlay.setGeometry(QRect(parent_local_pos, visible_widget.size()))
        self.overlay.show()
        self.overlay.raise_()

    def hide_overlay(self):
        if self.overlay: self.overlay.hide()

    def get_dock_location(self, global_pos):
        if self.overlay:
            pos_in_overlay = self.overlay.mapFromGlobal(global_pos)
            return self.overlay.get_dock_location(pos_in_overlay)
        return None

    def show_preview(self, location):
        if self.overlay: self.overlay.show_preview(location)

    def show(self):
        # This is the new, intelligent show method.
        # If the widget has a manager and a main window is set, we can auto-position it.
        if self.manager and self.manager.main_window:
            # Do not auto-position a widget if it's already maximized or if it already
            # has a valid, non-zero position.
            if not self._is_maximized and self.pos().x() == 0 and self.pos().y() == 0:
                main_window_pos = self.manager.main_window.pos()

                # Use the manager's counter to create a pleasing cascade effect.
                count = self.manager.floating_widget_count
                new_global_x = main_window_pos.x() + 150 + (count % 7) * 40
                new_global_y = main_window_pos.y() + 150 + (count % 7) * 40
                self.move(new_global_x, new_global_y)

        # Set up shadow effect if this is a floating widget (not docked)
        if not self.parent_container and not self._is_maximized:
            self._setup_shadow_effect()

        # Call the original QWidget.show() to make the widget visible.
        super().show()

    def set_title(self, new_title: str):
        """
        Updates the title of the dockable widget.
        This changes both the window's official title and the visible text in the title bar.
        """
        self.setWindowTitle(new_title)
        if self.title_bar:
            self.title_bar.title_label.setText(new_title)

    # Close event no longer needs to handle a separate shadow
    def closeEvent(self, event):
        if self.manager:
            if self in self.manager.model.roots:
                self.manager._cleanup_widget_references(self)
                if self.manager.debug_mode:
                    self.manager.model.pretty_print()
        super().closeEvent(event)