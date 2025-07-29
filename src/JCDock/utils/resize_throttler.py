from typing import Optional, Callable
from PySide6.QtCore import QTimer, QRect
from PySide6.QtWidgets import QWidget


class ResizeThrottler:
    """
    Throttles resize operations to improve performance during rapid mouse movements.
    Batches multiple resize requests into single geometry updates at ~60fps (16ms intervals).
    """
    
    def __init__(self, widget: QWidget, interval_ms: int = 16):
        """
        Initialize the resize throttler.
        
        Args:
            widget: Widget being resized
            interval_ms: Throttling interval in milliseconds (default 16ms ~60fps)
        """
        self.widget = widget
        self.interval_ms = interval_ms
        self._timer: Optional[QTimer] = None
        self._pending_geometry: Optional[QRect] = None
        self._performance_monitor = None
        self._last_geometry: Optional[QRect] = None
        self._geometry_callback: Optional[Callable] = None
        
    def set_performance_monitor(self, monitor):
        """Set reference to performance monitor for throttling statistics."""
        self._performance_monitor = monitor
        
    def set_geometry_callback(self, callback: Callable[[QRect], None]):
        """
        Set callback function to execute when geometry is actually applied.
        
        Args:
            callback: Function to call with the final geometry
        """
        self._geometry_callback = callback
    
    def request_resize(self, new_geometry: QRect):
        """
        Request a resize operation. This will be throttled and applied later.
        
        Args:
            new_geometry: Requested geometry for the widget
        """
        if self._performance_monitor:
            self._performance_monitor.increment_counter('resize_requests')
        
        # Store the most recent geometry request
        self._pending_geometry = QRect(new_geometry)
        
        # Start or restart the timer
        if not self._timer:
            self._timer = QTimer()
            self._timer.setSingleShot(True)
            self._timer.timeout.connect(self._apply_pending_resize)
            
        if self._timer.isActive():
            # Timer is already running, just update the pending geometry
            if self._performance_monitor:
                self._performance_monitor.increment_counter('resize_requests_batched')
        else:
            # Start the timer
            self._timer.start(self.interval_ms)
            if self._performance_monitor:
                self._performance_monitor.increment_counter('resize_timers_started')
    
    def _apply_pending_resize(self):
        """Apply the pending resize operation (called by timer)."""
        if not self._pending_geometry:
            return
            
        geometry_to_apply = QRect(self._pending_geometry)
        self._pending_geometry = None
        
        # Check if geometry actually changed to avoid redundant updates
        if self._last_geometry and geometry_to_apply == self._last_geometry:
            if self._performance_monitor:
                self._performance_monitor.increment_counter('resize_skipped_identical')
            return
            
        self._last_geometry = QRect(geometry_to_apply)
        
        # Apply the geometry
        if self._performance_monitor:
            timer_id = self._performance_monitor.start_timing('throttled_resize_application')
        
        try:
            self.widget.setGeometry(geometry_to_apply)
            
            # Call custom callback if provided
            if self._geometry_callback:
                self._geometry_callback(geometry_to_apply)
                
            if self._performance_monitor:
                self._performance_monitor.increment_counter('resize_applications')
                
        finally:
            if self._performance_monitor and 'timer_id' in locals():
                self._performance_monitor.end_timing(timer_id)
    
    def flush_pending(self):
        """
        Immediately apply any pending resize operation without waiting for timer.
        Useful when resize operation is finishing.
        """
        if self._timer and self._timer.isActive():
            self._timer.stop()
            
        if self._pending_geometry:
            self._apply_pending_resize()
            
        if self._performance_monitor:
            self._performance_monitor.increment_counter('resize_flushes')
    
    def has_pending_resize(self) -> bool:
        """Check if there's a pending resize operation."""
        return self._pending_geometry is not None
    
    def cancel_pending(self):
        """Cancel any pending resize operation."""
        if self._timer and self._timer.isActive():
            self._timer.stop()
            
        self._pending_geometry = None
        
        if self._performance_monitor:
            self._performance_monitor.increment_counter('resize_cancellations')
    
    def cleanup(self):
        """Clean up timer and resources."""
        if self._timer:
            if self._timer.isActive():
                self._timer.stop()
            self._timer.deleteLater()
            self._timer = None
            
        self._pending_geometry = None
        self._last_geometry = None
        self._geometry_callback = None
        
        if self._performance_monitor:
            self._performance_monitor.increment_counter('throttler_cleanups')
    
    def get_throttling_stats(self) -> dict:
        """Get statistics about throttling performance."""
        return {
            'interval_ms': self.interval_ms,
            'has_pending': self.has_pending_resize(),
            'timer_active': self._timer.isActive() if self._timer else False,
            'has_callback': self._geometry_callback is not None
        }