<template>
  <div class="app-shell">
    <header class="app-header">
      <div class="header-brand">
        <span class="logo">🧪</span>
        <span class="title">AI 测试用例生成系统</span>
      </div>
      <nav class="header-nav">
        <router-link to="/" class="nav-link">首页</router-link>
        <router-link to="/pipelines" class="nav-link">任务列表</router-link>
        <router-link to="/knowledge" class="nav-link">知识库</router-link>
      </nav>
    </header>
    <main class="app-main">
      <router-view />
    </main>
  </div>
</template>

<script setup>
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: #f5f5f5;
  color: #333;
}
.app-shell { min-height: 100vh; display: flex; flex-direction: column; }
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  height: 56px;
  background: #fff;
  border-bottom: 1px solid #e0e0e0;
  position: sticky;
  top: 0;
  z-index: 100;
}
.header-brand { display: flex; align-items: center; gap: 8px; }
.logo { font-size: 20px; }
.title { font-size: 16px; font-weight: 600; }
.header-nav { display: flex; gap: 4px; }
.nav-link {
  padding: 8px 16px;
  border-radius: 6px;
  text-decoration: none;
  color: #555;
  font-size: 14px;
  transition: all 0.2s;
}
.nav-link:hover { background: #f0f0f0; color: #111; }
.nav-link.router-link-active { background: #e8f0fe; color: #1a73e8; font-weight: 500; }
.app-main { flex: 1; padding: 24px; max-width: 1200px; margin: 0 auto; width: 100%; }
</style>
