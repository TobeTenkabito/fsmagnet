"""
DHT 加速模块
"""
import asyncio
import ipaddress
import logging
import socket
import time
from typing import Iterable

import libtorrent as lt

from config import APP_DATA_DIR, config

logger = logging.getLogger("fsmagnet.dht")
DHT_STATE_FILE = APP_DATA_DIR / "fsmagnet_dht_state.dat"

DNS_CACHE_TTL = 600.0
DNS_TIMEOUT = 2.5
DNS_CONCURRENCY = 8

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
        self._added_nodes: set[tuple[str, int]] = set()
        self._dns_cache: dict[tuple[str, int], tuple[float, list[str]]] = {}

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

    def add_bootstrap_nodes(self) -> int:
        """同步版本：只添加无需 DNS 的 IP 节点，避免阻塞启动路径。"""
        success = 0
        nodes = self._bootstrap_nodes()
        for host, port in nodes:
            ip = self._ip_literal(host)
            if ip and self._add_dht_node(ip, port):
                success += 1
        logger.info(f"✅ 同步添加 {success}/{len(nodes)} 个无需 DNS 的 Bootstrap 节点")
        return success

    async def add_bootstrap_nodes_async(
        self,
        dns_timeout: float = DNS_TIMEOUT,
        concurrency: int = DNS_CONCURRENCY,
    ) -> int:
        """异步版本：并发解析 DNS，缓存结果，不阻塞事件循环。"""
        nodes = self._bootstrap_nodes()
        semaphore = asyncio.Semaphore(max(1, concurrency))
        success = 0
        candidates = 0
        tasks = []

        for host, port in nodes:
            ip = self._ip_literal(host)
            if ip:
                candidates += 1
                if self._add_dht_node(ip, port):
                    success += 1
                continue
            tasks.append(asyncio.create_task(
                self._resolve_node(host, port, semaphore, dns_timeout)
            ))

        for task in asyncio.as_completed(tasks):
            host, port, addresses = await task
            candidates += len(addresses)
            for ip in addresses:
                if self._add_dht_node(ip, port):
                    logger.debug(f"DHT bootstrap: {host} → {ip}:{port}")
                    success += 1
        logger.info(f"✅ 异步添加 {success}/{candidates} 个 Bootstrap 节点")
        return success

    def _bootstrap_nodes(self) -> list[tuple[str, int]]:
        configured = config.get("dht_bootstrap_nodes", []) or []
        return self._normalize_nodes([*configured, *BOOTSTRAP_NODES])

    @staticmethod
    def _normalize_nodes(nodes: Iterable[tuple[str, int]]) -> list[tuple[str, int]]:
        normalized: list[tuple[str, int]] = []
        seen: set[tuple[str, int]] = set()
        for node in nodes:
            try:
                host, port = node
                host = str(host).strip()
                port = int(port)
            except (TypeError, ValueError):
                logger.warning(f"忽略无效 DHT Bootstrap 节点: {node}")
                continue
            if not host or not 0 < port < 65536:
                logger.warning(f"忽略无效 DHT Bootstrap 节点: {node}")
                continue

            key = (host.lower(), port)
            if key in seen:
                continue
            seen.add(key)
            normalized.append((host, port))
        return normalized

    async def _resolve_node(
        self,
        host: str,
        port: int,
        semaphore: asyncio.Semaphore,
        timeout: float,
    ) -> tuple[str, int, list[str]]:
        ip = self._ip_literal(host)
        if ip:
            return host, port, [ip]

        key = (host.lower(), port)
        now = time.monotonic()
        cached = self._dns_cache.get(key)
        if cached and cached[0] > now:
            return host, port, cached[1]

        async with semaphore:
            now = time.monotonic()
            cached = self._dns_cache.get(key)
            if cached and cached[0] > now:
                return host, port, cached[1]

            try:
                addresses = await self._lookup_host(host, port, timeout)
            except asyncio.TimeoutError:
                logger.warning(f"DNS 解析超时: {host}")
                return host, port, []
            except socket.gaierror as e:
                logger.warning(f"DNS 解析失败: {host} → {e}")
                return host, port, []
            except Exception as e:
                logger.warning(f"DNS 解析异常: {host} → {e}")
                return host, port, []

        self._dns_cache[key] = (time.monotonic() + DNS_CACHE_TTL, addresses)
        return host, port, addresses

    async def _lookup_host(self, host: str, port: int, timeout: float) -> list[str]:
        loop = asyncio.get_running_loop()
        infos = await asyncio.wait_for(
            loop.getaddrinfo(
                host,
                port,
                family=socket.AF_INET,
                type=socket.SOCK_DGRAM,
            ),
            timeout=timeout,
        )

        addresses: list[str] = []
        seen: set[str] = set()
        for _, _, _, _, sockaddr in infos:
            ip = sockaddr[0]
            if ip not in seen:
                seen.add(ip)
                addresses.append(ip)
        return addresses

    @staticmethod
    def _ip_literal(host: str) -> str | None:
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            return None
        if ip.version != 4:
            return None
        return str(ip)

    def _add_dht_node(self, host: str, port: int) -> bool:
        key = (host, port)
        if key in self._added_nodes:
            return False
        try:
            self.session.add_dht_node(key)
            self._added_nodes.add(key)
            return True
        except Exception as e:
            logger.warning(f"Bootstrap 节点添加失败: {host} → {e}")
            return False

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
