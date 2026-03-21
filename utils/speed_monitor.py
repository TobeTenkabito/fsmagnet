"""
实时速度监控：滑动窗口统计，支持全局和单任务
"""
import time
from collections import deque
from threading import Lock
from typing import Dict


class SpeedSampler:
    """
    单个速度采样器（滑动窗口，默认5秒）
    """
    def __init__(self, window_sec: float = 5.0):
        self.window = window_sec
        self._samples: deque = deque()   # (timestamp, bytes)
        self._lock = Lock()

    def record(self, byte_count: int):
        now = time.monotonic()
        with self._lock:
            self._samples.append((now, byte_count))
            self._evict(now)

    def _evict(self, now: float):
        cutoff = now - self.window
        while self._samples and self._samples[0][0] < cutoff:
            self._samples.popleft()

    @property
    def speed_bps(self) -> float:
        """当前速度 bytes/s"""
        now = time.monotonic()
        with self._lock:
            self._evict(now)
            if not self._samples:
                return 0.0
            total = sum(b for _, b in self._samples)
            elapsed = now - self._samples[0][0]
            return total / elapsed if elapsed > 0 else 0.0

    def reset(self):
        with self._lock:
            self._samples.clear()


class SpeedMonitor:
    """
    全局速度监控器
    管理所有任务的下载/上传速度采样
    """
    def __init__(self):
        self._dl: Dict[str, SpeedSampler] = {}   # task_id -> SpeedSampler
        self._ul: Dict[str, SpeedSampler] = {}
        self._lock = Lock()

    def _ensure(self, task_id: str):
        if task_id not in self._dl:
            self._dl[task_id] = SpeedSampler()
            self._ul[task_id] = SpeedSampler()

    def record_download(self, task_id: str, bytes_count: int):
        with self._lock:
            self._ensure(task_id)
        self._dl[task_id].record(bytes_count)

    def record_upload(self, task_id: str, bytes_count: int):
        with self._lock:
            self._ensure(task_id)
        self._ul[task_id].record(bytes_count)

    def get_download_speed(self, task_id: str) -> float:
        return self._dl.get(task_id, SpeedSampler()).speed_bps

    def get_upload_speed(self, task_id: str) -> float:
        return self._ul.get(task_id, SpeedSampler()).speed_bps

    def get_global_download_speed(self) -> float:
        return sum(s.speed_bps for s in self._dl.values())

    def get_global_upload_speed(self) -> float:
        return sum(s.speed_bps for s in self._ul.values())

    def remove_task(self, task_id: str):
        with self._lock:
            self._dl.pop(task_id, None)
            self._ul.pop(task_id, None)


# 全局单例
monitor = SpeedMonitor()