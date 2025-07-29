from PySide6.QtGui import QPainter, QPen, QColor, QCursor
from PySide6.QtWidgets import QTabWidget, QTabBar, QApplication
from PySide6.QtCore import Qt, QPoint

from ..interaction.tab_drag_preview import TabDragPreview
from ..core.docking_state import DockingState


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
            if pos.x() < tab_rect.center().x():
                if tab_rect.contains(pos):
                    return i
            else:
                if tab_rect.contains(pos):
                    return i + 1

        if self.count() > 0:
            return self.count()

        return 0

    def paintEvent(self, event):
        """
        Overridden to draw the drop indicator line with enhanced bounds validation.
        """
        super().paintEvent(event)
        if self._drop_indicator_index != -1:
            painter = QPainter(self)
            
            bar_rect = self.rect()
            if bar_rect.width() <= 0 or bar_rect.height() <= 0:
                return
                
            painter.setClipRect(bar_rect)
            
            pen = QPen(QColor(0, 120, 215), 3)
            painter.setPen(pen)

            if self._drop_indicator_index < self.count():
                tab_rect = self.tabRect(self._drop_indicator_index)
                
                if (tab_rect.isValid() and 
                    tab_rect.left() >= 0 and 
                    tab_rect.left() <= bar_rect.width() and
                    tab_rect.intersects(bar_rect)):
                    
                    line_x = max(0, min(tab_rect.left(), bar_rect.width()))
                    line_top = max(0, 0)
                    line_bottom = min(self.height(), bar_rect.height())
                    
                    if line_bottom > line_top:
                        painter.drawLine(line_x, line_top, line_x, line_bottom)
            else:
                if self.count() > 0:
                    tab_rect = self.tabRect(self.count() - 1)
                    
                    if (tab_rect.isValid() and 
                        tab_rect.right() >= 0 and 
                        tab_rect.right() <= bar_rect.width() and
                        tab_rect.intersects(bar_rect)):
                        
                        line_x = max(0, min(tab_rect.right(), bar_rect.width()))
                        line_top = max(0, 0)
                        line_bottom = min(self.height(), bar_rect.height())
                        
                        if line_bottom > line_top:
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
        
        self.drag_preview = None
        self.dragged_tab_index = -1
        self.dragged_widget = None
        self.is_custom_dragging = False
        self.mouse_grabbed = False
        
        # Connect to currentChanged signal to force proper widget visibility
        self.currentChanged.connect(self._on_tab_changed)

    def set_manager(self, manager):
        self.manager = manager

    def start_tab_drag(self, index):
        """
        Starts a custom drag operation for a tab at the specified index.
        Uses a floating preview window instead of Qt's native drag system.
        """
        if not self.manager or self.is_custom_dragging:
            return

        content_to_remove = self.widget(index)

        from .dock_container import DockContainer

        container = self.parent()
        while container and not isinstance(container, DockContainer):
            container = container.parent()

        if container:
            owner_widget = next((w for w in container.contained_widgets if w.content_container is content_to_remove),
                                None)

            if owner_widget:
                self._start_custom_drag(index, owner_widget)

    def _start_custom_drag(self, tab_index, widget):
        """
        Initialize custom drag operation with floating preview.
        """
        self.is_custom_dragging = True
        self.dragged_tab_index = tab_index
        self.dragged_widget = widget
        
        self.setTabEnabled(tab_index, False)
        
        self.drag_preview = TabDragPreview(self, tab_index)
        
        self.manager._set_state(DockingState.DRAGGING_TAB)
        self.manager.destroy_all_overlays()
        self.manager.hit_test_cache.build_cache(self.manager.window_stack, self.manager.containers)
        
        # Find parent container to exclude from overlay targets
        parent_container = self.parent()
        while parent_container and not hasattr(parent_container, 'tearable_tab_widget'):
            parent_container = parent_container.parent()
        
        self.manager.hit_test_cache.set_drag_operation_state(True, parent_container)
        
        cursor_pos = QCursor.pos()
        self.drag_preview.show_preview(cursor_pos)
        
        self.grabMouse()
        self.mouse_grabbed = True

    def mouseMoveEvent(self, event):
        """
        Handle mouse movement for custom drag operations.
        """
        if self.is_custom_dragging and self.drag_preview:
            global_pos = self.mapToGlobal(event.pos())
            self.drag_preview.update_position(global_pos)
            
            if self.manager:
                self.manager._drag_source_id = self.dragged_widget.persistent_id
                self.manager.handle_qdrag_move(global_pos)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """
        Handle mouse release to complete or cancel custom drag operation.
        """
        if self.is_custom_dragging and event.button() == Qt.LeftButton:
            self._complete_custom_drag()
        else:
            super().mouseReleaseEvent(event)

    def _complete_custom_drag(self):
        """
        Complete the custom drag operation by docking or creating floating window.
        """
        if not self.is_custom_dragging or not self.dragged_widget:
            return
            
        try:
            cursor_pos = QCursor.pos()
            
            if self.mouse_grabbed:
                try:
                    self.releaseMouse()
                    self.mouse_grabbed = False
                except RuntimeError:
                    pass
            
            QApplication.processEvents()
            
            dock_target_info = None
            if self.manager and hasattr(self.manager, 'last_dock_target'):
                dock_target_info = self.manager.last_dock_target
            
            if dock_target_info:
                try:
                    target, location = dock_target_info
                    success = self.manager.dock_widget_from_drag(
                        self.dragged_widget.persistent_id, 
                        target, 
                        location
                    )
                    if not success:
                        self._create_floating_window_from_drag(cursor_pos)
                except Exception as e:
                    print(f"ERROR during dock operation: {e}")
                    self._create_floating_window_from_drag(cursor_pos)
            else:
                self._create_floating_window_from_drag(cursor_pos)
                
        except Exception as e:
            if self.mouse_grabbed:
                try:
                    self.releaseMouse()
                    self.mouse_grabbed = False
                except:
                    pass
        finally:
            self._cleanup_custom_drag()

    def _create_floating_window_from_drag(self, cursor_pos):
        """
        Create a floating window from the dragged tab.
        """
        if self.manager and self.dragged_widget:
            self.manager._create_floating_window_from_drag(self.dragged_widget, cursor_pos)

    def _cleanup_custom_drag(self):
        """
        Clean up after custom drag operation.
        """
        if self.dragged_tab_index >= 0:
            self.setTabEnabled(self.dragged_tab_index, True)
        
        if self.drag_preview:
            self.drag_preview.hide_preview()
            self.drag_preview.deleteLater()
            self.drag_preview = None
        
        if self.mouse_grabbed:
            try:
                self.releaseMouse()
                self.mouse_grabbed = False
            except RuntimeError:
                pass
        
        QApplication.processEvents()
        
        if self.manager:
            self.manager._set_state(DockingState.IDLE)
            self.manager.hit_test_cache.set_drag_operation_state(False)
            self.manager.destroy_all_overlays()
            self.manager._drag_source_id = None
        
        self.is_custom_dragging = False
        self.dragged_tab_index = -1
        self.dragged_widget = None
        self.mouse_grabbed = False

    def _on_tab_changed(self, index):
        """
        Handle tab changes to ensure proper widget visibility and prevent bleeding.
        """
        # Hide all widgets first
        for i in range(self.count()):
            widget = self.widget(i)
            if widget and i != index:
                widget.hide()
        
        # Show and update the current widget
        if index >= 0:
            current_widget = self.widget(index)
            if current_widget:
                current_widget.show()
                current_widget.raise_()
                current_widget.update()
        
        # Force repaint of the tab widget
        self.repaint()

    def resizeEvent(self, event):
        """
        Handle resize events to ensure proper tab content refresh.
        """
        super().resizeEvent(event)
        
        # Force visibility update for all tabs to prevent bleeding
        current_index = self.currentIndex()
        for i in range(self.count()):
            widget = self.widget(i)
            if widget:
                if i == current_index:
                    widget.show()
                    widget.raise_()
                    widget.update()
                else:
                    widget.hide()
        
        # Force repaint of the entire tab widget
        self.repaint()

    def keyPressEvent(self, event):
        """
        Handle ESC key to cancel drag operation.
        """
        if self.is_custom_dragging and event.key() == Qt.Key_Escape:
            self._cleanup_custom_drag()
        else:
            super().keyPressEvent(event)