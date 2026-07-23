<template>
  <div class="stat-card">
    <span class="stat-card__value tabular-nums">{{ value }}</span>
    <span class="stat-card__label">{{ label }}</span>
  </div>
</template>

<script setup>
defineProps({
  value: { type: [Number, String], default: 0 },
  label: { type: String, required: true },
})
</script>

<style scoped>
.stat-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
  padding: var(--space-lg) var(--space-xl);
  background: var(--gradient-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  position: relative;
  overflow: hidden;
  transition: transform var(--duration-normal) var(--ease-out),
              box-shadow var(--duration-normal) var(--ease-out),
              border-color var(--duration-normal) var(--ease-out);
}

.stat-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: var(--gradient-accent);
  opacity: 0;
  transition: opacity var(--duration-normal) var(--ease-out);
}

.stat-card:hover {
  transform: translateY(-3px);
  box-shadow: var(--shadow-md);
  border-color: var(--border-strong);
}
[data-theme="dark"] .stat-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md), var(--shadow-accent);
  border-color: var(--accent);
}

.stat-card:hover::before {
  opacity: 1;
}
[data-theme="dark"] .stat-card::before {
  background: var(--accent);
  box-shadow: 0 0 8px hsl(0 0% 50% / 0.4);
}
[data-theme="dark"] .stat-card__value {
  text-shadow: var(--text-glow);
}

.stat-card__value {
  font-size: var(--text-2xl);
  font-weight: 800;
  color: var(--text-primary);
  line-height: 1.15;
  letter-spacing: -0.03em;
}

.stat-card__label {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  font-weight: 500;
}
</style>
