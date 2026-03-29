<template>
  <div class="overlay" @click.self="$emit('close')">
    <div class="modal">
      <div class="modal-header">
        <span>⚙ 设置</span>
        <button class="btn-close" @click="$emit('close')">✕</button>
      </div>

      <div class="modal-body">

        <!-- ── 主题选择 ── -->
        <section class="section">
          <div class="section-title">🎨 界面主题</div>
          <div class="theme-grid">
            <button
              v-for="t in themes"
              :key="t.value"
              class="theme-btn"
              :class="{ active: cfg.theme === t.value }"
              @click="selectTheme(t.value)"
            >
              <span class="theme-preview" :data-preview="t.value"></span>
              <span class="theme-label">{{ t.label }}</span>
              <span v-if="cfg.theme === t.value" class="theme-check">✓</span>
            </button>
          </div>
        </section>

        <!-- ── 下载优化 ── -->
        <section class="section">
          <div class="section-title">🚀 下载优化</div>
          <div class="field">
            <label>最大连接数</label>
            <input v-model.number="cfg.connections_limit" type="number" min="50" max="3000" />
          </div>
          <div class="field">
            <label>磁盘缓存 (MB)</label>
            <input v-model.number="cfg.cache_mb" type="number" min="64" max="8192" />
          </div>
          <div class="field">
            <label>上传限速 (KB/s，0=不限)</label>
            <input v-model.number="cfg.upload_limit_kb" type="number" min="0" />
          </div>
        </section>

        <!-- ── 网络 ── -->
        <section class="section">
          <div class="section-title">🔒 网络</div>
          <div class="field toggle">
            <label>强制协议加密（绕过 ISP 限速）</label>
            <input type="checkbox" v-model="cfg.force_encryption" />
          </div>
          <div class="field toggle">
            <label>启用 DHT</label>
            <input type="checkbox" v-model="cfg.enable_dht" />
          </div>
          <div class="field toggle">
            <label>启用 UPnP（自动端口映射）</label>
            <input type="checkbox" v-model="cfg.enable_upnp" />
          </div>
          <div class="field toggle">
            <label>启用局域网发现 (LSD)</label>
            <input type="checkbox" v-model="cfg.enable_lsd" />
          </div>
        </section>
      </div>

      <div class="modal-footer">
        <button class="btn-cancel" @click="$emit('close')">取消</button>
        <button class="btn-confirm" :disabled="saving" @click="save">
          {{ saving ? '保存中...' : '保存设置' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, inject } from 'vue'
import { settingsApi } from '../api/index.js'

const emit   = defineEmits(['close'])
const saving = ref(false)
const error  = ref('')

// 从 App.vue provide 注入主题应用函数
const applyTheme = inject('applyTheme')

const themes = [
  { value: 'dark',   label: '🌑 黑色' },
  { value: 'light',  label: '☀️ 白色' },
  { value: 'blue',   label: '🌊 蓝色' },
  { value: 'yellow', label: '🌟 黄色' },
]

const cfg = ref({
  theme:             'dark',
  connections_limit: 500,
  cache_mb:          512,
  upload_limit_kb:   0,
  force_encryption:  false,
  enable_dht:        true,
  enable_upnp:       true,
  enable_lsd:        true,
})

function selectTheme(value) {
  cfg.value.theme = value
  // 实时预览：立即应用，不需要等保存
  applyTheme(value)
}

async function save() {
  saving.value = true
  error.value  = ''
  try {
    await settingsApi.save(cfg.value)
    applyTheme(cfg.value.theme)
    emit('close')
  } catch (e) {
    error.value = '保存失败：' + e.message
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  try {
    const data = await settingsApi.get()
    if (data) Object.assign(cfg.value, data)
  } catch {}
})
</script>

<style scoped>
/* ── 主题选择器 ── */
.theme-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin-top: 8px;
}

.theme-btn {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 10px 6px 8px;
  border-radius: 10px;
  border: 2px solid transparent;
  background: var(--bg-card);
  cursor: pointer;
  transition: border-color 0.2s, transform 0.15s;
}
.theme-btn:hover  { transform: translateY(-2px); border-color: var(--accent); }
.theme-btn.active { border-color: var(--accent); }

.theme-preview {
  width: 40px;
  height: 28px;
  border-radius: 6px;
  display: block;
  border: 1px solid rgba(255,255,255,0.08);
}
/* 四种主题的预览色块 */
.theme-preview[data-preview="dark"]   { background: linear-gradient(135deg,#1a1d2e 50%,#7c8cff 100%); }
.theme-preview[data-preview="light"]  { background: linear-gradient(135deg,#f0f2f8 50%,#4f7cff 100%); }
.theme-preview[data-preview="blue"]   { background: linear-gradient(135deg,#0d1b3e 50%,#00d4ff 100%); }
.theme-preview[data-preview="yellow"] { background: linear-gradient(135deg,#1c1a0e 50%,#f5c518 100%); }

.theme-label {
  font-size: 11px;
  color: var(--text-sub);
  white-space: nowrap;
}
.theme-check {
  position: absolute;
  top: 4px; right: 6px;
  font-size: 11px;
  color: var(--accent);
  font-weight: bold;
}
</style>