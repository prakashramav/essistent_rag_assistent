from collections import defaultdict
import threading
import time
from typing import Dict, List, Tuple

HISTOGRAM_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)


class PrometheusMetricsRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self._start_time = time.time()
        
        # Counters: (name, label_tuple) -> count
        self._counters: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], float] = defaultdict(float)
        
        # Gauges: (name, label_tuple) -> value
        self._gauges: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], float] = defaultdict(float)
        
        # Histograms: (name, label_tuple) -> {"buckets": {le: count}, "sum": float, "count": int}
        self._histograms: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], dict] = {}

    def inc_counter(self, name: str, amount: float = 1.0, **labels):
        label_key = tuple(sorted(labels.items()))
        with self._lock:
            self._counters[(name, label_key)] += amount

    def set_gauge(self, name: str, value: float, **labels):
        label_key = tuple(sorted(labels.items()))
        with self._lock:
            self._gauges[(name, label_key)] = value

    def observe_histogram(self, name: str, value: float, **labels):
        label_key = tuple(sorted(labels.items()))
        with self._lock:
            key = (name, label_key)
            if key not in self._histograms:
                self._histograms[key] = {
                    "buckets": {b: 0 for b in HISTOGRAM_BUCKETS},
                    "sum": 0.0,
                    "count": 0,
                }
            
            entry = self._histograms[key]
            entry["sum"] += value
            entry["count"] += 1
            for b in HISTOGRAM_BUCKETS:
                if value <= b:
                    entry["buckets"][b] += 1

    def format_prometheus(self) -> str:
        with self._lock:
            lines: List[str] = [
                "# HELP system_uptime_seconds Total application uptime in seconds",
                "# TYPE system_uptime_seconds gauge",
                f"system_uptime_seconds {round(time.time() - self._start_time, 2)}",
                "",
                "# HELP http_requests_total Total number of HTTP requests processed",
                "# TYPE http_requests_total counter",
            ]

            # Render Counters
            for (name, label_tuple), val in sorted(self._counters.items()):
                label_str = ",".join(f'{k}="{v}"' for k, v in label_tuple)
                lines.append(f"{name}{{{label_str}}} {val}")

            lines.extend([
                "",
                "# HELP http_request_duration_seconds HTTP request duration histogram in seconds",
                "# TYPE http_request_duration_seconds histogram",
            ])

            # Render Histograms
            for (name, label_tuple), entry in sorted(self._histograms.items()):
                base_labels = dict(label_tuple)
                # Bucket lines
                for b in HISTOGRAM_BUCKETS:
                    b_labels = {**base_labels, "le": str(b)}
                    label_str = ",".join(f'{k}="{v}"' for k, v in sorted(b_labels.items()))
                    lines.append(f"{name}_bucket{{{label_str}}} {entry['buckets'][b]}")
                
                # +Inf bucket
                inf_labels = {**base_labels, "le": "+Inf"}
                inf_str = ",".join(f'{k}="{v}"' for k, v in sorted(inf_labels.items()))
                lines.append(f"{name}_bucket{{{inf_str}}} {entry['count']}")
                # Sum and count
                label_str = ",".join(f'{k}="{v}"' for k, v in label_tuple)
                lbl_suffix = f"{{{label_str}}}" if label_str else ""
                lines.append(f"{name}_sum{lbl_suffix} {round(entry['sum'], 4)}")
                lines.append(f"{name}_count{lbl_suffix} {entry['count']}")

            # Render Gauges
            if self._gauges:
                lines.extend(["", "# TYPE gauges gauge"])
                for (name, label_tuple), val in sorted(self._gauges.items()):
                    label_str = ",".join(f'{k}="{v}"' for k, v in label_tuple)
                    lbl_suffix = f"{{{label_str}}}" if label_str else ""
                    lines.append(f"{name}{lbl_suffix} {val}")

            return "\n".join(lines) + "\n"


# Singleton instance
metrics = PrometheusMetricsRegistry()
