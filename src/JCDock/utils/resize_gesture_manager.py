from typing import Optional, Dict, Any
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PySide6.QtCore import QTimer, QObject, Signal, QEvent, QRect, QPoint
from PySide6.QtGui import QPixmap, QPainter
from PySide6.QtCore import Qt


class ResizeGestureManager(QObject):
    """
    Universal resize gesture detection and smooth resize system that works for
    both floating containers and main application windows.
    
    Uses static snapshots during resize operations to eliminate layout recalculation
    overhead and provide smooth visual feedback.
    """
    
    resize_gesture_started = Signal(QWidget)
    resize_gesture_finished = Signal(QWidget)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Track widgets currently being resized
        self._widgets_being_resized: Dict[QWidget, Dict[str, Any]] = {}
        
        # Gesture detection timer delay (ms)
        self._gesture_timeout = 150  # 150ms after last resize event
        
    def register_widget(self, widget: QWidget):
        """
        Register a widget to use the smooth resize system.
        
        Args:
            widget: Widget to monitor for resize gestures
        """
        if widget in self._widgets_being_resized:
            return  # Already registered
            
        # Install event filter to catch resize events
        widget.installEventFilter(self)
        
    def start_manual_gesture(self, widget: QWidget, resize_edge: str = None, start_pos: QPoint = None):
        """
        Manually start a resize gesture for a widget.
        This is called when the user starts dragging a resize edge.
        
        Args:
            widget: Widget to start gesture for
            resize_edge: Edge being resized (e.g., "top", "left", etc.)
            start_pos: Starting mouse position
        """
        if widget not in self._widgets_being_resized:
            self._start_resize_gesture(widget)
            
            # Store manual resize information
            if widget in self._widgets_being_resized:
                resize_state = self._widgets_being_resized[widget]
                resize_state['manual_resize'] = True
                resize_state['resize_edge'] = resize_edge
                resize_state['start_pos'] = start_pos
                resize_state['start_geom'] = widget.geometry()
                
                # Install mouse tracking for manual resize
                widget.grabMouse()
                widget.installEventFilter(self)
        
    def unregister_widget(self, widget: QWidget):
        """
        Unregister a widget from the smooth resize system.
        
        Args:
            widget: Widget to stop monitoring
        """
        if widget in self._widgets_being_resized:
            self._cleanup_deleted_widget(widget)
            
        try:
            widget.removeEventFilter(self)
        except RuntimeError:
            # Widget was already deleted
            pass
        
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """
        Event filter to detect resize events and manage gesture detection.
        Also handles mouse events for manual resize operations.
        
        Args:
            watched: Widget being watched
            event: Event being processed
            
        Returns:
            bool: True if event was handled, False to pass through
        """
        if not isinstance(watched, QWidget):
            return False
            
        if event.type() == QEvent.Type.Resize:
            self._handle_resize_event(watched, event)
            return False  # Pass resize events through
            
        # Handle mouse events for manual resize
        if watched in self._widgets_being_resized:
            resize_state = self._widgets_being_resized[watched]
            if resize_state.get('manual_resize', False):
                if event.type() == QEvent.Type.MouseMove:
                    self._handle_manual_resize_move(watched, event)
                    return True  # Consume mouse move events during manual resize
                elif event.type() == QEvent.Type.MouseButtonRelease:
                    self._finish_manual_resize(watched)
                    return True  # Consume mouse release events
            
        return False
        
    def _handle_resize_event(self, widget: QWidget, event):
        """
        Handle resize event for a widget - start or continue gesture detection.
        
        Args:
            widget: Widget being resized
            event: Resize event
        """
        if widget not in self._widgets_being_resized:
            # First resize event - start gesture detection
            self._start_resize_gesture(widget)
        else:
            # Continuing resize gesture - restart timer
            self._restart_gesture_timer(widget)
            
    def _start_resize_gesture(self, widget: QWidget):
        """
        Start resize gesture detection for a widget.
        
        Args:
            widget: Widget starting resize gesture
        """
        # Capture static snapshot of current state
        snapshot = self._capture_widget_snapshot(widget)
        if not snapshot:
            return  # Failed to capture snapshot
            
        # Create snapshot display label
        snapshot_label = self._create_snapshot_label(widget, snapshot)
        
        # Set up gesture timer
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._finish_resize_gesture(widget))
        timer.start(self._gesture_timeout)
        
        # Store resize state
        self._widgets_being_resized[widget] = {
            'snapshot': snapshot,
            'snapshot_label': snapshot_label,
            'timer': timer,
            'original_central_widget': None,  # Will be set during UI swap
            'is_main_window': hasattr(widget, 'setCentralWidget')
        }
        
        # Swap UI to show snapshot
        self._swap_to_snapshot_ui(widget)
        
        # Emit signal
        self.resize_gesture_started.emit(widget)
        
    def _restart_gesture_timer(self, widget: QWidget):
        """
        Restart the gesture detection timer for ongoing resize.
        
        Args:
            widget: Widget with ongoing resize gesture
        """
        if widget not in self._widgets_being_resized:
            return
            
        timer = self._widgets_being_resized[widget]['timer']
        timer.stop()
        timer.start(self._gesture_timeout)
        
    def _capture_widget_snapshot(self, widget: QWidget) -> Optional[QPixmap]:
        """
        Capture a static snapshot of the widget's current appearance.
        
        Args:
            widget: Widget to capture
            
        Returns:
            QPixmap: Snapshot image, or None if capture failed
        """
        try:
            if hasattr(widget, 'centralWidget') and widget.centralWidget():
                # For main windows, capture the central widget
                return widget.centralWidget().grab()
            else:
                # For regular widgets, capture the whole widget
                return widget.grab()
        except Exception as e:
            print(f"Failed to capture widget snapshot: {e}")
            return None
            
    def _create_snapshot_label(self, widget: QWidget, snapshot: QPixmap) -> QLabel:
        """
        Create a QLabel to display the snapshot with proper scaling.
        
        Args:
            widget: Widget being snapshotted
            snapshot: Snapshot pixmap
            
        Returns:
            QLabel: Label configured to display and scale the snapshot
        """
        label = QLabel()
        label.setPixmap(snapshot)
        label.setScaledContents(True)  # Allow pixmap to scale with label
        label.setMinimumSize(1, 1)  # Allow shrinking
        
        # Match the original widget's size policy if possible
        if hasattr(widget, 'sizePolicy'):
            label.setSizePolicy(widget.sizePolicy())
            
        return label
        
    def _swap_to_snapshot_ui(self, widget: QWidget):
        """
        Swap the widget's UI to show the static snapshot instead of live content.
        
        Args:
            widget: Widget to swap UI for
        """
        resize_state = self._widgets_being_resized[widget]
        snapshot_label = resize_state['snapshot_label']
        
        if resize_state['is_main_window']:
            # For main windows, replace central widget
            original_central = widget.centralWidget()
            resize_state['original_central_widget'] = original_central
            
            if original_central:
                original_central.hide()
                widget.setCentralWidget(snapshot_label)
        else:
            # For containers, hide content and show snapshot
            # This is more complex - we need to temporarily replace the layout
            layout = widget.layout()
            if layout:
                # Hide all child widgets
                resize_state['hidden_children'] = []
                for i in range(layout.count()):
                    item = layout.itemAt(i)
                    if item and item.widget():
                        child = item.widget()
                        child.hide()
                        resize_state['hidden_children'].append(child)
                
                # Add snapshot label to layout
                layout.addWidget(snapshot_label)
                
    def _finish_resize_gesture(self, widget: QWidget):
        """
        Finish resize gesture and restore live UI.
        
        Args:
            widget: Widget finishing resize gesture
        """
        if widget not in self._widgets_being_resized:
            return
            
        # Check if widget is still valid
        try:
            if widget.isVisible is None:  # Widget has been deleted
                self._cleanup_deleted_widget(widget)
                return
        except RuntimeError:
            # Widget C++ object has been deleted
            self._cleanup_deleted_widget(widget)
            return
            
        resize_state = self._widgets_being_resized[widget]
        
        # Stop and cleanup timer
        timer = resize_state['timer']
        timer.stop()
        timer.deleteLater()
        
        # Restore original UI
        self._restore_original_ui(widget, resize_state)
        
        # Cleanup resize state
        del self._widgets_being_resized[widget]
        
        # Emit signal
        self.resize_gesture_finished.emit(widget)
        
    def _cleanup_deleted_widget(self, widget: QWidget):
        """
        Clean up state for a widget that has been deleted.
        
        Args:
            widget: Widget that was deleted
        """
        if widget not in self._widgets_being_resized:
            return
            
        resize_state = self._widgets_being_resized[widget]
        
        # Stop and cleanup timer
        timer = resize_state.get('timer')
        if timer:
            timer.stop()
            timer.deleteLater()
            
        # Cleanup snapshot label if it exists
        snapshot_label = resize_state.get('snapshot_label')
        if snapshot_label:
            try:
                snapshot_label.deleteLater()
            except RuntimeError:
                pass  # Already deleted
                
        # Remove from tracking
        del self._widgets_being_resized[widget]
        
    def _restore_original_ui(self, widget: QWidget, resize_state: Dict[str, Any]):
        """
        Restore the original live UI after resize gesture completes.
        
        Args:
            widget: Widget to restore UI for
            resize_state: Stored resize state information
        """
        snapshot_label = resize_state.get('snapshot_label')
        
        try:
            if resize_state.get('is_main_window', False):
                # Restore main window central widget
                original_central = resize_state.get('original_central_widget')
                if original_central:
                    widget.setCentralWidget(original_central)
                    original_central.show()
                    
                    # Trigger final layout update
                    original_central.updateGeometry()
            else:
                # Restore container layout
                layout = widget.layout()
                if layout and snapshot_label:
                    # Remove snapshot label
                    layout.removeWidget(snapshot_label)
                    
                    # Show hidden children
                    hidden_children = resize_state.get('hidden_children', [])
                    for child in hidden_children:
                        try:
                            child.show()
                        except RuntimeError:
                            pass  # Child was deleted
                        
                    # Trigger final layout update
                    widget.updateGeometry()
                    
            # Cleanup snapshot
            if snapshot_label:
                try:
                    snapshot_label.deleteLater()
                except RuntimeError:
                    pass  # Already deleted
                    
        except RuntimeError:
            # Widget was deleted during restoration
            pass
        
    def is_widget_resizing(self, widget: QWidget) -> bool:
        """
        Check if a widget is currently in a resize gesture.
        
        Args:
            widget: Widget to check
            
        Returns:
            bool: True if widget is currently being resized
        """
        return widget in self._widgets_being_resized
        
    def set_gesture_timeout(self, timeout_ms: int):
        """
        Set the timeout for gesture detection.
        
        Args:
            timeout_ms: Timeout in milliseconds
        """
        self._gesture_timeout = max(50, min(timeout_ms, 1000))  # Clamp between 50-1000ms
        
    def get_gesture_timeout(self) -> int:
        """Get current gesture timeout in milliseconds."""
        return self._gesture_timeout
        
    def _handle_manual_resize_move(self, widget: QWidget, event):
        """
        Handle mouse move during manual resize operation.
        
        Args:
            widget: Widget being resized
            event: Mouse move event
        """
        if widget not in self._widgets_being_resized:
            return
            
        resize_state = self._widgets_being_resized[widget]
        if not resize_state.get('manual_resize', False):
            return
            
        # Calculate new geometry based on mouse movement
        current_pos = event.globalPosition().toPoint()
        start_pos = resize_state.get('start_pos')
        start_geom = resize_state.get('start_geom')
        resize_edge = resize_state.get('resize_edge')
        
        if not all([start_pos, start_geom, resize_edge]):
            return
            
        delta = current_pos - start_pos
        new_geom = QRect(start_geom)
        
        # Apply resize based on edge
        if "right" in resize_edge:
            new_width = start_geom.width() + delta.x()
            new_geom.setWidth(max(new_width, widget.minimumWidth()))
        if "left" in resize_edge:
            new_width = start_geom.width() - delta.x()
            new_width = max(new_width, widget.minimumWidth())
            new_geom.setX(start_geom.right() - new_width)
            new_geom.setWidth(new_width)
        if "bottom" in resize_edge:
            new_height = start_geom.height() + delta.y()
            new_geom.setHeight(max(new_height, widget.minimumHeight()))
        if "top" in resize_edge:
            new_height = start_geom.height() - delta.y()
            new_height = max(new_height, widget.minimumHeight())
            new_geom.setY(start_geom.bottom() - new_height)
            new_geom.setHeight(new_height)
            
        # Apply the new geometry to the widget directly
        # This will trigger resize events which will be captured normally
        widget.setGeometry(new_geom)
        
    def _finish_manual_resize(self, widget: QWidget):
        """
        Finish manual resize operation.
        
        Args:
            widget: Widget finishing manual resize
        """
        if widget not in self._widgets_being_resized:
            return
            
        try:
            widget.releaseMouse()
        except:
            pass
            
        # Let the normal gesture completion handle the rest
        self._finish_resize_gesture(widget)