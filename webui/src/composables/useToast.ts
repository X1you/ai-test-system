/**
 * Toast 通知 — Pinia store 驱动
 */
import { defineStore } from 'pinia'

export interface ToastItem {
  id: number
  message: string
  type: 'info' | 'success' | 'error' | 'warn'
}

let toastId = 0

export const useToastStore = defineStore('toast', {
  state: () => ({
    items: [] as ToastItem[],
  }),
  actions: {
    show(message: string, type: ToastItem['type'] = 'info', duration = 2500) {
      const id = ++toastId
      this.items.push({ id, message, type })
      setTimeout(() => this.dismiss(id), duration)
    },
    success(msg: string) { this.show(msg, 'success') },
    error(msg: string) { this.show(msg, 'error', 4000) },
    warn(msg: string) { this.show(msg, 'warn', 3500) },
    info(msg: string) { this.show(msg, 'info') },
    dismiss(id: number) {
      const idx = this.items.findIndex((t) => t.id === id)
      if (idx >= 0) this.items.splice(idx, 1)
    },
  },
})
