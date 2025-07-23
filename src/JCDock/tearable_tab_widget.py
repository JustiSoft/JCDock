# tearable_tab_widget.py
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtWidgets import QTabWidget, QTabBar, QApplication
from PySide6.QtCore import Qt, QPoint


class TearableTabBar(QTabBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMovable(True)
        self.setTabsClosable(True)
        self.drag_start_pos = None
        self._drop_indicator_index = -1
        self.setMouseTracking(True)

    def set_drop_indicator_index(self, index):
        """
        Sets the index for the drop indicator and triggers a repaint.
        An index of -1 hides the indicator.
        """
        if self._drop_indicator_index != index:
            self._drop_indicator_index = index
            self.update()

    def get_drop_index(self, pos: QPoint):
        """
        Calculates the desired insertion index based on the mouse position.
        Returns -1 if not over the tab bar.
        """
        if not self.rect().contains(pos):
            return -1

        for i in range(self.count()):
            tab_rect = self.tabRect(i)
            # Check the left half of the tab
            if pos.x() < tab_rect.center().x():
                if tab_rect.contains(pos):
                    return i
            # Check the right half of the tab
            else:
                if tab_rect.contains(pos):
                    return i + 1

        # If we are over the empty part of the tab bar, return the last index
        if self.count() > 0:
            return self.count()

        return 0  # If the bar is empty

    def paintEvent(self, event):
        """
        Overridden to draw the drop indicator line with enhanced bounds validation.
        """
        super().paintEvent(event)
        if self._drop_indicator_index != -1:
            painter = QPainter(self)
            
            # ENHANCED SAFETY: Validate tab bar geometry before painting
            bar_rect = self.rect()
            if bar_rect.width() <= 0 or bar_rect.height() <= 0:
                return  # Skip indicator painting for invalid geometry
                
            # Constrain painting to tab bar bounds
            painter.setClipRect(bar_rect)
            
            pen = QPen(QColor(0, 120, 215), 3)  # A distinct blue color
            painter.setPen(pen)

            if self._drop_indicator_index < self.count():
                tab_rect = self.tabRect(self._drop_indicator_index)
                
                # Validate tab rectangle before drawing
                if (tab_rect.isValid() and 
                    tab_rect.left() >= 0 and 
                    tab_rect.left() <= bar_rect.width() and
                    tab_rect.intersects(bar_rect)):
                    
                    # Constrain line coordinates to tab bar bounds
                    line_x = max(0, min(tab_rect.left(), bar_rect.width()))
                    line_top = max(0, 0)
                    line_bottom = min(self.height(), bar_rect.height())
                    
                    if line_bottom > line_top:  # Ensure positive line length
                        painter.drawLine(line_x, line_top, line_x, line_bottom)
            else:
                # If inserting at the very end, draw line at the right of the last tab
                if self.count() > 0:
                    tab_rect = self.tabRect(self.count() - 1)
                    
                    # Validate last tab rectangle before drawing
                    if (tab_rect.isValid() and 
                        tab_rect.right() >= 0 and 
                        tab_rect.right() <= bar_rect.width() and
                        tab_rect.intersects(bar_rect)):
                        
                        # Constrain line coordinates to tab bar bounds
                        line_x = max(0, min(tab_rect.right(), bar_rect.width()))
                        line_top = max(0, 0)
                        line_bottom = min(self.height(), bar_rect.height())
                        
                        if line_bottom > line_top:  # Ensure positive line length
                            painter.drawLine(line_x, line_top, line_x, line_bottom)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drag_start_pos and (event.buttons() & Qt.LeftButton):
            if (event.pos() - self.drag_start_pos).manhattanLength() > QApplication.startDragDistance() * 2:
                tear_threshold = 30
                if (event.pos().y() < -tear_threshold or
                        event.pos().y() > self.height() + tear_threshold):

                    tab_index = self.tabAt(self.drag_start_pos)
                    if tab_index != -1:
                        self.parentWidget().start_tab_drag(tab_index)
                        self.drag_start_pos = None
                        return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.drag_start_pos = None
        super().mouseReleaseEvent(event)


class TearableTabWidget(QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tab_bar = TearableTabBar(self)
        self.setTabBar(self.tab_bar)
        self.manager = None

    def set_manager(self, manager):
        self.manager = manager

    def start_tab_drag(self, index):
        """
        Starts a Qt-native drag operation for a tab at the specified index.
        """
        if not self.manager:
            return

        # 1. Identify the DockPanel associated with this tab index
        content_to_remove = self.widget(index)

        # We need to find the DockContainer that owns this tab widget to look up the widget
        from .dock_container import DockContainer

        container = self.parent()
        while container and not isinstance(container, DockContainer):
            container = container.parent()

        if container:
            owner_widget = next((w for w in container.contained_widgets if w.content_container is content_to_remove),
                                None)

            if owner_widget:
                # 2. Tell the manager to start the Qt drag operation
                self.manager.start_tab_drag_operation(owner_widget.persistent_id)