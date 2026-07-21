import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import './assets/tokens.css'

const app = createApp(App)
app.use(router)
app.mount('#app')

// ─── Minimal ripple effect (light mode only) ───
// Pure visual: creates a transient <span> at click position, removed after animation.
// No business logic, no template modifications, no event-binding changes.
document.addEventListener('pointerdown', (e) => {
  // Only in light mode
  if (document.documentElement.getAttribute('data-theme') === 'dark') return
  // Only real <button> elements (not links styled as buttons)
  const btn = e.target.closest('button')
  if (!btn || btn.disabled) return

  // Ensure button can clip the ripple
  btn.classList.add('ripple-scope')

  const rect = btn.getBoundingClientRect()
  const size = Math.max(rect.width, rect.height)
  const ripple = document.createElement('span')
  ripple.className = 'ripple-effect'
  ripple.style.left = `${e.clientX - rect.left}px`
  ripple.style.top = `${e.clientY - rect.top}px`
  ripple.style.width = `${size}px`
  ripple.style.height = `${size}px`
  btn.appendChild(ripple)

  ripple.addEventListener('animationend', () => ripple.remove(), { once: true })
  // Safety cleanup
  setTimeout(() => { if (ripple.parentNode) ripple.remove() }, 800)
})
