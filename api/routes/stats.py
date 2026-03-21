import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import json
import api.server as srv

router = APIRouter(prefix="/api/stats", tags=["stats"])


# ── REST：全局统计快照 ────────────────────────────────────
@router.get("/")
async def get_stats():
    """获取全局速度、流量、DHT 统计"""
    stats = srv.turbo_session.get_stats_snapshot()
    return {"ok": True, "stats": stats}


# ── SSE：实时推送 ─────────────────────────────────────────
# ⚠️ 必须在 /{task_id} 之前注册，否则 "stream" 会被当成 task_id
@router.get("/stream")
async def stats_stream():
    """
    SSE 实时推送，每秒一帧。
    前端收到格式：
      data: {"tasks":[...], "global_speed":102400, "global_ul":4096, "dht_nodes":312}
    """
    async def event_generator():
        while True:
            try:
                tasks = srv.turbo_session.get_all_tasks()
                stats = srv.turbo_session.get_stats_snapshot()

                payload = {
                    "tasks":        tasks,
                    "global_speed": stats.get("global_speed", 0),
                    "global_ul":    stats.get("global_ul",    0),
                    "dht_nodes":    stats.get("dht_nodes",    0),
                }
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

            except Exception:
                yield "data: {}\n\n"

            await asyncio.sleep(1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


# ── REST：单任务统计 ──────────────────────────────────────
# ⚠️ 动态路由放最后
@router.get("/{task_id}")
async def get_task_stats(task_id: str):
    """获取单个任务的速度/进度"""
    tasks = srv.turbo_session.get_all_tasks()
    task = next((t for t in tasks if t["id"] == task_id), None)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"ok": True, "stats": task}