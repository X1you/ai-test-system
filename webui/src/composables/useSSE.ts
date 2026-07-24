/**
 * SSE 连接管理
 * EventSource 实时推送 + 心跳超时检测 + 降级轮询 + 网络恢复重连
 */

import { ref, onUnmounted, type Ref } from 'vue'

export interface SSEHandlers {
  onStepDone?: (data: any) => void
  onLog?: (data: any) => void
  onPaused?: (data: any) => void
  onTerminal?: (event: string, data: any) => void
  onStatusChange?: (status: SSEStatus) => void
}

export type SSEStatus = 'connected' | 'reconnecting' | 'polling' | 'disconnected'

const HEARTBEAT_TIMEOUT = 45000 // 45s 无 ping 判定连接已死
const MAX_RECONNECT = 5
const POLL_BASE_INTERVAL = 3000

export function useSSE(pipelineId: string, handlers: SSEHandlers) {
  const connected = ref(false)
  const status: Ref<SSEStatus> = ref('disconnected')

  let es: EventSource | null = null
  let reconnectCount = 0
  let pollTimer: ReturnType<typeof setInterval> | null = null
  let heartbeatTimer: ReturnType<typeof setTimeout> | null = null
  let usingPolling = false

  function setStatus(s: SSEStatus) {
    status.value = s
    handlers.onStatusChange?.(s)
  }

  function clearHeartbeat() {
    if (heartbeatTimer) {
      clearTimeout(heartbeatTimer)
      heartbeatTimer = null
    }
  }

  function resetHeartbeat() {
    clearHeartbeat()
    heartbeatTimer = setTimeout(() => {
      // 心跳超时 → 断开并降级
      disconnectSSE()
      startPolling()
    }, HEARTBEAT_TIMEOUT)
  }

  function disconnectSSE() {
    if (es) {
      es.close()
      es = null
    }
    clearHeartbeat()
    connected.value = false
  }

  function connect() {
    if (!pipelineId) return
    disconnectSSE()
    stopPolling()

    const url = `/api/v1/pipeline/${pipelineId}/stream`
    setStatus('reconnecting')

    try {
      es = new EventSource(url)
    } catch {
      startPolling()
      return
    }

    es.onopen = () => {
      connected.value = true
      reconnectCount = 0
      setStatus('connected')
      resetHeartbeat()
    }

    es.addEventListener('step_done', (e) => {
      resetHeartbeat()
      try { handlers.onStepDone?.(JSON.parse((e as MessageEvent).data)) } catch {}
    })

    es.addEventListener('log', (e) => {
      resetHeartbeat()
      try { handlers.onLog?.(JSON.parse((e as MessageEvent).data)) } catch {}
    })

    es.addEventListener('paused', (e) => {
      resetHeartbeat()
      try { handlers.onPaused?.(JSON.parse((e as MessageEvent).data)) } catch {}
    })

    // 终态事件
    for (const evt of ['done', 'error', 'cancelled']) {
      es.addEventListener(evt, (e) => {
        try { handlers.onTerminal?.(evt, JSON.parse((e as MessageEvent).data || '{}')) } catch {}
        disconnectSSE()
        setStatus('disconnected')
      })
    }

    // 心跳
    es.addEventListener('ping', () => {
      resetHeartbeat()
    })

    es.onerror = () => {
      connected.value = false
      disconnectSSE()

      if (reconnectCount < MAX_RECONNECT) {
        reconnectCount++
        setStatus('reconnecting')
        setTimeout(connect, 3000)
      } else {
        startPolling()
      }
    }
  }

  async function pollOnce() {
    try {
      const resp = await fetch(`/api/v1/pipeline/${pipelineId}/progress`)
      if (!resp.ok) return
      const data = await resp.json()
      setStatus('polling')
      // 把轮询数据当作 step_done 处理
      handlers.onStepDone?.(data)
    } catch {}
  }

  function startPolling() {
    if (usingPolling) return
    usingPolling = true
    setStatus('polling')
    pollOnce()
    pollTimer = setInterval(pollOnce, POLL_BASE_INTERVAL)
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
    usingPolling = false
  }

  function disconnect() {
    disconnectSSE()
    stopPolling()
    setStatus('disconnected')
  }

  // 网络恢复后尝试重连 SSE
  function onOnline() {
    if (usingPolling) {
      reconnectCount = 0
      connect()
    }
  }
  window.addEventListener('online', onOnline)

  onUnmounted(() => {
    disconnect()
    window.removeEventListener('online', onOnline)
  })

  return { connected, status, connect, disconnect }
}
