import axios from 'axios'

const http = axios.create({
  baseURL: '/api',
  timeout: 10000,
})

// ── 下载管理 ──────────────────────────────────────────
export const downloadApi = {
  /** 获取任务列表 */
  list() {
    return http.get('/download/list')
  },

  /** 添加磁力链 */
  add(uri, save_path) {
    return http.post('/download/add', { uri, save_path })
  },

  /** 暂停 */
  pause(id) {
    return http.post(`/download/${id}/pause`)
  },

  /** 继续 */
  resume(id) {
    return http.post(`/download/${id}/resume`)
  },

  /** 删除 */
  remove(id) {
    return http.delete(`/download/${id}`)
  },
}

// ── 设置 ──────────────────────────────────────────────
export const settingsApi = {
  /** 读取设置 */
  get() {
    return http.get('/settings/')
  },

  /** 更新设置 */
  update(data) {
    return http.patch('/settings/', data)
  },
}

// ── SSE 实时推送 ───────────────────────────────────────
/**
 * 订阅后端 SSE 统计流
 * @param {(data: object) => void} onData  收到数据的回调
 * @returns {EventSource}  调用 .close() 断开
 *
 * 后端推送格式（每秒一次）：
 * data: {"tasks":[...], "global_speed": 102400, "global_ul": 4096, "dht_nodes": 312}
 */
export function subscribeStats(onData) {
  const es = new EventSource('/api/stats/stream')

  es.onmessage = (e) => {
    try {
      onData(JSON.parse(e.data))
    } catch (_) {}
  }

  es.onerror = () => {
    // SSE 断线自动重连，不需要手动处理
  }

  return es
}
