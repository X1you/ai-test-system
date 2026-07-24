<script setup lang="ts">
/**
 * WebhookPanel — 集成与 Webhook 管理面板
 *
 * 显示：
 *  - Webhook 接收端点 URL（供外部平台配置）
 *  - 全局签名密钥状态（WEBHOOK_SECRET）
 *  - 已注册的适配器平台列表
 */
import { onMounted, ref } from 'vue'
import { apiGet } from '@/composables/useApi'
import { API } from '@/types/api'

interface WebhookStatus {
  secret_configured: boolean
  platforms: string[]
  webhook_url_template: string
}

const loading = ref(false)
const status = ref<WebhookStatus | null>(null)
const error = ref<string | null>(null)

onMounted(async () => {
  loading.value = true
  try {
    status.value = await apiGet(API.WEBHOOKS.STATUS)
  } catch (e: any) {
    error.value = e?.message || '获取 Webhook 状态失败'
  } finally {
    loading.value = false
  }
})

const baseUrl = typeof window !== 'undefined' ? window.location.origin : ''
</script>

<template>
  <section class="wh-panel">
    <h3 class="wh-title">Webhook 集成</h3>
    <p class="wh-desc">
      外部测试管理平台（如 TestRail）可通过 Webhook 向本系统推送事件。
      配置以下 URL 到外部平台的 Webhook 设置中即可。
    </p>

    <div v-if="loading" class="wh-loading">加载中…</div>

    <div v-else-if="error" class="wh-error">{{ error }}</div>

    <template v-else-if="status">
      <!-- 密钥状态 -->
      <div class="wh-row">
        <span class="wh-label">签名密钥</span>
        <span
          class="wh-badge"
          :class="status.secret_configured ? 'is-ok' : 'is-warn'"
        >
          {{ status.secret_configured ? '已配置' : '未配置' }}
        </span>
        <span class="wh-hint">
          {{
            status.secret_configured
              ? 'WEBHOOK_SECRET 环境变量已设置，签名验证生效'
              : '请设置 WEBHOOK_SECRET 环境变量以启用 HMAC 签名验证'
          }}
        </span>
      </div>

      <!-- Webhook URL -->
      <div class="wh-row">
        <span class="wh-label">接收端点</span>
        <code class="wh-url">{{ baseUrl }}/api/v1/webhooks/{platform}</code>
        <span class="wh-hint">
          将 <code>{platform}</code> 替换为实际平台名（如 <code>testrail</code>）
        </span>
      </div>

      <!-- 已注册平台 -->
      <div class="wh-row">
        <span class="wh-label">已注册平台</span>
        <div v-if="status.platforms.length > 0" class="wh-platforms">
          <span
            v-for="p in status.platforms"
            :key="p"
            class="wh-platform-tag"
          >{{ p }}</span>
        </div>
        <span v-else class="wh-hint">暂无已注册的适配器平台</span>
      </div>
    </template>
  </section>
</template>

<style scoped>
.wh-panel {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}
.wh-title {
  font-size: var(--text-md);
  font-weight: var(--weight-bold);
  margin: 0;
}
.wh-desc {
  font-size: var(--text-xs);
  color: var(--muted-fg);
  margin: 0;
  line-height: 1.5;
}
.wh-loading,
.wh-error {
  font-size: var(--text-sm);
  color: var(--muted-fg);
}
.wh-error {
  color: #dc2626;
}

.wh-row {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  flex-wrap: wrap;
  padding: 0.5rem 0;
  border-top: 1px solid var(--border-light);
}
.wh-label {
  font-size: var(--text-sm);
  font-weight: var(--weight-semibold);
  color: var(--muted-fg);
  min-width: 5rem;
  flex-shrink: 0;
}
.wh-badge {
  padding: 0.15rem 0.55rem;
  font-size: 0.7rem;
  font-weight: 600;
  border-radius: var(--radius-full);
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--muted-fg);
}
.wh-badge.is-ok {
  color: #10b981;
  border-color: #10b98140;
  background: #10b9810d;
}
.wh-badge.is-warn {
  color: #f59e0b;
  border-color: #f59e0b40;
  background: #f59e0b0d;
}
.wh-hint {
  font-size: 0.7rem;
  color: var(--muted-fg);
  flex-basis: 100%;
  margin-top: 0.2rem;
}
.wh-hint code {
  font-family: var(--font-mono, monospace);
  font-size: 0.7rem;
  background: var(--hover-bg);
  padding: 0 0.25rem;
  border-radius: 2px;
}

.wh-url {
  font-family: var(--font-mono, monospace);
  font-size: 0.72rem;
  background: var(--hover-bg);
  padding: 0.25rem 0.5rem;
  border-radius: var(--radius-sm);
  color: var(--fg);
  word-break: break-all;
}

.wh-platforms {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}
.wh-platform-tag {
  padding: 0.2rem 0.55rem;
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--fg);
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-full);
}
</style>