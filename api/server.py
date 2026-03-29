import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import sys
import os
import logging
logger = logging.getLogger("fsmagnet.server")

from core.session import TurboSession

turbo_session: TurboSession = None
webview_window = None

# 对话框类型常量
OPEN_DIALOG   = 0
FOLDER_DIALOG = 2


def _win_pick_folder() -> tuple | None:
    """
    用 IFileOpenDialog COM 接口弹出文件夹选择框。
    比 SHBrowseForFolderW 更现代、更稳定，Win Vista+ 均支持。
    """
    import ctypes
    import ctypes.wintypes as wt

    ole32    = ctypes.WinDLL("ole32",    use_last_error=True)
    shell32  = ctypes.WinDLL("shell32",  use_last_error=True)

    # IFileOpenDialog CLSID / IID
    CLSID_FileOpenDialog = ctypes.c_byte * 16
    IID_IFileOpenDialog  = ctypes.c_byte * 16

    # 用 CLSIDFromString 解析 GUID
    clsid = (ctypes.c_byte * 16)()
    iid   = (ctypes.c_byte * 16)()
    ole32.CLSIDFromString("{DC1C5A9C-E88A-4dde-A5A1-60F82A20AEF7}", ctypes.byref(clsid))
    ole32.IIDFromString( "{D57C7288-D4AD-4768-BE02-9D969532D960}", ctypes.byref(iid))

    ole32.CoInitialize(None)
    try:
        # CoCreateInstance
        pDialog = ctypes.c_void_p()
        hr = ole32.CoCreateInstance(
            ctypes.byref(clsid),
            None,
            1,                      # CLSCTX_INPROC_SERVER
            ctypes.byref(iid),
            ctypes.byref(pDialog),
        )
        if hr != 0 or not pDialog.value:
            return None

        # vtable 布局（IFileOpenDialog 继承自 IFileDialog 继承自 IModalWindow）
        # vtable[0]=QueryInterface [1]=AddRef [2]=Release
        # vtable[3]=Show  [5]=SetOptions  [9]=GetResult
        vtable = ctypes.cast(
            ctypes.cast(pDialog, ctypes.POINTER(ctypes.c_void_p))[0],
            ctypes.POINTER(ctypes.c_void_p)
        )

        # SetOptions: FOS_PICKFOLDERS(0x20) | FOS_FORCEFILESYSTEM(0x40)
        SetOptions = ctypes.WINFUNCTYPE(ctypes.HRESULT, ctypes.c_void_p, ctypes.c_uint)(vtable[9])
        # vtable index for SetOptions is 9 in IFileDialog
        # 重新用正确偏移：Show=3, SetOptions=9, GetOptions=10, GetResult=20
        # IFileOpenDialog vtable (完整顺序):
        # 0  QueryInterface
        # 1  AddRef
        # 2  Release
        # 3  Show                  ← IModalWindow
        # 4  SetFileTypes
        # 5  SetFileTypeIndex
        # 6  GetFileTypeIndex
        # 7  Advise
        # 8  Unadvise
        # 9  SetOptions
        # 10 GetOptions
        # 11 SetDefaultFolder
        # 12 SetFolder
        # 13 GetFolder
        # 14 GetCurrentSelection
        # 15 SetFileName
        # 16 GetFileName
        # 17 SetTitle
        # 18 SetOkButtonLabel
        # 19 SetFileNameLabel
        # 20 GetResult
        # 21 AddPlace
        # 22 SetDefaultExtension
        # 23 Close
        # 24 SetClientGuid
        # 25 ClearClientData
        # 26 SetFilter
        # 27 GetResults             ← IFileOpenDialog 专有
        # 28 GetSelectedItems

        FOS_PICKFOLDERS    = 0x00000020
        FOS_FORCEFILESYSTEM= 0x00000040

        _SetOptions = ctypes.WINFUNCTYPE(
            ctypes.HRESULT, ctypes.c_void_p, ctypes.c_uint
        )(vtable[9])
        _SetOptions(pDialog.value, FOS_PICKFOLDERS | FOS_FORCEFILESYSTEM)

        # Show(hwnd=0)
        _Show = ctypes.WINFUNCTYPE(
            ctypes.HRESULT, ctypes.c_void_p, wt.HWND
        )(vtable[3])
        hr = _Show(pDialog.value, None)
        if hr != 0:          # 用户取消 hr = 0x800704C7
            # Release
            _Release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtable[2])
            _Release(pDialog.value)
            return None

        # GetResult → IShellItem
        pItem = ctypes.c_void_p()
        _GetResult = ctypes.WINFUNCTYPE(
            ctypes.HRESULT, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)
        )(vtable[20])
        hr = _GetResult(pDialog.value, ctypes.byref(pItem))
        if hr != 0 or not pItem.value:
            return None

        # IShellItem vtable: 0=QI 1=AddRef 2=Release 3=BindToHandler
        #                    4=GetParent 5=GetDisplayName 6=GetAttributes 7=Compare
        SIGDN_FILESYSPATH = ctypes.c_int(0x80058000)
        item_vtable = ctypes.cast(
            ctypes.cast(pItem, ctypes.POINTER(ctypes.c_void_p))[0],
            ctypes.POINTER(ctypes.c_void_p)
        )
        _GetDisplayName = ctypes.WINFUNCTYPE(
            ctypes.HRESULT,
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_wchar_p),
        )(item_vtable[5])

        pszPath = ctypes.c_wchar_p()
        hr = _GetDisplayName(pItem.value, SIGDN_FILESYSPATH.value, ctypes.byref(pszPath))

        result = pszPath.value if hr == 0 else None

        # 释放 pszPath（CoTaskMemFree）
        if pszPath.value:
            ole32.CoTaskMemFree(pszPath)

        # Release IShellItem
        _ItemRelease = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(item_vtable[2])
        _ItemRelease(pItem.value)

        # Release IFileOpenDialog
        _Release = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vtable[2])
        _Release(pDialog.value)

        return (result,) if result else None

    except Exception as e:
        import logging
        logging.getLogger("fsmagnet.system").error(f"_win_pick_folder 失败: {e}")
        return None
    finally:
        ole32.CoUninitialize()


