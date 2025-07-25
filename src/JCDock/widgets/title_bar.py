# title_bar.py

from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QPushButton, QHBoxLayout, QStyle, QApplication, QGraphicsDropShadowEffect
from PySide6.QtCore import Qt, QPoint, QRect, QEvent, QRectF
from PySide6.QtGui import QColor, QPainter, QBrush, QMouseEvent, QPainterPath, QPalette, QRegion, QPen, QIcon, QPixmap

from ..core.docking_state import DockingState
from ..utils.icon_cache import IconCache


class TitleBar(QWidget):
    def __init__(self, title, parent=None, top_level_widget=None):
        super().__init__(parent)
        self._top_level_widget = top_level_widget if top_level_widget is not None else parent
        self.setObjectName(f"TitleBar_{title.replace(' ', '_')}")
        self.setAutoFillBackground(False)
        self.setFixedHeight(35)
        self.setMouseTracking(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 0, 2, 0)
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

        self.close_button.clicked.connect(self.on_close_button_clicked)

        layout.addWidget(self.close_button)

        self.moving = False
        self.offset = QPoint()

    def paintEvent(self, event):
        """Paint the title bar background with rounded top corners to match container."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        bg_color = QColor("#F0F0F0")
        if hasattr(self._top_level_widget, '_title_bar_color'):
            bg_color = self._top_level_widget._title_bar_color
        
        rect = QRectF(self.rect())
        path = QPainterPath()
        radius = 8.0
        
        path.moveTo(rect.left(), rect.bottom())
        path.lineTo(rect.left(), rect.top() + radius)
        path.arcTo(rect.left(), rect.top(), radius * 2, radius * 2, 180, -90)
        path.lineTo(rect.right() - radius, rect.top())
        path.arcTo(rect.right() - radius * 2, rect.top(), radius * 2, radius * 2, 90, -90)
        path.lineTo(rect.right(), rect.bottom())
        path.closeSubpath()
        
        painter.fillPath(path, QBrush(bg_color))
        super().paintEvent(event)

    def on_close_button_clicked(self):
        """Determines whether to close a single widget or a whole container."""
        from .dock_container import DockContainer

        manager = getattr(self._top_level_widget, 'manager', None)
        if not manager:
            self._top_level_widget.close()
            return

        if isinstance(self._top_level_widget, DockContainer):
            manager.request_close_container(self._top_level_widget)
        else:
            manager.request_close_widget(self._top_level_widget)

    def mouseMoveEvent(self, event):
        if self.moving:
            if hasattr(self._top_level_widget, 'manager') and self._top_level_widget.manager:
                self._top_level_widget.manager.handle_live_move(self._top_level_widget, event)
            new_widget_global = event.globalPosition().toPoint() - self.offset
            self._top_level_widget.move(new_widget_global)
            return
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if (self.close_button.geometry().contains(event.pos()) or
                self.maximize_button.geometry().contains(event.pos()) or
                self.minimize_button.geometry().contains(event.pos())):
            super().mousePressEvent(event)
            return

        if event.button() == Qt.LeftButton:
            from .dock_container import DockContainer
            
            edge = None
            if isinstance(self._top_level_widget, DockContainer):
                pos = event.pos()
                margin = getattr(self._top_level_widget, 'resize_margin', 8)
                on_left = 0 <= pos.x() < margin
                on_right = self.width() - margin < pos.x() <= self.width()
                on_top = 0 <= pos.y() < margin

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
                    
                    if hasattr(self._top_level_widget, 'manager') and self._top_level_widget.manager:
                        self._top_level_widget.manager._set_state(DockingState.RESIZING_WINDOW)

            if not edge:
                if hasattr(self._top_level_widget, 'on_activation_request'):
                    self._top_level_widget.on_activation_request()
                if hasattr(self._top_level_widget, 'manager') and self._top_level_widget.manager:
                    if hasattr(self._top_level_widget.manager, 'destroy_all_overlays'):
                        self._top_level_widget.manager.destroy_all_overlays()

                self.moving = True
                self.offset = event.globalPosition().toPoint() - self._top_level_widget.pos()
                
                if hasattr(self._top_level_widget, 'manager') and self._top_level_widget.manager:
                    manager = self._top_level_widget.manager
                    manager.hit_test_cache.build_cache(manager.window_stack, manager.containers)
                    manager._set_state(DockingState.DRAGGING_WINDOW)
                    manager.hit_test_cache.set_drag_operation_state(True)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.moving:
                # First, clear the moving flag
                self.moving = False
                
                manager = getattr(self._top_level_widget, 'manager', None)
                if manager and hasattr(manager, 'last_dock_target') and manager.last_dock_target:
                    manager.finalize_dock_from_live_move(self._top_level_widget, manager.last_dock_target)
                
                if manager:
                    if hasattr(manager, 'last_dock_target'):
                        manager.last_dock_target = None
                    if hasattr(manager, 'destroy_all_overlays'):
                        manager.destroy_all_overlays()
                    if hasattr(manager, 'hit_test_cache'):
                        manager.hit_test_cache.set_drag_operation_state(False)
                    manager._set_state(DockingState.IDLE)
                
                if hasattr(self._top_level_widget, 'restore_normal_opacity'):
                    self._top_level_widget.restore_normal_opacity()
            if hasattr(self._top_level_widget, 'resizing') and self._top_level_widget.resizing:
                self._top_level_widget.resizing = False
                self._top_level_widget.resize_edge = None
                
                if hasattr(self._top_level_widget, 'manager') and self._top_level_widget.manager:
                    self._top_level_widget.manager._set_state(DockingState.IDLE)

    def _create_control_icon(self, icon_type: str, color=QColor("#303030")):
        """Creates cached window control icons for improved performance."""
        return IconCache.get_control_icon(icon_type, color.name(), 24)