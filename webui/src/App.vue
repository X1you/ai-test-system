<template>
  <div class="app-layout">
    <a href="#main-content" class="skip-link">跳到主内容</a>
    <AppSidebar />
    <main id="main-content" class="app-main">
      <router-view />
    </main>
    <ToastContainer />
  </div>
</template>

<script setup>
import AppSidebar from './components/AppSidebar.vue'
import ToastContainer from './components/ToastContainer.vue'
</script>

<style scoped>
.app-layout {
  display: flex;
  min-height: 100vh;
}

.app-main {
  flex: 1;
  min-width: 0;
  padding: var(--space-xl);
  overflow-y: auto;
}

@media (max-width: 768px) {
  .app-layout {
    flex-direction: column;
  }
  .app-main {
    padding: var(--space-lg);
    padding-bottom: 72px; /* bottom tab bar space */
  }
}
</style>
