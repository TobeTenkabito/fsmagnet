"""
DHT 加速模块
"""
import os
import socket
import asyncio
import logging
from pathlib import Path
import libtorrent as lt

logger = logging.getLogger("fsmagnet.dht")


from config import APP_DATA_DIR
DHT_STATE_FILE = APP_DATA_DIR / "fsmagnet_dht_state.dat"

BOOTSTRAP_NODES = [
    ("67.215.246.10",   6881),
    ("82.221.103.244",  6881),
    ("87.98.162.88",    6881),
    ("95.211.198.146",  25401),
    ("212.129.33.59",   6881),
    ("91.121.59.153",   6881),
    ("205.185.116.116", 6881),
    ("173.254.204.71",  6881),
    ("194.165.16.77",   6881),
    ("51.15.43.212",    6881),
    ("185.71.67.60",    6881),
    ("185.71.67.61",    6881),
    ("108.165.168.163", 6881),
    ("45.55.59.57",     6881),
    ("104.131.98.232",  6881),
]


class DHTManager:
    def __init__(self, session: lt.session):
        self.session = session
        self._running = False

    def ensure_dht_started(self):
        """确保 DHT 已启动"""
        try:
            # ✅ 修复：新版 libtorrent 通过 apply_settings 控制 DHT
            # start_dht() 已废弃，只需确保 enable_dht=True 即可
            current = self.session.get_settings()
            if not current.get("enable_dht", False):
                logger.warning("enable_dht 为 False，强制开启")
                self.session.apply_settings({"enable_dht": True})
            logger.info("✅ DHT 设置已确认开启")
        except Exception as e:
            logger.warning(f"DHT 设置检查失败: {e}")

    def save_state(self):
        try:
            entry = self.session.save_state()
            data = lt.bencode(entry)
            with open(DHT_STATE_FILE, "wb") as f:
                f.write(data)
            logger.debug("DHT 路由表已保存")
        except Exception as e:
            logger.warning(f"DHT 状态保存失败: {e}")

    def load_state(self) -> bool:
        if not DHT_STATE_FILE.exists():
            logger.info("无 DHT 历史状态，将从头建立")
            return False
        try:
            with open(DHT_STATE_FILE, "rb") as f:
                data = f.read()
            entry = lt.bdecode(data)
            self.session.load_state(entry)
            logger.info("✅ DHT 路由表已从磁盘恢复")
            return True
        except Exception as e:
            logger.warning(f"DHT 状态恢复失败: {e}")
            return False

    def add_bootstrap_nodes(self):
        success = 0
        for host, port in BOOTSTRAP_NODES:
            try:
                self.session.add_dht_node((host, port))
                success += 1
            except Exception as e:
                logger.warning(f"Bootstrap 节点添加失败: {host} → {e}")
        logger.info(f"✅ 成功添加 {success}/{len(BOOTSTRAP_NODES)} 个 Bootstrap 节点")

    async def add_bootstrap_nodes_async(self):
        """异步版本：DNS 解析不阻塞事件循环"""
        loop = asyncio.get_event_loop()
        success = 0
        for host, port in BOOTSTRAP_NODES:
            try:
                ip = await loop.run_in_executor(None, socket.gethostbyname, host)
                self.session.add_dht_node((ip, port))
                logger.info(f"DHT bootstrap: {host} → {ip}:{port}")
                success += 1
            except Exception as e:
                logger.warning(f"DNS 解析失败: {host} → {e}")
        logger.info(f"✅ 异步添加 {success}/{len(BOOTSTRAP_NODES)} 个 Bootstrap 节点")

    def get_node_count(self) -> int:
        try:
            return self.session.status().dht_nodes
        except Exception:
            return 0

    async def wait_until_ready(self, min_nodes: int = 5, timeout: float = 30.0) -> bool:
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            count = self.get_node_count()
            logger.debug(f"DHT 节点数: {count}")
            if count >= min_nodes:
                logger.info(f"✅ DHT 就绪，当前节点数: {count}")
                return True
            await asyncio.sleep(0.5)
        logger.warning(f"DHT 等待超时，当前节点数: {self.get_node_count()}")
        return False

    async def run_periodic_save(self, interval: float = 300.0):
        self._running = True
        while self._running:
            await asyncio.sleep(interval)
            self.save_state()

    def stop(self):
        self._running = False
        self.save_state()
