"""
DHT 加速模块
- 维护高质量 Bootstrap 节点列表
- 定期保存/恢复 DHT 路由表（加速冷启动）
- 监控 DHT 节点数量
"""
import os
import pickle
import logging
import asyncio
from pathlib import Path
import libtorrent as lt

logger = logging.getLogger("fsmagnet.dht")

DHT_STATE_FILE = Path("./fsmagnet_dht_state.dat")

# 高质量公共 Bootstrap 节点
BOOTSTRAP_NODES = [
    ("router.bittorrent.com",  6881),
    ("router.utorrent.com",    6881),
    ("dht.transmissionbt.com", 6881),
    ("dht.aelitis.com",        6881),
    ("router.bitcomet.com",    6881),
    ("dht.libtorrent.org",     25401),
]


class DHTManager:
    def __init__(self, session: lt.session):
        self.session = session
        self._running = False

    def load_state(self) -> bool:
        """从磁盘恢复上次的 DHT 路由表，大幅加速冷启动"""
        if not DHT_STATE_FILE.exists():
            return False
        try:
            with open(DHT_STATE_FILE, "rb") as f:
                state = pickle.load(f)
            entry = lt.bdecode(state)
            self.session.load_state(entry)
            logger.info("✅ DHT 路由表已从磁盘恢复")
            return True
        except Exception as e:
            logger.warning(f"DHT 状态恢复失败: {e}")
            return False

    def save_state(self):
        """保存 DHT 路由表到磁盘"""
        try:
            entry = self.session.save_state()
            data = lt.bencode(entry)
            with open(DHT_STATE_FILE, "wb") as f:
                f.write(data)
            logger.info("DHT 路由表已保存")
        except Exception as e:
            logger.warning(f"DHT 状态保存失败: {e}")

    def add_bootstrap_nodes(self):
        """手动添加 Bootstrap 节点"""
        for host, port in BOOTSTRAP_NODES:
            try:
                self.session.add_dht_node((host, port))
            except Exception:
                pass
        logger.info(f"已添加 {len(BOOTSTRAP_NODES)} 个 DHT Bootstrap 节点")

    def get_node_count(self) -> int:
        """获取当前 DHT 节点数"""
        try:
            status = self.session.status()
            return status.dht_nodes
        except Exception:
            return 0

    async def wait_until_ready(self, min_nodes: int = 20, timeout: float = 30.0) -> bool:
        """
        等待 DHT 网络就绪（节点数达到阈值）
        """
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            count = self.get_node_count()
            if count >= min_nodes:
                logger.info(f"✅ DHT 就绪，当前节点数: {count}")
                return True
            await asyncio.sleep(0.5)
        logger.warning(f"DHT 等待超时，当前节点数: {self.get_node_count()}")
        return False

    async def run_periodic_save(self, interval: float = 300.0):
        """每5分钟保存一次 DHT 状态"""
        self._running = True
        while self._running:
            await asyncio.sleep(interval)
            self.save_state()

    def stop(self):
        self._running = False
        self.save_state()