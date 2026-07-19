import { ref, onUnmounted } from 'vue'

/**
 * SSE 连接管理
 * 自动重连 + 降级轮询
 */
export function useSSE(pipelineId, handlers = {}) {
  const connected = ref(false)
  const usingFallback = ref(false)

  let es = null
  let reconnectCount = 0
  let pollTimer = null
  const MAX_RECONNECT = 5
  const POLL_INTERVAL = 3000

  function connect() {
    if (!pipelineId) return

    const url = `/api/v1/pipeline/${pipelineId}/stream`
    es = new EventSource(url)

    es.onopen = () => {
      connected.value = true
      reconnectCount = 0
    }

    // 步骤完成
    es.addEventListener('step_done', (e) => {
      const data = JSON.parse(e.data)
      handlers.onStepDone?.(data)
    })

    // 日志
    es.addEventListener('log', (e) => {
      const data = JSON.parse(e.data)
      handlers.onLog?.(data)
    })

    // 终态事件
    for (const evt of ['done', 'error', 'cancelled']) {
      es.addEventListener(evt, (e) => {
        const data = JSON.parse(e.data)
        handlers.onTerminal?.(evt, data)
        close()
      })
    }

    // 心跳（忽略）
    es.addEventListener('ping', () => {})

    // 错误 → 重连或降级
    es.onerror = () => {
      connected.value = false
      es?.close()
      es = null

      if (reconnectCount < MAX_RECONNECT) {
        reconnectCount++
        setTimeout(connect, 3000)
      } else {
        startFallbackPolling()
      }
    }
  }

  function startFallbackPolling() {
    usingFallback.value = true
    pollTimer = setInterval(async () => {
      try {
        const resp = await fetch(`/api/v1/pipeline/${pipelineId}/progress`)
        if (!resp.ok) return
        const data = await resp.json()
        handlers.onPoll?.(data)
        // 终态停止轮询
        if (['done', 'error', 'cancelled'].includes(data.status)) {
          stopFallbackPolling()
          handlers.onTerminal?.(data.status, data)
        }
      } catch { /* ignore */ }
    }, POLL_INTERVAL)
  }

  function stopFallbackPolling() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
    usingFallback.value = false
  }

  function close() {
    es?.close()
    es = null
    connected.value = false
    stopFallbackPolling()
  }

  onUnmounted(close)

  return { connected, usingFallback, connect, close }
}
