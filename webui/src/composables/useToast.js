/**
 * 全局 Toast 通知 — window 级单例，保证跨 chunk 共享同一实例
 *
 * 用法：
 *   import { useToast } from '../composables/useToast'
 *   const toast = useToast()
 *   toast.success('保存成功')
 */

import { ref } from 'vue'

function createToast() {
  const items = ref([])
  let _seq = 0

  function push(type, message, duration = 3000) {
    const id = ++_seq
    items.value = [...items.value, { id, type, message }]
    if (duration > 0) {
      setTimeout(() => remove(id), duration)
    }
    return id
  }

  function remove(id) {
    items.value = items.value.filter(t => t.id !== id)
  }

  return {
    items,
    remove,
    success(msg, dur) { return push('success', msg, dur) },
    error(msg, dur)   { return push('error', msg, dur ?? 4000) },
    info(msg, dur)    { return push('info', msg, dur) },
    warn(msg, dur)    { return push('warn', msg, dur) },
  }
}

// window 全局单例：第一个加载的 chunk 创建，后续 chunk 复用
// 彻底规避 Vite 代码分割导致的模块多实例 / inject 上下文问题
export const toast = (window.__appToast ||= createToast())

/** 在任意组件 setup 中调用，获取全局 toast 实例 */
export function useToast() {
  return toast
}
