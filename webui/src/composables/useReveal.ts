/**
 * useReveal — IntersectionObserver 滚动揭示动画
 *
 * 用法：给需要揭示动画的元素加上 data-reveal 属性，该 composable 会在
 * onMounted 时（nextTick + setTimeout(50) 确保 DOM 渲染完成）为所有
 * [data-reveal] 注册 IntersectionObserver，进入视口即添加 .is-visible。
 *
 * 样式约定（在落地页根样式中定义）：
 *   [data-reveal]      { opacity: 0; transform: translateY(24px); transition: ...; }
 *   [data-reveal].is-visible { opacity: 1; transform: none; }
 *
 * 可用属性（每元素）：
 *   data-reveal-delay  整数 ms，延迟出现（写进 transition-delay）
 *   data-reveal-y      translateY 像素（默认 24）
 */
import { onMounted, onBeforeUnmount, nextTick } from 'vue'

export interface RevealOptions {
  root?: Element | null
  rootMargin?: string
  threshold?: number | number[]
  selector?: string
  once?: boolean
}

export function useReveal(options: RevealOptions = {}) {
  const {
    root = null,
    rootMargin = '0px 0px -10% 0px',
    threshold = 0.15,
    selector = '[data-reveal]',
    once = true,
  } = options

  let observer: IntersectionObserver | null = null

  const setupObserver = () => {
    // 历史浏览器兼容兜底
    if (typeof IntersectionObserver === 'undefined') {
      const els = document.querySelectorAll<HTMLElement>(selector)
      els.forEach((el) => el.classList.add('is-visible'))
      return
    }

    observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-visible')
            if (once && observer) observer.unobserve(entry.target)
          } else if (!once) {
            entry.target.classList.remove('is-visible')
          }
        })
      },
      { root, rootMargin, threshold },
    )

    const els = document.querySelectorAll<HTMLElement>(selector)
    if (observer) {
      els.forEach((el) => observer!.observe(el))
    }
  }

  onMounted(() => {
    // nextTick 确保 Vue 完成 DOM patch，setTimeout(50) 再兜底一次渲染时序
    nextTick(() => {
      setTimeout(setupObserver, 50)
    })
  })

  onBeforeUnmount(() => {
    if (observer) {
      observer.disconnect()
      observer = null
    }
  })

  return {
    /** 手动重新扫描并观察（动态插入元素时调用） */
    refresh: setupObserver,
  }
}
