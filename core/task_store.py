"""
任务持久化存储
负责把下载任务的元信息存到 APP_DATA_DIR/tasks.json
重启后可以从这里恢复所有任务
"""
import json
import logging
from pathlib import Path
from typing import Optional

from config import APP_DATA_DIR

logger = logging.getLogger("fsmagnet.task_store")

TASKS_FILE = APP_DATA_DIR / "tasks.json"


def load_tasks() -> list[dict]:
    """读取持久化的任务列表，返回 list[dict]，失败返回空列表"""
    if not TASKS_FILE.exists():
        return []
    try:
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except Exception as e:
        logger.warning(f"读取 tasks.json 失败，忽略: {e}")
    return []


def save_tasks(tasks: list[dict]):
    """把任务列表持久化到磁盘"""
    try:
        TASKS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(TASKS_FILE, "w", encoding="utf-8") as f:
            json.dump(tasks, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"保存 tasks.json 失败: {e}")


def upsert_task(task_id: str, uri: str, save_path: str, task_type: str = "magnet"):
    """
    新增或更新一条任务记录
    task_type: "magnet" | "torrent"
    """
    tasks = load_tasks()
    # 已存在则更新
    for t in tasks:
        if t["task_id"] == task_id:
            t.update({"uri": uri, "save_path": save_path, "task_type": task_type})
            save_tasks(tasks)
            return
    # 不存在则追加
    tasks.append({
        "task_id":   task_id,
        "uri":       uri,
        "save_path": save_path,
        "task_type": task_type,
    })
    save_tasks(tasks)


def remove_task(task_id: str):
    """从持久化列表中删除一条任务"""
    tasks = load_tasks()
    tasks = [t for t in tasks if t["task_id"] != task_id]
    save_tasks(tasks)