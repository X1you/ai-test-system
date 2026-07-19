<template>
  <div class="knowledge-view">
    <h1>📚 知识库管理</h1>

    <!-- 动态配置卡片（Sprint 6.1 核心） -->
    <div class="config-card">
      <h2>动态配置</h2>
      <p class="card-desc">配置知识库连接，保存后立即热切换生效</p>

      <div class="form-group">
        <label>Provider 类型</label>
        <select v-model="form.provider_type">
          <option value="mcp_filesystem">MCP Filesystem（本地 Vault）</option>
          <option value="obsidian_api">Obsidian API（远程）</option>
        </select>
      </div>

      <div v-if="form.provider_type === 'obsidian_api'" class="form-group">
        <label>连接 URL</label>
        <input v-model="form.connection_url" placeholder="http://127.0.0.1:27124" />
      </div>

      <div v-if="form.provider_type === 'obsidian_api'" class="form-group">
        <label>Auth Token</label>
        <input v-model="form.auth_token" type="password" placeholder="可选" />
      </div>

      <div v-if="form.provider_type === 'mcp_filesystem'" class="form-group">
        <label>Vault 路径</label>
        <input v-model="form.vault_path" placeholder="/path/to/obsidian/vault" />
      </div>

      <button class="btn-save" :disabled="saving" @click="saveConfig">
        {{ saving ? '保存中...' : '💾 保存并热切换' }}
      </button>

      <div v-if="message" :class="['msg', message.startsWith('配置已生效') ? 'msg-ok' : 'msg-err']">
        {{ message }}
      </div>
    </div>

    <!-- 当前生效配置 -->
    <div class="config-card">
      <h2>当前生效配置</h2>
      <button class="btn-refresh" @click="loadCurrentConfig">🔄 刷新</button>
      <div v-if="currentConfig" class="config-info">
        <div v-if="currentConfig.configured">
          <p><strong>Provider:</strong> {{ currentConfig.provider_type }}</p>
          <p v-if="currentConfig.connection_url"><strong>URL:</strong> {{ currentConfig.connection_url }}</p>
          <p v-if="currentConfig.vault_path"><strong>Vault:</strong> {{ currentConfig.vault_path }}</p>
          <p><strong>Token:</strong> {{ currentConfig.auth_token_masked }}</p>
          <p><strong>更新时间:</strong> {{ currentConfig.updated_at }}</p>
        </div>
        <div v-else>
          <p class="dummy-hint">⚠️ 未配置（Dummy 模式）— 请在上方配置知识库连接</p>
        </div>
      </div>
    </div>

    <!-- 知识库统计 -->
    <div class="config-card">
      <h2>知识库统计</h2>
      <button class="btn-refresh" @click="loadStatus">🔄 刷新</button>
      <div v-if="status" class="status-info">
        <p v-if="!status.enabled" class="dummy-hint">知识库未启用</p>
        <div v-else>
          <p><strong>总条目:</strong> {{ status.total }}</p>
          <div v-if="status.categories" class="categories">
            <span v-for="(count, cat) in status.categories" :key="cat" class="cat-badge">
              {{ cat }}: {{ count }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const form = ref({
  provider_type: 'mcp_filesystem',
  connection_url: '',
  auth_token: '',
  vault_path: '',
})
const saving = ref(false)
const message = ref('')
const currentConfig = ref(null)
const status = ref(null)

async function saveConfig() {
  saving.value = true
  message.value = ''
  try {
    const resp = await fetch('/api/v1/knowledge/update_config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form.value),
    })
    const data = await resp.json()
    message.value = data.message || (data.status === 'success' ? '配置已生效' : '保存失败')
    if (data.status === 'success') {
      loadCurrentConfig()
      loadStatus()
    }
  } catch (e) {
    message.value = `网络错误: ${e.message}`
  } finally {
    saving.value = false
  }
}

async function loadCurrentConfig() {
  try {
    const resp = await fetch('/api/v1/knowledge/current_config')
    currentConfig.value = await resp.json()
  } catch { /* ignore */ }
}

async function loadStatus() {
  try {
    const resp = await fetch('/api/v1/knowledge/status')
    status.value = await resp.json()
  } catch { /* ignore */ }
}

onMounted(() => {
  loadCurrentConfig()
  loadStatus()
})
</script>

<style scoped>
.knowledge-view { max-width: 720px; margin: 0 auto; }
h1 { font-size: 24px; margin-bottom: 20px; }
.config-card {
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 16px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}
.config-card h2 { font-size: 16px; margin-bottom: 8px; }
.card-desc { font-size: 13px; color: #666; margin-bottom: 16px; }
.form-group { margin-bottom: 12px; }
.form-group label { display: block; font-size: 13px; font-weight: 500; margin-bottom: 4px; color: #555; }
.form-group input, .form-group select {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
}
.form-group input:focus, .form-group select:focus { outline: none; border-color: #1a73e8; }
.btn-save {
  width: 100%;
  padding: 10px;
  background: #1a73e8;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  margin-top: 8px;
}
.btn-save:hover:not(:disabled) { background: #1557b0; }
.btn-save:disabled { background: #ccc; cursor: not-allowed; }
.btn-refresh {
  background: #f0f0f0;
  border: none;
  border-radius: 6px;
  padding: 6px 12px;
  font-size: 13px;
  cursor: pointer;
  margin-bottom: 12px;
}
.btn-refresh:hover { background: #e0e0e0; }
.msg { margin-top: 12px; font-size: 14px; padding: 8px 12px; border-radius: 6px; }
.msg-ok { background: #e6f4ea; color: #188038; }
.msg-err { background: #fce8e6; color: #d93025; }
.config-info p { font-size: 14px; margin-bottom: 4px; }
.dummy-hint { color: #f9ab00; font-size: 14px; }
.status-info p { font-size: 14px; margin-bottom: 4px; }
.categories { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.cat-badge {
  background: #e8f0fe;
  color: #1a73e8;
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
}
</style>
