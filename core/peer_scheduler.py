"""
Peer 评分与分片调度器
libtorrent 已内置 Rarest-First 和 EndGame，
本模块在其之上提供：
1. Peer 质量评分与主动剔除
2. 调度统计上报
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import libtorrent as lt

logger = logging.getLogger("fsmagnet.scheduler")


@dataclass
class PeerInfo:
    ip: str
    port: int
    first_seen: float = field(default_factory=time.monotonic)
    bytes_downloaded: int = 0
    request_failures: int = 0
    choke_events: int = 0
    speed_samples: List[float] = field(default_factory=list)

    def record_speed(self, bps: float):
        self.speed_samples.append(bps)
        if len(self.speed_samples) > 20:
            self.speed_samples.pop(0)

    @property
    def avg_speed(self) -> float:
        if not self.speed_samples:
            return 0.0
        return sum(self.speed_samples) / len(self.speed_samples)

    @property
    def score(self) -> float:
        """综合评分：速度 60% + 稳定性 40%"""
        speed_score = min(self.avg_speed / (512 * 1024), 10.0)
        stability = max(0.0, 10.0 - self.request_failures * 1.5 - self.choke_events * 0.5)
        return speed_score * 0.6 + stability * 0.4


class PeerScheduler:
    """
    配合 libtorrent 的 Peer 管理器
    通过 alert 回调更新 Peer 统计，定期剔除低质量 Peer
    """

    def __init__(self, handle: lt.torrent_handle):
        self.handle = handle
        self._peers: Dict[str, PeerInfo] = {}
        self._last_evict = time.monotonic()
        self.evict_interval = 30.0   # 每30秒评估一次

    def _peer_key(self, ip: str, port: int) -> str:
        return f"{ip}:{port}"

    def update_from_handle(self):
        """从 torrent_handle 拉取最新 Peer 列表并更新统计"""
        try:
            peers = self.handle.get_peer_info()
        except Exception:
            return

        current_keys = set()
        for p in peers:
            key = self._peer_key(p.ip[0], p.ip[1])
            current_keys.add(key)

            if key not in self._peers:
                self._peers[key] = PeerInfo(ip=p.ip[0], port=p.ip[1])

            info = self._peers[key]
            info.record_speed(p.down_speed)
            info.bytes_downloaded = p.total_download

            if p.flags & lt.peer_info.choked:
                info.choke_events += 1

        # 清理已断开的 Peer
        gone = set(self._peers.keys()) - current_keys
        for k in gone:
            del self._peers[k]

    def maybe_evict(self):
        """定期剔除低分 Peer，释放连接槽给更好的节点"""
        now = time.monotonic()
        if now - self._last_evict < self.evict_interval:
            return
        self._last_evict = now

        if len(self._peers) < 10:
            return

        sorted_peers = sorted(self._peers.values(), key=lambda p: p.score)
        evict_count = max(1, len(sorted_peers) // 10)  # 剔除最差 10%

        for peer in sorted_peers[:evict_count]:
            if peer.score < 1.0:  # 只剔除真正差的
                try:
                    self.handle.disconnect_peer(
                        (peer.ip, peer.port),
                        lt.error_code(lt.errors.banned_by_ip_filter)
                    )
                    logger.debug(f"剔除低质量 Peer: {peer.ip} score={peer.score:.2f}")
                except Exception:
                    pass

    def get_stats(self) -> dict:
        if not self._peers:
            return {"count": 0, "avg_score": 0, "top_speed_bps": 0}
        scores = [p.score for p in self._peers.values()]
        speeds = [p.avg_speed for p in self._peers.values()]
        return {
            "count": len(self._peers),
            "avg_score": round(sum(scores) / len(scores), 2),
            "top_speed_bps": int(max(speeds)),
        }