from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import api.server as srv

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    save_path:          Optional[str]  = None
    upload_limit_kb:    Optional[int]  = None   # 上传限速 KB/s，0=不限
    download_limit_kb:  Optional[int]  = None   # 下载限速 KB/s，0=不限
    connections_limit:  Optional[int]  = None   # 最大连接数
    cache_mb:           Optional[int]  = None   # 缓存大小 MB
    force_encryption:   Optional[bool] = None   # 强制加密
    enable_dht:         Optional[bool] = None   # DHT
    enable_upnp:        Optional[bool] = None   # UPnP
    enable_lsd:         Optional[bool] = None   # 局域网发现
    theme:              Optional[str] = None    # 主题


@router.get("/")
async def get_settings():
    """读取当前配置"""
    settings = srv.turbo_session.get_settings()
    return {"ok": True, "settings": settings}


@router.patch("/")
async def update_settings(req: SettingsUpdate):
    try:
        data = req.dict(exclude_none=True)
        # ── 把 theme 从 session 参数里剥离出来单独保存 ──
        theme = data.pop("theme", None)
        if theme is not None:
            srv.turbo_session.save_ui_setting("theme", theme)  # 见下方说明

        # 剩余的才传给 libtorrent session
        if data:
            await srv.turbo_session.apply_settings(data)

        settings = srv.turbo_session.get_settings()
        return {"ok": True, "settings": settings}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
