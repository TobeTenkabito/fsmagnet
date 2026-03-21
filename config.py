"""
FSMagnet 全局配置
自用场景：所有参数都可以激进调整
"""
import sys
import os
import json
from pathlib import Path


def _get_app_data_dir() -> Path:
    """
    获取应用数据目录，兼容开发环境和 PyInstaller 打包环境。

    Windows : C:/Users/<用户>/AppData/Roaming/FSMagnet/
    macOS   : ~/Library/Application Support/FSMagnet/
    Linux   : ~/.config/FSMagnet/
    """
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))

    app_dir = base / "FSMagnet"
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


# ── 路径常量 ──────────────────────────────────────────
APP_DATA_DIR = _get_app_data_dir()
CONFIG_PATH  = APP_DATA_DIR / "fsmagnet_config.json"

# 默认下载目录：用户的 Downloads 文件夹
DEFAULT_SAVE_PATH = str(Path.home() / "Downloads" / "FSMagnet")


DEFAULT_CONFIG = {
    # ── 下载 ──────────────────────────────
    "save_path":          DEFAULT_SAVE_PATH,
    "connections_limit":  500,
    "upload_limit_kb":    50,
    "download_limit_kb":  0,
    "active_downloads":   5,
    "active_seeds":       10,

    # ── 磁盘缓存 ──────────────────────────
    "cache_mb":           512,
    "coalesce_writes":    True,
    "preallocate_disk":   True,

    # ── 网络 ──────────────────────────────
    "force_encryption":   True,
    "enable_dht":         True,
    "enable_lsd":         True,
    "enable_upnp":        True,
    "enable_natpmp":      True,
    "listen_port_start":  6881,
    "listen_port_end":    6891,

    # ── DHT Bootstrap 节点 ────────────────
    "dht_bootstrap_nodes": [
        ("router.bittorrent.com", 6881),
        ("router.utorrent.com",   6881),
        ("dht.transmissionbt.com",6881),
        ("dht.aelitis.com",       6881),
    ],

    # ── 调度 ──────────────────────────────
    "request_queue_time":       3,
    "max_out_request_queue":    1500,
    "piece_timeout":            20,
    "peer_timeout":             20,
    "whole_pieces_threshold":   20,
}


class Config:
    def __init__(self):
        self._data: dict = {}
        self.load()

    def load(self):
        """从本地 JSON 加载配置，不存在则用默认值"""
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                # 新版本新增的 key 用默认值补全
                self._data = {**DEFAULT_CONFIG, **saved}
                return
            except Exception:
                # JSON 损坏时回退默认值
                pass
        self._data = dict(DEFAULT_CONFIG)

    def save(self):
        """持久化到 APP_DATA_DIR/fsmagnet_config.json"""
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        # 过滤掉不可序列化的类型（如 tuple 列表）
        serializable = _make_serializable(self._data)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=2, ensure_ascii=False)

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value):
        self._data[key] = value
        self.save()

    def update(self, data: dict):
        self._data.update(data)
        self.save()

    def all(self) -> dict:
        return _make_serializable(self._data)

    def __getitem__(self, key):
        return self._data[key]


def _make_serializable(data: dict) -> dict:
    """
    将 dict 中不可 JSON 序列化的类型转换：
    - tuple → list（dht_bootstrap_nodes 是 tuple 列表）
    """
    result = {}
    for k, v in data.items():
        if isinstance(v, list):
            result[k] = [list(i) if isinstance(i, tuple) else i for i in v]
        else:
            result[k] = v
    return result


# 全局单例
config = Config()