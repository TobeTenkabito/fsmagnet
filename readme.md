# 🧲 FSMagnet

> **纯 Vibe Coding 产物** — 本项目 100% 由 AI 辅助编写，从架构到每一行代码均通过自然语言描述生成，无一行手写逻辑。

---

## 📖 项目简介

FSMagnet 是一个轻量级的 **磁力链接 / DHT 资源嗅探与下载工具**，基于 Python 构建，支持打包为单文件 `.exe` 直接运行，无需安装任何依赖。

---

## ✨ 项目特点

### 🪶 极度轻量，无需安装
- 单文件 `.exe`，双击即用，无需 Java、.NET 或其他运行时
- 内存占用极低，不像 qBittorrent / Transmission 常驻后台吃资源
- 无复杂的配置文件，开箱即用

### 🔍 DHT 网络嗅探
- 直接接入 BitTorrent DHT 网络，被动嗅探全网实时资源
- 无需 Tracker 服务器，纯去中心化工作
- 支持 DHT 状态持久化，重启后自动恢复节点表

### 🖥️ 原生 Windows UI
- 使用 Win32 原生对话框（`IFileOpenDialog`），无 Qt/Tk 依赖
- 文件选择、目录选择体验与系统原生一致
- 打包体积远小于携带 Qt 的 qBittorrent（qB 安装包 ~100MB vs 本项目数 MB 级）

### 🧩 架构简洁
- 纯 Python 实现，代码结构扁平，易于阅读和二次修改
- Server/Client 分离，支持多线程并发下载任务
- 无数据库依赖，状态以轻量文件格式持久化

---

## ⚖️ 与主流工具对比

| 特性 | FSMagnet    | qBittorrent | Transmission | BitComet |
|------|-------------|-------------|--------------|----------|
| 安装包大小 | 20~30 MB    | ~100 MB | ~20 MB | ~30 MB |
| 需要安装 | ❌ 免安装       | ✅ | ✅ | ✅ |
| DHT 嗅探 | ✅ 主动嗅探      | ⚠️ 仅用于下载 | ⚠️ 仅用于下载 | ⚠️ 仅用于下载 |
| 上传/做种 | ✅           | ✅ | ✅ | ✅ |
| Web UI | ❌           | ✅ | ✅ | ✅ |
| RSS 订阅 | ❌           | ✅ | ❌ | ✅ |
| 内存占用 | 极低          | 中等 | 低 | 中等 |
| 跨平台 | ⚠️ 仅 Windows | ✅ | ✅ | ❌ |
| 开源 | ✅           | ✅ | ✅ | ❌ |

---

## ⚠️ 已知限制 / 短处

> 本项目定位为**轻量嗅探+下载工具**，并非全功能 BT 客户端，以下功能**刻意不做或暂未实现**：

- ❌ **无 Web UI / 远程控制** — 不能像 qB 一样挂机远程管理
- ❌ **仅支持 Windows** — 依赖 Win32 API，Linux / macOS 暂不支持
- ❌ **无速度限制 / 计划任务** — 缺少 qB 的精细流控功能
- ❌ **无 RSS 自动订阅** — 不能像 qB 一样自动追番
- ⚠️ **DHT 冷启动较慢** — 首次运行需要时间加入 DHT 网络，节点表为空时嗅探效率低
- ⚠️ **稳定性未经大规模验证** — Vibe Coding 产物，边角 case 可能存在未知 bug

---

## 🚀 快速开始

### 直接运行 exe
```
FSMagnet.exe
```

### 从源码运行
```bash
git clone https://github.com/yourname/fsmagnet.git
cd fsmagnet
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### 打包为 exe
```bash
pip install pyinstaller
pyinstaller --onefile main.py
```

---

## 🛠️ 技术栈

- **Python 3.13+**
- **asyncio** — 异步 DHT 网络通信
- **ctypes / Win32 API** — 原生文件对话框（`IFileOpenDialog`）
- **PyInstaller** — 打包为单文件 exe

---

## 🤖 关于 Vibe Coding

本项目是一次完整的 **Vibe Coding** 实践：

> *"不写代码，只描述意图，让 AI 把想法变成可运行的程序。"*

从 DHT 协议实现、多线程架构、Win32 对话框集成，到打包脚本，**全程通过自然语言与 AI 对话完成**，作者本人未手动编写任何业务逻辑代码。

这证明了在 2026 年，一个有想法但不想写代码的人，完全可以构建出一个功能完整的实用工具。

**但是，对于想从事专业软件开发的人，依旧需要具备基础知识**

---

## 📄 License

MIT License — 随便用，随便改，出了问题自负。