def _win_pick_file(allow_multiple=False, file_types=()) -> tuple | None:
    import ctypes
    import ctypes.wintypes as wt
    import re

    class OPENFILENAMEW(ctypes.Structure):
        _fields_ = [
            ("lStructSize",       wt.DWORD),
            ("hwndOwner",         wt.HWND),
            ("hInstance",         wt.HINSTANCE),
            ("lpstrFilter",       ctypes.c_wchar_p),
            ("lpstrCustomFilter", ctypes.c_wchar_p),
            ("nMaxCustFilter",    wt.DWORD),
            ("nFilterIndex",      wt.DWORD),
            ("lpstrFile",         ctypes.c_wchar_p),
            ("nMaxFile",          wt.DWORD),
            ("lpstrFileTitle",    ctypes.c_wchar_p),
            ("nMaxFileTitle",     wt.DWORD),
            ("lpstrInitialDir",   ctypes.c_wchar_p),
            ("lpstrTitle",        ctypes.c_wchar_p),
            ("Flags",             wt.DWORD),
            ("nFileOffset",       wt.WORD),
            ("nFileExtension",    wt.WORD),
            ("lpstrDefExt",       ctypes.c_wchar_p),
            ("lCustData",         ctypes.c_long),
            ("lpfnHook",          ctypes.c_void_p),
            ("lpTemplateName",    ctypes.c_wchar_p),
        ]

    ole32 = ctypes.WinDLL("ole32")
    ole32.CoInitialize(None)
    try:
        ofn_filter = ""
        if file_types:
            for ft in file_types:
                exts = re.findall(r'\*\.\w+', ft)
                ext_str = ";".join(exts) if exts else "*.*"
                ofn_filter += f"{ft}\0{ext_str}\0"
        else:
            ofn_filter += "所有文件 (*.*)\0*.*\0"
        ofn_filter += "\0"

        OFN_EXPLORER         = 0x00080000
        OFN_FILEMUSTEXIST    = 0x00001000
        OFN_ALLOWMULTISELECT = 0x00000200

        flags = OFN_EXPLORER | OFN_FILEMUSTEXIST
        if allow_multiple:
            flags |= OFN_ALLOWMULTISELECT

        MAX_CHARS = 32768
        buf = ctypes.create_unicode_buffer(MAX_CHARS)

        ofn = OPENFILENAMEW()
        ofn.lStructSize = ctypes.sizeof(OPENFILENAMEW)
        ofn.lpstrFilter = ofn_filter
        ofn.lpstrFile   = ctypes.cast(buf, ctypes.c_wchar_p)
        ofn.nMaxFile    = MAX_CHARS
        ofn.Flags       = flags

        comdlg32 = ctypes.WinDLL("comdlg32")
        if not comdlg32.GetOpenFileNameW(ctypes.byref(ofn)):
            return None

        # ── 正确解析 buffer ──────────────────────────────
        # buf 是 c_wchar_Array，每个元素是一个宽字符
        # 多选时内容: "dir\0file1\0file2\0\0"
        # 单选时内容: "C:\full\path.ext\0"
        parts = []
        i = 0
        while i < MAX_CHARS:
            # 找下一个 \0 的位置
            j = i
            while j < MAX_CHARS and buf[j] != '\0':
                j += 1
            chunk = buf[i:j]          # 切片直接得到字符串片段
            if not chunk:             # 遇到空串说明到了双 \0 结尾
                break
            parts.append("".join(chunk))
            i = j + 1                 # 跳过这个 \0，继续

        if not parts:
            return None
        if len(parts) == 1:
            return (parts[0],)
        # 多选：parts[0] 是目录，后面是文件名
        folder = parts[0]
        return tuple(os.path.join(folder, f) for f in parts[1:])

    except Exception as e:
        import logging
        logging.getLogger("fsmagnet.system").error(f"_win_pick_file 失败: {e}")
        return None
    finally:
        ole32.CoUninitialize()


