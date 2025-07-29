import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class PerformanceMetric:
    """
    Represents a single performance measurement.
    """
    name: str
    start_time: float
    end_time: Optional[float] = None
    duration: Optional[float] = None
    metadata: Dict = field(default_factory=dict)
    
    def finish(self):
        """Mark the metric as finished and calculate duration."""
        if self.end_time is None:
            self.end_time = time.perf_counter()
            self.duration = self.end_time - self.start_time


class PerformanceMonitor:
    """
    Performance monitoring system for drag operations and other JCDock operations.
    Tracks timing, counts, and provides statistics for performance optimization.
    """
    
    def __init__(self):
        self._metrics: List[PerformanceMetric] = []
        self._active_metrics: Dict[str, PerformanceMetric] = {}
        self._counters: Dict[str, int] = defaultdict(int)
        self._enabled = False
    
    def enable(self):
        """Enable performance monitoring."""
        self._enabled = True
    
    def disable(self):
        """Disable performance monitoring."""
        self._enabled = False
    
    def start_timing(self, name: str, metadata: Dict = None) -> str:
        """
        Start timing a performance metric.
        
        Args:
            name: Name of the metric
            metadata: Optional metadata to store with the metric
            
        Returns:
            str: Unique identifier for this timing session
        """
        if not self._enabled:
            return ""
            
        metric_id = f"{name}_{len(self._metrics)}"
        metric = PerformanceMetric(
            name=name,
            start_time=time.perf_counter(),
            metadata=metadata or {}
        )
        
        self._active_metrics[metric_id] = metric
        return metric_id
    
    def end_timing(self, metric_id: str):
        """
        End timing for a performance metric.
        
        Args:
            metric_id: Identifier returned by start_timing
        """
        if not self._enabled or metric_id not in self._active_metrics:
            return
            
        metric = self._active_metrics[metric_id]
        metric.finish()
        
        self._metrics.append(metric)
        del self._active_metrics[metric_id]
    
    def increment_counter(self, name: str, amount: int = 1):
        """
        Increment a performance counter.
        
        Args:
            name: Counter name
            amount: Amount to increment by
        """
        if self._enabled:
            self._counters[name] += amount
    
    def get_drag_performance_stats(self) -> Dict:
        """
        Get performance statistics specific to drag operations.
        
        Returns:
            dict: Drag performance statistics
        """
        if not self._enabled:
            return {}
            
        drag_metrics = [m for m in self._metrics if 'drag' in m.name.lower()]
        overlay_metrics = [m for m in self._metrics if 'overlay' in m.name.lower()]
        
        stats = {
            'drag_operations': len(drag_metrics),
            'overlay_operations': len(overlay_metrics),
            'total_drag_time': sum(m.duration or 0 for m in drag_metrics),
            'total_overlay_time': sum(m.duration or 0 for m in overlay_metrics),
            'average_drag_time': 0,
            'average_overlay_time': 0,
        }
        
        if drag_metrics:
            stats['average_drag_time'] = stats['total_drag_time'] / len(drag_metrics)
        if overlay_metrics:
            stats['average_overlay_time'] = stats['total_overlay_time'] / len(overlay_metrics)
            
        return stats
    
    def get_cache_performance_stats(self) -> Dict:
        """
        Get performance statistics for caching operations.
        
        Returns:
            dict: Cache performance statistics
        """
        return {
            'cache_hits': self._counters.get('cache_hits', 0),
            'cache_misses': self._counters.get('cache_misses', 0),
            'cache_invalidations': self._counters.get('cache_invalidations', 0),
            'geometry_cache_updates': self._counters.get('geometry_cache_updates', 0),
        }
    
    def get_overall_stats(self) -> Dict:
        """
        Get overall performance statistics.
        
        Returns:
            dict: Complete performance statistics
        """
        if not self._enabled:
            return {'monitoring_enabled': False}
            
        completed_metrics = [m for m in self._metrics if m.duration is not None]
        
        stats = {
            'monitoring_enabled': True,
            'total_metrics': len(self._metrics),
            'completed_metrics': len(completed_metrics),
            'active_metrics': len(self._active_metrics),
            'total_time': sum(m.duration for m in completed_metrics),
            'counters': dict(self._counters),
            'drag_stats': self.get_drag_performance_stats(),
            'cache_stats': self.get_cache_performance_stats(),
        }
        
        if completed_metrics:
            stats['average_operation_time'] = stats['total_time'] / len(completed_metrics)
            stats['slowest_operation'] = max(completed_metrics, key=lambda m: m.duration or 0).name
            stats['fastest_operation'] = min(completed_metrics, key=lambda m: m.duration or 0).name
        
        return stats
    
    def clear_metrics(self):
        """Clear all collected metrics and counters."""
        self._metrics.clear()
        self._active_metrics.clear()
        self._counters.clear()
    
    def context_timer(self, name: str, metadata: Dict = None):
        """
        Context manager for timing operations.
        
        Args:
            name: Name of the metric
            metadata: Optional metadata
            
        Example:
            with monitor.context_timer('drag_operation'):
                # perform drag operation
                pass
        """
        return PerformanceContext(self, name, metadata)


class PerformanceContext:
    """Context manager for performance timing."""
    
    def __init__(self, monitor: PerformanceMonitor, name: str, metadata: Dict = None):
        self.monitor = monitor
        self.name = name
        self.metadata = metadata
        self.metric_id = None
    
    def __enter__(self):
        self.metric_id = self.monitor.start_timing(self.name, self.metadata)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.metric_id:
            self.monitor.end_timing(self.metric_id)