import { ref, onUnmounted } from 'vue'

/**
 * 轮询 hook
 * @param {Function} fn - 异步函数
 * @param {number} interval - 间隔 ms
 * @param {Object} opts - { immediate: true, stopWhen: (data) => bool }
 */
export function usePolling(fn, interval = 5000, opts = {}) {
  const { immediate = true, stopWhen = null } = opts
  const isActive = ref(false)
  let timer = null

  async function tick() {
    try {
      const data = await fn()
      if (stopWhen && stopWhen(data)) {
        stop()
      }
    } catch { /* ignore */ }
  }

  function start() {
    if (isActive.value) return
    isActive.value = true
    if (immediate) tick()
    timer = setInterval(tick, interval)
  }

  function stop() {
    isActive.value = false
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }

  onUnmounted(stop)

  return { isActive, start, stop, tick }
}