def request_dialog(dialog_type: int, **kwargs):
    """
    从任意线程直接弹出原生 Windows 对话框。
    不依赖主线程，不需要队列，不需要 tkinter。
    返回 tuple(路径, ...) 或 None。
    """
    if sys.platform != "win32":
        # 非 Windows 回退到 webview 内置对话框
        if webview_window is None:
            return None
        return webview_window.create_file_dialog(
            dialog_type,
            allow_multiple=kwargs.get("allow_multiple", False),
            file_types=kwargs.get("file_types", ()),
        )

    if dialog_type == FOLDER_DIALOG:
        return _win_pick_folder()
    else:
        return _win_pick_file(
            allow_multiple=kwargs.get("allow_multiple", False),
            file_types=kwargs.get("file_types", ()),
        )


def pump_dialogs():
    """保留接口兼容性，win32 原生对话框不需要主线程轮询，此函数为空操作。"""
    pass


def _resource_path(relative: str) -> str:
    """打包后从 _MEIPASS 取资源，开发时从项目根目录取"""
    if hasattr(sys, '_MEIPASS'):
        base = sys._MEIPASS
    else:
        base = os.path.abspath('.')
    return os.path.join(base, relative)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global turbo_session
    from core.task_store import load_tasks
    from config import APP_DATA_DIR

    turbo_session = TurboSession()
    await turbo_session.start()

    # ✅ 恢复上次的任务
    tasks = load_tasks()
    if tasks:
        logger.info(f"恢复 {len(tasks)} 个历史任务...")
        for t in tasks:
            task_id   = t["task_id"]
            save_path = t["save_path"]
            task_type = t.get("task_type", "magnet")
            uri       = t["uri"]
            try:
                if task_type == "torrent":
                    torrent_path = APP_DATA_DIR / "torrents" / f"{task_id}.torrent"
                    if torrent_path.exists():
                        torrent_data = torrent_path.read_bytes()
                        await turbo_session.add_torrent_file(task_id, torrent_data, save_path)
                    else:
                        logger.warning(f"任务 {task_id} 的 .torrent 文件丢失，跳过")
                else:
                    await turbo_session.add_magnet(task_id, uri, save_path)
                logger.info(f"  ✓ 恢复任务 {task_id}")
            except Exception as e:
                logger.error(f"  ✗ 恢复任务 {task_id} 失败: {e}")

    yield

    await turbo_session.stop()


app = FastAPI(title="FSMagnet API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from api.routes.download import router as dl_router
from api.routes.stats    import router as st_router
from api.routes.settings import router as se_router
from api.routes.system   import router as sys_router

app.include_router(dl_router)
app.include_router(st_router)
app.include_router(se_router)
app.include_router(sys_router)


def run_server(port: int = 17878):
    import uvicorn

    # ✅ 统一用 _resource_path，开发和打包都能找到正确路径
    dist_path = Path(_resource_path("ui/dist"))

    if dist_path.exists():
        app.mount(
            "/",
            StaticFiles(directory=str(dist_path), html=True),
            name="frontend",
        )
        print(f"[INFO] 前端静态文件已挂载: {dist_path}")
    else:
        # 打包后找不到 dist，打印路径方便排查
        print(f"[WARN] 未找到前端文件: {dist_path}")

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
    