import axios from 'axios'

const http = axios.create({
  baseURL: '/api',
  timeout: 500000,
})

// ── 下载管理 ──────────────────────────────────────────────
export const downloadApi = {
  add: (uri, savePath) =>
    http.post('/download/add', { uri, save_path: savePath }).then(r => r.data),

  // ✅ 直接传路径字符串，后端读文件，不走 file:// 协议
  addTorrent: (filePath, savePath) =>
    http.post('/download/add-torrent-path', {
      file_path: filePath,
      save_path: savePath,
    }).then(r => r.data),

  list: () =>
    http.get('/download/list').then(r => r.data),

  remove: (taskId, deleteFiles = false) =>
    http.delete(`/download/${taskId}`, { params: { delete_files: deleteFiles } }).then(r => r.data),

  pause: (taskId) =>
    http.post(`/download/${taskId}/pause`).then(r => r.data),

  resume: (taskId) =>
    http.post(`/download/${taskId}/resume`).then(r => r.data),
}

// ── 设置 ──────────────────────────────────────────────────
export const settingsApi = {
  get()        { return http.get('/settings/').then(r => r.data) },
  update(data) { return http.patch('/settings/', data).then(r => r.data) },
}

// ── 统计 REST（SSE 降级时使用） ───────────────────────────
export const statsApi = {
  get() { return http.get('/stats/').then(r => r.data) },
}

// ── 系统对话框 ────────────────────────────────────────────
export const systemApi = {
  pickFolder:  () => http.get('/system/pick-folder').then(r => r.data),
  pickTorrent: () => http.get('/system/pick-torrent').then(r => r.data),
}

// ── SSE 实时推送 ──────────────────────────────────────────
export function subscribeStats(onData) {
  const es = new EventSource('/api/stats/stream')

  es.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data)
      if (Object.keys(data).length) onData(data)
    } catch (_) {}
  }

  es.onerror = () => {}

  return es
}