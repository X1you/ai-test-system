<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-header">
        <span class="login-icon">🧪</span>
        <h1 class="login-title">AI 测试用例生成系统</h1>
        <p class="login-subtitle">请登录以继续</p>
      </div>

      <form class="login-form" @submit.prevent="handleLogin">
        <div class="form-field">
          <label for="username" class="form-label">用户名</label>
          <input
            id="username"
            v-model="form.username"
            type="text"
            class="form-input"
            autocomplete="username"
            :disabled="loading"
            placeholder="请输入用户名"
            required
          />
        </div>

        <div class="form-field">
          <label for="password" class="form-label">密码</label>
          <input
            id="password"
            v-model="form.password"
            type="password"
            class="form-input"
            autocomplete="current-password"
            :disabled="loading"
            placeholder="请输入密码"
            required
          />
        </div>

        <p v-if="errorMsg" class="login-error" role="alert">{{ errorMsg }}</p>

        <button
          type="submit"
          class="login-btn"
          :disabled="loading || !form.username || !form.password"
        >
          {{ loading ? '登录中…' : '登 录' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { api, ApiError } from '../composables/useApi'
import { setAuth } from '../composables/useAuth'

const router = useRouter()
const route = useRoute()

const form = reactive({
  username: '',
  password: '',
})
const loading = ref(false)
const errorMsg = ref('')

async function handleLogin() {
  loading.value = true
  errorMsg.value = ''

  try {
    const resp = await api.post('/auth/login', {
      json: {
        username: form.username,
        password: form.password,
      },
    })

    // 持久化 token + 用户信息
    setAuth(resp.access_token, {
      username: resp.username,
      role: resp.role,
    })

    // 跳转到 redirect 参数或首页
    const redirect = route.query.redirect || '/'
    router.push(redirect)
  } catch (e) {
    if (e instanceof ApiError) {
      if (e.status === 429) {
        errorMsg.value = e.data?.detail || '登录尝试过于频繁，请稍后再试'
      } else if (e.status === 401) {
        errorMsg.value = '用户名或密码错误'
      } else {
        errorMsg.value = e.data?.detail || `登录失败（${e.status}）`
      }
    } else {
      errorMsg.value = '网络错误，请检查连接后重试'
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: var(--space-xl);
  background: var(--bg-inset);
}

.login-card {
  width: 100%;
  max-width: 400px;
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  padding: var(--space-3xl);
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.06);
}
[data-theme="dark"] .login-card {
  border-color: hsl(150 40% 15%);
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.5), 0 0 16px hsl(150 100% 50% / 0.08);
}

.login-header {
  text-align: center;
  margin-bottom: var(--space-2xl);
}

.login-icon {
  font-size: 48px;
  line-height: 1;
}

.login-title {
  margin: var(--space-md) 0 var(--space-xs);
  font-size: 1.4rem;
  font-weight: 700;
  color: var(--text-primary);
}
[data-theme="dark"] .login-title {
  text-shadow: var(--text-glow);
  letter-spacing: 0;
}

.login-subtitle {
  margin: 0;
  font-size: 0.9rem;
  color: var(--text-secondary);
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-lg);
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.form-label {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-secondary);
}

.form-input {
  padding: var(--space-md) var(--space-lg);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  font-size: 0.95rem;
  color: var(--text-primary);
  background: var(--bg-surface-raised);
  transition: border-color var(--duration-fast) var(--ease-out),
              box-shadow var(--duration-fast) var(--ease-out);
}

.form-input:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-subtle);
}

.form-input:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.login-error {
  margin: 0;
  padding: var(--space-sm) var(--space-md);
  font-size: 0.85rem;
  color: #e53e3e;
  background: rgba(229, 62, 62, 0.08);
  border-radius: var(--radius-sm);
}

.login-btn {
  padding: var(--space-md) var(--space-lg);
  border: none;
  border-radius: var(--radius-md);
  font-size: 1rem;
  font-weight: 600;
  color: var(--accent-text);
  background: var(--accent);
  cursor: pointer;
  transition: background var(--duration-fast) var(--ease-out),
              transform var(--duration-fast) var(--ease-out);
}
[data-theme="dark"] .login-btn {
  box-shadow: var(--shadow-accent);
}
[data-theme="dark"] .login-btn:hover:not(:disabled) {
  box-shadow: var(--shadow-accent-lg);
}

.login-btn:hover:not(:disabled) {
  background: var(--accent-hover);
}

.login-btn:active:not(:disabled) {
  transform: scale(0.98);
}

.login-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.login-btn:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
</style>
