"""
TurboSession：FSMagnet 核心下载会话
整合所有子模块，对外暴露统一接口供 API 层调用
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
import json
import libtorrent as lt

from config import config
from network.dht import DHTManager
from network.encryption import get_encryption_settings
from network.nat import diagnose as nat_diagnose
from utils.system_probe import probe
from utils.speed_monitor import monitor
from core.bandwidth import BandwidthController
from core.peer_scheduler import PeerScheduler
from core.task_store import upsert_task, remove_task as store_remove_task
import asyncio
from enum import Enum

class RemoveIntent(str, Enum):
    STOP_SEED = "stop_seed"  # 仅停止做种，保留文件 + resume data（可恢复）
    REMOVE_TASK = "remove_task"  # 移除任务，保留文件，清掉 resume data（不可恢复）
    DELETE_ALL = "delete_all"  # 移除任务 + 删除文件（彻底清除）


logger = logging.getLogger("fsmagnet.session")


# ── 任务状态 ─────────────────────────────────────────────
STATE_MAP = {
    lt.torrent_status.checking_files:         "checking",
    lt.torrent_status.downloading_metadata:   "metadata",
    lt.torrent_status.downloading:            "downloading",
    lt.torrent_status.finished:               "seeding",
    lt.torrent_status.seeding:                "seeding",
    lt.torrent_status.allocating:             "allocating",
    lt.torrent_status.checking_resume_data:   "checking",
}

PUBLIC_TRACKERS = [
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://open.tracker.cl:1337/announce",
    "udp://tracker.openbittorrent.com:6969/announce",
    "udp://opentracker.i2p.rocks:6969/announce",
    "udp://tracker.torrent.eu.org:451/announce",
    "udp://explodie.org:6969/announce",
    "udp://tracker.cyberia.is:6969/announce",
    "https://tracker.tamersunion.org:443/announce",
]

@dataclass
class DownloadTask:
    task_id: str
    magnet: str
    save_path: str
    handle: lt.torrent_handle
    added_at: float = field(default_factory=time.time)
    scheduler: Optional[PeerScheduler] = None

    # 做种相关
    total_uploaded: int = 0
    seeding_started_at: float = 0.0

    # 缓存的上一次状态（用于速度计算）
    _last_bytes: int = 0
    _last_time: float = field(default_factory=time.monotonic)


class TurboSession:
    """
    FSMagnet 核心会话，生命周期与程序相同
    """

    def __init__(self):
        self._session: Optional[lt.session] = None
        self._tasks: Dict[str, DownloadTask] = {}
        self._dht: Optional[DHTManager] = None
        self._bandwidth: Optional[BandwidthController] = None
        self._bg_tasks: List[asyncio.Task] = []
        self._running = False

    # ── 启动 / 停止 ───────────────────────────────────────
    async def start(self):
        logger.info("TurboSession 启动中...")

        hw = probe.summary()
        self._session = self._build_session(hw)
        self._dht = DHTManager(self._session)
        self._bandwidth = BandwidthController(self._session)

        self._dht.load_state()
        self._dht.add_bootstrap_nodes()
        self._dht.ensure_dht_started()

        self._running = True
        self._bg_tasks = [
            asyncio.create_task(self._alert_loop()),
            asyncio.create_task(self._stats_loop()),
            asyncio.create_task(self._bandwidth.run()),
            asyncio.create_task(self._dht.run_periodic_save()),
            asyncio.create_task(self._dht_warmup()),
        ]
        logger.info(f"✅ TurboSession 启动完成，DHT 节点数: {self._dht.get_node_count()}")
        asyncio.create_task(self._run_nat_diag())

    async def _dht_warmup(self):
        self._dht.add_bootstrap_nodes()
        ready = await self._dht.wait_until_ready(min_nodes=5, timeout=60.0)
        if ready:
            logger.info("✅ DHT 预热完成")
        else:
            logger.warning("⚠️ DHT 预热超时，将在后台继续建立连接")

    async def _run_nat_diag(self):
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, nat_diagnose)
        logger.info(f"NAT 诊断: {result}")

    async def stop(self):
        logger.info("TurboSession 停止中...")
        self._running = False
        self._bandwidth.stop()
        self._dht.stop()

        if self._tasks:
            # ✅ 向所有任务发出 save_resume_data 请求
            pending = {task_id for task_id, task in self._tasks.items()
                       if task.handle.is_valid()}
            done_event = asyncio.Event()
            loop = asyncio.get_event_loop()

            # 临时标记：_on_resume_data 写完一个就从 pending 移除
            self._stop_pending = pending
            self._stop_event = done_event

            for task in self._tasks.values():
                if task.handle.is_valid():
                    try:
                        task.handle.save_resume_data(
                            lt.torrent_handle.save_info_dict |
                            lt.torrent_handle.only_if_modified
                        )
                    except Exception:
                        pass

            # 继续跑 alert_loop 直到所有 resume data 写完（最多等 5 秒）
            self._running = True  # 临时重开，让 alert_loop 继续处理
            try:
                await asyncio.wait_for(done_event.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("stop(): 部分 resume data 未能在 5s 内写完，强制退出")
            finally:
                self._running = False
                self._stop_pending = None
                self._stop_event = None

        for t in self._bg_tasks:
            t.cancel()

        self._session.pause()
        logger.info("TurboSession 已停止")

    # ── 构建 libtorrent session ───────────────────────────
    def _build_session(self, hw: dict) -> lt.session:
        ses = lt.session()
        # 动态参数（按硬件覆盖配置文件）
        dyn_connections = hw["optimal_connections"]
        dyn_cache = hw["optimal_cache_mb"] * 1024 // 16  # 转换为16KB块数

        settings = {
            "listen_interfaces": f"0.0.0.0:{config['listen_port_start']}",

            # 连接
            "connections_limit": dyn_connections,
            "active_downloads": config["active_downloads"],
            "active_seeds": config["active_seeds"],

            # 缓存
            "cache_size": dyn_cache,
            "cache_expiry": 300,
            "use_read_cache": True,
            "coalesce_writes": config["coalesce_writes"],
            "coalesce_reads": True,

            # 网络
            "enable_dht": config["enable_dht"],
            "enable_lsd": config["enable_lsd"],
            "enable_upnp": config["enable_upnp"],
            "enable_natpmp": config["enable_natpmp"],
            "dht_upload_rate_limit": 20000,

            # 调度
            "request_queue_time": config["request_queue_time"],
            "max_out_request_queue": config["max_out_request_queue"],
            "piece_timeout": config["piece_timeout"],
            "peer_timeout": config["peer_timeout"],
            "whole_pieces_threshold": config["whole_pieces_threshold"],

            # 限速
            "upload_rate_limit": config["upload_limit_kb"] * 1024,
            "download_rate_limit": config["download_limit_kb"] * 1024,

            # 磁盘 IO
            "disk_io_write_mode": 0,
            "disk_io_read_mode": 0,
            "file_pool_size": 500,

            # Alert 掩码
            "alert_mask": (
                    lt.alert.category_t.error_notification
                    | lt.alert.category_t.status_notification
                    | lt.alert.category_t.progress_notification
                    | lt.alert.category_t.performance_warning
            ),
        }

        # 加密设置
        settings.update(get_encryption_settings(config["force_encryption"]))
        ses.apply_settings(settings)

        logger.info(
            f"Session 参数: 连接数={dyn_connections} "
            f"缓存={dyn_cache * 16 // 1024}MB "
            f"端口={config['listen_port_start']} "
            f"加密={'强制' if config['force_encryption'] else '优先'}"
        )
        return ses

    # ── 任务管理 ──────────────────────────────────────────
    async def add_magnet(self, task_id: str, magnet: str, save_path: str):
        Path(save_path).mkdir(parents=True, exist_ok=True)

        params = lt.parse_magnet_uri(magnet)
        params.save_path = save_path

        # ✅ 注入公共 Tracker，加速 peer 发现，不依赖 DHT
        existing = set(params.trackers)
        for t in PUBLIC_TRACKERS:
            if t not in existing:
                params.trackers.append(t)
        logger.info(f"注入 Tracker 后共 {len(params.trackers)} 个")

        # 尝试加载 resume data
        resume_file = Path(save_path) / f".{task_id}.resume"
        if resume_file.exists():
            try:
                with open(resume_file, "rb") as f:
                    params.resume_data = f.read()
                logger.info(f"任务 {task_id} 已加载断点续传数据")
            except Exception:
                pass

        handle = self._session.add_torrent(params)
        handle.set_max_connections(300)
        handle.set_max_uploads(-1)

        task = DownloadTask(
            task_id=task_id,
            magnet=magnet,
            save_path=save_path,
            handle=handle,
        )
        self._tasks[task_id] = task

        # ✅ 持久化任务
        upsert_task(task_id, magnet, save_path, task_type="magnet")
        logger.info(f"任务已添加: {task_id}")

    async def add_torrent_file(self, task_id: str, torrent_data: bytes, save_path: str):
        """通过 .torrent 文件字节流添加任务"""
        from config import APP_DATA_DIR

        Path(save_path).mkdir(parents=True, exist_ok=True)

        # ✅ 保存 .torrent 文件，重启后恢复任务用
        torrent_dir = APP_DATA_DIR / "torrents"
        torrent_dir.mkdir(parents=True, exist_ok=True)
        torrent_path = torrent_dir / f"{task_id}.torrent"
        torrent_path.write_bytes(torrent_data)

        info = lt.torrent_info(lt.bdecode(torrent_data))
        params = lt.add_torrent_params()
        params.ti = info
        params.save_path = save_path

        # 尝试加载 resume data
        resume_file = Path(save_path) / f".{task_id}.resume"
        if resume_file.exists():
            try:
                with open(resume_file, "rb") as f:
                    params.resume_data = f.read()
                logger.info(f"任务 {task_id} 已加载断点续传数据")
            except Exception:
                pass

        handle = self._session.add_torrent(params)
        handle.set_max_connections(300)
        handle.set_max_uploads(-1)

        task = DownloadTask(
            task_id=task_id,
            magnet=f"[torrent]{info.name()}",
            save_path=save_path,
            handle=handle,
        )
        self._tasks[task_id] = task

        # ✅ 持久化任务（uri 存 torrent 文件路径）
        upsert_task(task_id, str(torrent_path), save_path, task_type="torrent")
        logger.info(f"Torrent 任务已添加: {task_id} - {info.name()}")

    # ── TurboSession.remove_task 重构 ────────────────────────
    async def remove_task(
            self,
            task_id: str,
            intent: RemoveIntent = RemoveIntent.REMOVE_TASK,
    ) -> bool:
        task = self._tasks.get(task_id)
        if not task:
            return False

        resume_file = Path(task.save_path) / f".{task_id}.resume"

        if intent == RemoveIntent.STOP_SEED:
            task.handle.pause()
            task.handle.save_resume_data()
            monitor.remove_task(task_id)
            del self._tasks[task_id]
            # ✅ 从持久化列表移除
            store_remove_task(task_id)
            logger.info(f"任务已停止做种（可恢复）: {task_id}")

        elif intent == RemoveIntent.REMOVE_TASK:
            self._session.remove_torrent(task.handle, 0)
            monitor.remove_task(task_id)
            del self._tasks[task_id]
            if resume_file.exists():
                try:
                    resume_file.unlink()
                except Exception as e:
                    logger.warning(f"清除 resume data 失败: {e}")
            # ✅ 从持久化列表移除
            store_remove_task(task_id)
            logger.info(f"任务已移除（文件保留）: {task_id}")

        elif intent == RemoveIntent.DELETE_ALL:
            self._session.remove_torrent(task.handle, lt.options_t.delete_files)
            monitor.remove_task(task_id)
            del self._tasks[task_id]
            if resume_file.exists():
                try:
                    resume_file.unlink()
                except Exception as e:
                    logger.warning(f"清除 resume data 失败: {e}")
            # ✅ 从持久化列表移除
            store_remove_task(task_id)
            logger.info(f"任务已删除（含文件）: {task_id}")

        return True

    async def pause_task(self, task_id: str):
        task = self._tasks.get(task_id)
        if task:
            task.handle.pause()

    async def resume_task(self, task_id: str):
        task = self._tasks.get(task_id)
        if task:
            task.handle.resume()

    # ── 数据查询 ──────────────────────────────────────────
    def get_all_tasks(self) -> List[dict]:
        return [self._task_to_dict(t) for t in self._tasks.values()]

    def _task_to_dict(self, task: DownloadTask) -> dict:
        try:
            s = task.handle.status()
            state = STATE_MAP.get(s.state, "unknown")
            if task.handle.is_paused():
                state = "paused"

            name = s.name or "获取元数据中..."
            total = s.total_wanted if s.total_wanted > 0 else 0
            done = s.total_wanted_done

            return {
                "id":             task.task_id,
                "name":           name,
                "state":          state,
                "progress":       round(s.progress * 100, 2),
                "download_speed": s.download_payload_rate,
                "upload_speed":   s.upload_payload_rate,
                "peers":          s.num_peers,
                "seeds":          s.num_seeds,
                "total_size":     total,
                "done_size":      done,
                "eta":            self._calc_eta(s),
                "save_path":      task.save_path,
                "added_at":       task.added_at,
            }
        except Exception as e:
            return {
                "id": task.task_id, "name": "错误",
                "state": "error", "progress": 0,
                "download_speed": 0, "upload_speed": 0,
                "peers": 0, "seeds": 0, "total_size": 0,
                "done_size": 0, "eta": -1,
                "save_path": task.save_path, "added_at": task.added_at,
            }

    def _calc_eta(self, s) -> int:
        if s.download_payload_rate <= 0:
            return -1
        remaining = s.total_wanted - s.total_wanted_done
        return max(0, int(remaining / s.download_payload_rate))

    def get_stats_snapshot(self) -> dict:
        tasks = self.get_all_tasks()
        global_dl = sum(t["download_speed"] for t in tasks)
        global_ul = sum(t["upload_speed"] for t in tasks)
        return {
            "tasks":        tasks,
            "global_speed": global_dl,
            "global_ul":    global_ul,
            "timestamp":    time.time(),
            "dht_nodes":    self._dht.get_node_count() if self._dht else 0,
            "bandwidth":    self._bandwidth.get_trend_summary() if self._bandwidth else {},
        }

    def get_settings(self) -> dict:
        settings = config.all()
        # ── 合并 UI 配置（主题等）────────────────────────────
        ui = self._load_ui_settings()
        settings["theme"] = ui.get("theme", "dark")
        return settings

    async def apply_settings(self, new_settings: dict):
        theme = new_settings.pop("theme", None)
        if theme is not None:
            self.save_ui_setting("theme", theme)

        config.update(new_settings)

        lt_settings = {}
        if "connections_limit" in new_settings:
            lt_settings["connections_limit"] = new_settings["connections_limit"]
        if "upload_limit_kb" in new_settings:
            lt_settings["upload_rate_limit"] = new_settings["upload_limit_kb"] * 1024
        if "download_limit_kb" in new_settings:
            lt_settings["download_rate_limit"] = new_settings["download_limit_kb"] * 1024
        if "cache_mb" in new_settings:
            lt_settings["cache_size"] = new_settings["cache_mb"] * 1024 // 16
        if "force_encryption" in new_settings:
            lt_settings.update(get_encryption_settings(new_settings["force_encryption"]))
        # ✅ 补上这三个
        if "enable_dht" in new_settings:
            lt_settings["enable_dht"] = new_settings["enable_dht"]
        if "enable_upnp" in new_settings:
            lt_settings["enable_upnp"] = new_settings["enable_upnp"]
        if "enable_lsd" in new_settings:
            lt_settings["enable_lsd"] = new_settings["enable_lsd"]

        if lt_settings:
            self._session.apply_settings(lt_settings)

    def save_ui_setting(self, key: str, value):
        """保存 UI 专属配置到独立 json 文件"""
        data = self._load_ui_settings()
        data[key] = value
        try:
            with open(self._ui_settings_path(), "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"保存 UI 配置失败: {e}")

    def _load_ui_settings(self) -> dict:
        path = self._ui_settings_path()
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _ui_settings_path(self) -> Path:
        from config import APP_DATA_DIR
        return APP_DATA_DIR / "ui_settings.json"

    # ── 后台循环 ──────────────────────────────────────────
    async def _alert_loop(self):
        """处理 libtorrent alert 事件"""
        while self._running:
            alerts = self._session.pop_alerts()
            for alert in alerts:
                self._handle_alert(alert)
            await asyncio.sleep(0.1)

    def _handle_alert(self, alert):
        atype = type(alert).__name__
        if atype == "save_resume_data_alert":
            self._on_resume_data(alert)
        elif atype == "torrent_error_alert":
            logger.error(f"Torrent 错误: {alert.message()}")
        elif atype == "performance_alert":
            logger.warning(f"性能警告: {alert.message()}")
        elif atype == "metadata_received_alert":
            logger.info(f"元数据获取成功: {alert.torrent_name()}")

    async def _stats_loop(self):
        """定期更新 Peer 调度统计"""
        while self._running:
            for task in list(self._tasks.values()):
                if task.scheduler is None and task.handle.has_metadata():
                    task.scheduler = PeerScheduler(task.handle)
                if task.scheduler:
                    task.scheduler.update_from_handle()
                    task.scheduler.maybe_evict()
            await asyncio.sleep(5)

    def _save_resume_data(self, task: DownloadTask):
        try:
            task.handle.save_resume_data()
        except Exception:
            pass

    def _on_resume_data(self, alert):
        """保存断点续传数据到磁盘"""
        try:
            h = alert.handle
            for task in self._tasks.values():
                if task.handle == h:
                    resume_file = Path(task.save_path) / f".{task.task_id}.resume"
                    data = lt.bencode(alert.resume_data)
                    with open(resume_file, "wb") as f:
                        f.write(data)
                    logger.debug(f"resume data 已保存: {task.task_id}")

                    # ✅ 通知 stop() 这个任务已写完
                    if hasattr(self, "_stop_pending") and self._stop_pending is not None:
                        self._stop_pending.discard(task.task_id)
                        if not self._stop_pending and self._stop_event is not None:
                            loop = asyncio.get_event_loop()
                            loop.call_soon_threadsafe(self._stop_event.set)
                    break
        except Exception as e:
            logger.warning(f"保存 resume data 失败: {e}")
