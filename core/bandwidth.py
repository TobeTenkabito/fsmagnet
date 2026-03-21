"""
自适应带宽控制器
每隔 N 秒评估全局下载速度趋势，动态调整：
1. 全局连接数上限
2. 每个任务的连接数
3. 上传限速（保证下载带宽）
"""
import asyncio
import logging
import time
from collections import deque
from typing import TYPE_CHECKING

import libtorrent as lt

if TYPE_CHECKING:
    from core.session import TurboSession

logger = logging.getLogger("fsmagnet.bandwidth")


class BandwidthController:
    def __init__(self, session: lt.session, check_interval: float = 5.0):
        self.session = session
        self.check_interval = check_interval

        self._speed_history: deque = deque(maxlen=12)  # 最近60秒
        self._current_conn_limit: int = 500
        self._running = False

    async def run(self):
        self._running = True
        logger.info("带宽控制器启动")
        while self._running:
            await asyncio.sleep(self.check_interval)
            self._tick()

    def _tick(self):
        try:
            status = self.session.status()
            dl_speed = status.payload_download_rate   # bytes/s
            self._speed_history.append((time.monotonic(), dl_speed))
            self._adjust(dl_speed)
        except Exception as e:
            logger.warning(f"带宽控制 tick 异常: {e}")

    def _adjust(self, current_speed: float):
        """
        根据速度趋势调整连接数
        - 速度持续下降 → 增加连接数（尝试找更多 Peer）
        - 速度稳定且连接数多 → 适当减少（节省资源）
        """
        if len(self._speed_history) < 3:
            return

        recent = [s for _, s in list(self._speed_history)[-3:]]
        trend = recent[-1] - recent[0]   # 正=上升，负=下降

        settings = self.session.get_settings()
        conn_limit = settings.get("connections_limit", 500)

        if trend < -50 * 1024 and conn_limit < 2000:
            # 速度下降超过 50KB/s → 增加10%连接数
            new_limit = min(2000, int(conn_limit * 1.1))
            self.session.apply_settings({"connections_limit": new_limit})
            logger.debug(f"速度下降，连接数 {conn_limit} → {new_limit}")

        elif trend > 100 * 1024 and conn_limit > 100:
            # 速度上升且连接充足 → 维持现状，不做调整
            pass

    def stop(self):
        self._running = False

    def get_trend_summary(self) -> dict:
        if len(self._speed_history) < 2:
            return {"trend": "unknown", "samples": 0}
        speeds = [s for _, s in self._speed_history]
        trend = speeds[-1] - speeds[0]
        return {
            "trend": "up" if trend > 0 else "down" if trend < 0 else "stable",
            "current_bps": int(speeds[-1]),
            "samples": len(speeds),
        }