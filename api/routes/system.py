"""
系统级接口：文件夹选择、.torrent 文件选择
通过队列把对话框请求转发到主线程执行（WinForms 限制）
"""
import logging
from fastapi import APIRouter, HTTPException
import api.server as srv

router = APIRouter(prefix="/api/system", tags=["system"])
logger = logging.getLogger("fsmagnet.system")

OPEN_DIALOG   = 0   # webview.OPEN_DIALOG
FOLDER_DIALOG = 2   # webview.FOLDER_DIALOG


@router.get("/pick-folder")
async def pick_folder():
    import asyncio
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            None,
            lambda: srv.request_dialog(FOLDER_DIALOG, allow_multiple=False)
        )
        # result 可能是 None（取消）或 tuple（选了路径）
        if result and len(result) > 0:
            return {"ok": True, "path": result[0]}
        return {"ok": False, "path": None}   # 用户取消
    except Exception as e:
        logger.error(f"pick_folder 失败: {e}")
        return {"ok": False, "path": None}   # 不抛 500，静默处理


@router.get("/pick-torrent")
async def pick_torrent():
    import asyncio
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            None,
            lambda: srv.request_dialog(
                OPEN_DIALOG,
                allow_multiple=False,
                file_types=("Torrent 文件 (*.torrent)",),
            )
        )
        if result and len(result) > 0:
            return {"ok": True, "path": result[0]}
        return {"ok": False, "path": None}   # 用户取消
    except Exception as e:
        logger.error(f"pick_torrent 失败: {e}")
        return {"ok": False, "path": None}