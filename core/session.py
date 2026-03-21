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

import libtorrent as lt

from config import config
from network.dht import DHTManager
from network.encryption import get_encryption_settings
from network.nat import diagnose as nat_diagnose
from utils.system_probe import probe
from utils.speed_monitor import monitor
from core.bandwidth import BandwidthController
from core.peer_scheduler import PeerScheduler
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
        logger.info(f"硬件探测: {hw}")

        self._session = self._build_session(hw)
        self._dht = DHTManager(self._session)
        self._bandwidth = BandwidthController(self._session)

        # 恢复 DHT 路由表
        self._dht.load_state()
        self._dht.add_bootstrap_nodes()

        # 后台任务
        self._running = True
        self._bg_tasks = [
            asyncio.create_task(self._alert_loop()),
            asyncio.create_task(self._stats_loop()),
            asyncio.create_task(self._bandwidth.run()),
            asyncio.create_task(self._dht.run_periodic_save()),
        ]

        logger.info("✅ TurboSession 启动完成")

        # 异步打印 NAT 诊断（不阻塞启动）
        asyncio.create_task(self._run_nat_diag())

    async def _run_nat_diag(self):
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, nat_diagnose)
        logger.info(f"NAT 诊断: {result}")

    async def stop(self):
        logger.info("TurboSession 停止中...")
        self._running = False
        self._bandwidth.stop()
        self._dht.stop()
        for t in self._bg_tasks:
            t.cancel()
        # 保存所有任务的 resume data
        for task in self._tasks.values():
            self._save_resume_data(task)
        self._session.pause()
        logger.info("TurboSession 已停止")

    # ── 构建 libtorrent session ───────────────────────────
    def _build_session(self, hw: dict) -> lt.session:
        ses = lt.session()
        ses.listen_on(
            config["listen_port_start"],
            config["listen_port_end"],
        )

        # 动态参数（按硬件覆盖配置文件）
        dyn_connections = hw["optimal_connections"]
        dyn_cache = hw["optimal_cache_mb"] * 1024 // 16  # 转换为16KB块数

        settings = {
            # 连接
            "connections_limit":        dyn_connections,
            "active_downloads":         config["active_downloads"],
            "active_seeds":             config["active_seeds"],

            # 缓存
            "cache_size":               dyn_cache,
            "cache_expiry":             300,
            "use_read_cache":           True,
            "coalesce_writes":          config["coalesce_writes"],
            "coalesce_reads":           True,

            # 网络
            "enable_dht":               config["enable_dht"],
            "enable_lsd":               config["enable_lsd"],
            "enable_upnp":              config["enable_upnp"],
            "enable_natpmp":            config["enable_natpmp"],
            "dht_upload_rate_limit":    20000,

            # 调度
            "request_queue_time":       config["request_queue_time"],
            "max_out_request_queue":    config["max_out_request_queue"],
            "piece_timeout":            config["piece_timeout"],
            "peer_timeout":             config["peer_timeout"],
            "whole_pieces_threshold":   config["whole_pieces_threshold"],

            # 限速
            "upload_rate_limit":        config["upload_limit_kb"] * 1024,
            "download_rate_limit":      config["download_limit_kb"] * 1024,

            # 磁盘 IO
            "disk_io_write_mode":       0,   # 异步写入
            "disk_io_read_mode":        0,
            "file_pool_size":           500,

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
            f"加密={'强制' if config['force_encryption'] else '优先'}"
        )
        return ses

    # ── 任务管理 ──────────────────────────────────────────
    async def add_magnet(self, task_id: str, magnet: str, save_path: str):
        Path(save_path).mkdir(parents=True, exist_ok=True)

        params = lt.parse_magnet_uri(magnet)
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
        handle.set_max_connections(300)   # 单任务连接上限
        handle.set_max_uploads(-1)

        task = DownloadTask(
            task_id=task_id,
            magnet=magnet,
            save_path=save_path,
            handle=handle,
        )
        self._tasks[task_id] = task
        logger.info(f"任务已添加: {task_id}")

    async def add_torrent_file(self, task_id: str, torrent_data: bytes, save_path: str):
        """通过 .torrent 文件字节流添加任务"""
        from pathlib import Path
        import libtorrent as lt

        Path(save_path).mkdir(parents=True, exist_ok=True)

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
        logger.info(f"Torrent 任务已添加: {task_id} - {info.name()}")

    # ── TurboSession.remove_task 重构 ────────────────────────
    async def remove_task(
            self,
            task_id: str,
            intent: RemoveIntent = RemoveIntent.REMOVE_TASK,
    ) -> bool:
        """
        删除/停止任务，根据 intent 区分三种语义：

        - stop_seed   : 暂停做种，保留文件和 resume data，任务从内存移除
                        → 下次重新 add_magnet 可以用 resume data 恢复
        - remove_task : 移除任务，保留文件，清除 resume data
                        → 文件还在，但任务记录彻底消失
        - delete_all  : 移除任务 + 删除已下载文件
                        → 彻底清除，不可恢复
        """
        task = self._tasks.get(task_id)
        if not task:
            return False

        resume_file = Path(task.save_path) / f".{task_id}.resume"

        if intent == RemoveIntent.STOP_SEED:
            # ── 仅停止做种 ──────────────────────────────────
            # libtorrent 层面只 pause，不 remove
            # handle 保留在 session 里，任务从内存字典移除
            # resume data 保留，下次可以恢复
            task.handle.pause()
            task.handle.save_resume_data()  # 触发异步保存，_on_resume_data 会写盘
            monitor.remove_task(task_id)
            del self._tasks[task_id]
            logger.info(f"任务已停止做种（可恢复）: {task_id}")

        elif intent == RemoveIntent.REMOVE_TASK:
            # ── 移除任务，保留文件 ──────────────────────────
            self._session.remove_torrent(task.handle, 0)  # 0 = 不删文件
            monitor.remove_task(task_id)
            del self._tasks[task_id]
            # 清除 resume data（任务已不存在，留着没意义且占空间）
            if resume_file.exists():
                try:
                    resume_file.unlink()
                    logger.debug(f"已清除 resume data: {resume_file}")
                except Exception as e:
                    logger.warning(f"清除 resume data 失败: {e}")
            logger.info(f"任务已移除（文件保留）: {task_id}")

        elif intent == RemoveIntent.DELETE_ALL:
            # ── 移除任务 + 删除文件 ─────────────────────────
            self._session.remove_torrent(task.handle, lt.options_t.delete_files)
            monitor.remove_task(task_id)
            del self._tasks[task_id]
            # 同样清除 resume data
            if resume_file.exists():
                try:
                    resume_file.unlink()
                    logger.debug(f"已清除 resume data: {resume_file}")
                except Exception as e:
                    logger.warning(f"清除 resume data 失败: {e}")
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
        return config.all()

    async def apply_settings(self, new_settings: dict):
        config.update(new_settings)
        # 实时应用到 session
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
        if lt_settings:
            self._session.apply_settings(lt_settings)

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
                    break
        except Exception as e:
            logger.warning(f"保存 resume data 失败: {e}")
