import uuid
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from core.session import RemoveIntent
from typing import Optional
import api.server as srv

router = APIRouter(prefix="/api/download", tags=["download"])


class AddTaskRequest(BaseModel):
    uri: str                         # 磁力链
    save_path: Optional[str] = None  # 覆盖默认保存路径


@router.post("/add")
async def add_task(req: AddTaskRequest):
    """添加磁力链任务"""
    try:
        from config import config
        save_path = req.save_path or config["save_path"]
        task_id = str(uuid.uuid4())[:8]
        await srv.turbo_session.add_magnet(task_id, req.uri, save_path)
        return {"ok": True, "task_id": task_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/add-torrent")
async def add_torrent(
    file: UploadFile = File(...),
    save_path: Optional[str] = Form(None),
):
    """上传 .torrent 文件并加入下载队列"""
    if not file.filename.endswith(".torrent"):
        raise HTTPException(status_code=400, detail="只接受 .torrent 文件")
    try:
        from config import config
        import libtorrent as lt

        torrent_data = await file.read()
        save_path = save_path or config["save_path"]
        task_id = str(uuid.uuid4())[:8]

        await srv.turbo_session.add_torrent_file(task_id, torrent_data, save_path)
        return {"ok": True, "task_id": task_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{task_id}")
async def remove_task(
        task_id: str,
        intent: RemoveIntent = RemoveIntent.REMOVE_TASK,
):
    """
    删除/停止任务

    intent 可选值：
    - stop_seed   : 停止做种，保留文件和断点数据（任务可重新添加恢复）
    - remove_task : 移除任务记录，保留已下载文件（默认）
    - delete_all  : 移除任务并删除所有已下载文件
    """
    ok = await srv.turbo_session.remove_task(task_id, intent)
    if not ok:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"ok": True, "intent": intent}


@router.post("/{task_id}/stop-seed")
async def stop_seed(task_id: str):
    """停止做种，保留文件（做种任务专用）"""
    task = _find_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task["state"] != "seeding":
        raise HTTPException(status_code=400, detail="任务当前不在做种状态")
    ok = await srv.turbo_session.remove_task(task_id, RemoveIntent.STOP_SEED)
    return {"ok": ok}


@router.post("/{task_id}/pause")
async def pause_task(task_id: str):
    """暂停任务"""
    task = _find_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    await srv.turbo_session.pause_task(task_id)
    return {"ok": True}


@router.post("/{task_id}/resume")
async def resume_task(task_id: str):
    """恢复任务"""
    task = _find_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    await srv.turbo_session.resume_task(task_id)
    return {"ok": True}


@router.get("/list")
async def list_tasks():
    """列出所有任务"""
    tasks = srv.turbo_session.get_all_tasks()
    return {"ok": True, "tasks": tasks}


@router.get("/{task_id}")
async def get_task(task_id: str):
    """获取单个任务详情"""
    task = _find_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"ok": True, "task": task}


def _find_task(task_id: str) -> Optional[dict]:
    tasks = srv.turbo_session.get_all_tasks()
    return next((t for t in tasks if t["id"] == task_id), None)


class AddTorrentByPathRequest(BaseModel):
    file_path: str
    save_path: Optional[str] = None


@router.post("/add-torrent-path")
async def add_torrent_by_path(req: AddTorrentByPathRequest):
    """通过本地路径添加 .torrent 文件"""
    import os
    if not os.path.exists(req.file_path):
        raise HTTPException(status_code=400, detail="文件不存在")
    if not req.file_path.endswith(".torrent"):
        raise HTTPException(status_code=400, detail="只接受 .torrent 文件")
    try:
        from config import config
        save_path = req.save_path or config["save_path"]
        task_id = str(uuid.uuid4())[:8]
        with open(req.file_path, "rb") as f:
            torrent_data = f.read()
        await srv.turbo_session.add_torrent_file(task_id, torrent_data, save_path)
        return {"ok": True, "task_id": task_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))