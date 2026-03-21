<template>
  <div class="overlay" @click.self="$emit('close')">
    <div class="modal">
      <div class="modal-header">
        <span>⚙ 设置</span>
        <button class="btn-close" @click="$emit('close')">✕</button>
      </div>

      <div class="modal-body">
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
import { ref, onMounted } from 'vue'
import { settingsApi } from '../api/index.js'

const emit   = defineEmits(['close'])
const saving = ref(false)
const error  = ref('')

const cfg = ref({
  connections_limit: 500,
  cache_mb:          512,
  upload_limit_kb:   50,
  force_encryption:  true,
  enable_dht:        true,
  enable_upnp:       true,
  enable_lsd:        true,
})

onMounted(async () => {
  try {
    const res = await settingsApi.get()
    Object.assign(cfg.value, res.settings)
  } catch (e) {
    console.error('[Settings] 加载失败', e)
  }
})

async function save() {
  saving.value = true
  error.value  = ''
  try {
    await settingsApi.update(cfg.value)
    emit('close')
  } catch (e) {
    console.error('[Settings] 保存失败', e)
    error.value = e?.response?.data?.detail ?? '保存失败，请查看控制台'
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.65);
  display: flex; align-items: center; justify-content: center; z-index: 100;
}
.modal {
  background: #161822; border-radius: 14px;
  border: 1px solid #2a2d3e; width: 480px; max-width: 95vw;
}
.modal-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 18px 20px; border-bottom: 1px solid #2a2d3e;
  font-size: 15px; font-weight: 600; color: #e2e8f0;
}
.btn-close { background: none; border: none; color: #555; font-size: 16px; cursor: pointer; }
.btn-close:hover { color: #fff; }

.modal-body {
  padding: 20px; display: flex; flex-direction: column;
  gap: 20px; max-height: 60vh; overflow-y: auto;
}
.section { display: flex; flex-direction: column; gap: 12px; }
.section-title { font-size: 12px; color: #7c8cff; font-weight: 700; letter-spacing: 0.05em; }

.field {
  display: flex; justify-content: space-between; align-items: center;
  font-size: 13px; color: #aaa;
}
.field input[type="number"] {
  background: #0f1117; border: 1px solid #2a2d3e;
  border-radius: 6px; color: #e2e8f0; padding: 5px 10px;
  width: 120px; text-align: right; outline: none;
}
.field.toggle input[type="checkbox"] {
  width: 18px; height: 18px; accent-color: #7c8cff; cursor: pointer;
}

.modal-footer {
  display: flex; justify-content: flex-end; align-items: center; gap: 10px;
  padding: 16px 20px; border-top: 1px solid #2a2d3e;
}
.error-msg { color: #f87171; font-size: 12px; margin-right: auto; }
.btn-cancel {
  background: #1e2130; border: none; color: #aaa;
  border-radius: 8px; padding: 8px 20px; cursor: pointer;
}
.btn-confirm {
  background: #7c8cff; border: none; color: #fff;
  border-radius: 8px; padding: 8px 20px; cursor: pointer; font-weight: 600;
}
.btn-confirm:disabled { opacity: 0.5; cursor: not-allowed; }
</style>