/**
 * 可清理的轮询 hook
 */
import { onUnmounted } from 'vue'

export function usePolling(fn: () => void, interval: number) {
  let timer: ReturnType<typeof setInterval> | null = null

  function start() {
    if (timer) return
    timer = setInterval(fn, interval)
  }

  function stop() {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  }

  function restart(newInterval?: number) {
    stop()
    if (newInterval) interval = newInterval
    start()
  }

  onUnmounted(stop)

  return { start, stop, restart }
}
