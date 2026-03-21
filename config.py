"""
FSMagnet 全局配置
自用场景：所有参数都可以激进调整
"""
import os
import json
from pathlib import Path

CONFIG_PATH = Path("./fsmagnet_config.json")

DEFAULT_CONFIG = {
    # ── 下载 ──────────────────────────────
    "save_path": "./downloads",
    "connections_limit": 500,        # 最大全局连接数（启动时按RAM/CPU动态覆盖）
    "upload_limit_kb": 50,           # 上传限速 KB/s，0=不限
    "download_limit_kb": 0,          # 下载限速 KB/s，0=不限
    "active_downloads": 5,           # 同时下载任务数
    "active_seeds": 10,              # 同时做种任务数

    # ── 磁盘缓存 ──────────────────────────
    "cache_mb": 512,                 # 磁盘缓存 MB（启动时按RAM动态覆盖）
    "coalesce_writes": True,         # 合并小写入
    "preallocate_disk": True,        # 预分配磁盘空间

    # ── 网络 ──────────────────────────────
    "force_encryption": True,        # 强制协议加密
    "enable_dht": True,
    "enable_lsd": True,              # 局域网发现
    "enable_upnp": True,
    "enable_natpmp": True,
    "listen_port_start": 6881,
    "listen_port_end": 6891,

    # ── DHT Bootstrap 节点 ────────────────
    "dht_bootstrap_nodes": [
        ("router.bittorrent.com", 6881),
        ("router.utorrent.com", 6881),
        ("dht.transmissionbt.com", 6881),
        ("dht.aelitis.com", 6881),
    ],

    # ── 调度 ──────────────────────────────
    "request_queue_time": 3,
    "max_out_request_queue": 1500,
    "piece_timeout": 20,
    "peer_timeout": 20,
    "whole_pieces_threshold": 20,
}


class Config:
    def __init__(self):
        self._data: dict = {}
        self.load()

    def load(self):
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                self._data = {**DEFAULT_CONFIG, **saved}
                return
            except Exception:
                pass
        self._data = dict(DEFAULT_CONFIG)

    def save(self):
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value):
        self._data[key] = value
        self.save()

    def update(self, data: dict):
        self._data.update(data)
        self.save()

    def all(self) -> dict:
        return dict(self._data)

    def __getitem__(self, key):
        return self._data[key]


# 全局单例
config = Config()