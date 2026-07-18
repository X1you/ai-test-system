/* ============================================================
   AI TestGen — Premium JS Library v3.0
   ============================================================ */

/**
 * HTML 转义
 */
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text || '';
  return div.innerHTML;
}

/**
 * 文件大小格式化
 */
function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

/**
 * 时间格式化
 */
function formatTime(isoString) {
  if (!isoString) return '--';
  try {
    const d = new Date(isoString);
    const pad = (n) => String(n).padStart(2, '0');
    return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  } catch (e) {
    return '--';
  }
}

/**
 * 日期格式化
 */
function formatDate(isoString) {
  if (!isoString) return '--';
  try {
    const d = new Date(isoString);
    const pad = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  } catch (e) {
    return '--';
  }
}

/**
 * 相对时间
 */
function relativeTime(isoString) {
  if (!isoString) return '--';
  try {
    const now = Date.now();
    const then = new Date(isoString).getTime();
    const diff = now - then;
    const sec = Math.floor(diff / 1000);
    if (sec < 60) return '刚刚';
    const min = Math.floor(sec / 60);
    if (min < 60) return `${min} 分钟前`;
    const hour = Math.floor(min / 60);
    if (hour < 24) return `${hour} 小时前`;
    const day = Math.floor(hour / 24);
    return `${day} 天前`;
  } catch (e) {
    return '--';
  }
}

/**
 * Toast 通知（带数量上限，防止 DOM 堆积）
 */
let _toastTimer = null;
var MAX_TOASTS = 5; // 容器最多同时存在 5 条 toast
function showToast(message, type, duration) {
  type = type || 'info';
  duration = duration || 4000;
  const container = document.getElementById('toast-container');
  if (!container) return;

  // 数量上限：超出则移除最早的
  var existing = container.querySelectorAll('.toast');
  while (existing.length >= MAX_TOASTS) {
    existing[0].remove();
    existing = container.querySelectorAll('.toast');
  }

  const icons = { success: '✓', error: '✕', warning: '!', info: 'i' };
  const toast = document.createElement('div');
  toast.className = 'toast toast-' + type;
  toast.setAttribute('role', 'alert');
  toast.setAttribute('aria-live', 'assertive');
  toast.innerHTML = '<span aria-hidden="true" style="font-weight:700;font-size:0.85rem;">' + (icons[type] || '') + '</span><span>' + message + '</span>';
  container.appendChild(toast);

  // 每条 toast 独立计时器（不再用全局 _toastTimer 覆盖）
  setTimeout(function () {
    toast.style.animation = 'toast-out 0.3s ease forwards';
    setTimeout(function () { toast.remove(); }, 300);
  }, duration);
}

/**
 * 确认对话框
 */
function confirmDialog(message, title) {
  return new Promise(function (resolve) {
    if (typeof message === 'object' && message.preventDefault) {
      return resolve(true);
    }
    const result = window.confirm(message);
    resolve(result);
  });
}

/**
 * 防抖
 */
function debounce(fn, delay) {
  let timer = null;
  return function () {
    const ctx = this;
    const args = arguments;
    clearTimeout(timer);
    timer = setTimeout(function () { fn.apply(ctx, args); }, delay);
  };
}

/**
 * 节流
 */
function throttle(fn, limit) {
  let inThrottle = false;
  return function () {
    const ctx = this;
    const args = arguments;
    if (!inThrottle) {
      fn.apply(ctx, args);
      inThrottle = true;
      setTimeout(function () { inThrottle = false; }, limit);
    }
  };
}

/**
 * 初始化文件上传区域交互
 */
function initUploadZone(zoneId, inputSelector, nameDisplayId, iconId, textId) {
  const zone = document.getElementById(zoneId);
  const input = zone ? zone.querySelector(inputSelector) : null;
  const nameDisplay = document.getElementById(nameDisplayId);
  const icon = iconId ? document.getElementById(iconId) : null;
  const text = textId ? document.getElementById(textId) : null;

  if (!zone || !input) return;

  input.addEventListener('change', function () {
    if (this.files && this.files.length > 0) {
      const f = this.files[0];
      if (nameDisplay) {
        nameDisplay.textContent = f.name + ' (' + formatFileSize(f.size) + ')';
        nameDisplay.style.display = 'block';
      }
      if (icon) icon.textContent = '\u2713';
      if (text) text.innerHTML = '已选择文件';
      zone.classList.add('has-file');
    }
  });

  zone.addEventListener('dragover', function (e) {
    e.preventDefault();
    zone.classList.add('dragover');
  });

  zone.addEventListener('dragleave', function () {
    zone.classList.remove('dragover');
  });

  zone.addEventListener('drop', function () {
    zone.classList.remove('dragover');
  });
}

/**
 * 初始化选项卡片交互
 */
function initOptionCards(containerSelector) {
  const container = document.querySelector(containerSelector);
  if (!container) return;

  const cards = container.querySelectorAll('.option-card-tile');
  cards.forEach(function (card) {
    card.addEventListener('click', function () {
      const input = this.querySelector('input');
      if (!input) return;

      if (input.type === 'radio') {
        const name = input.name;
        container.querySelectorAll('.option-card-tile input[name="' + name + '"]').forEach(function (other) {
          other.closest('.option-card-tile').classList.remove('selected');
        });
        this.classList.add('selected');
        if (!input.checked) {
          input.checked = true;
          // ★ 关键：手动触发 change 事件，让依赖 radio change 的逻辑（如自定义维度输入框）正常工作
          input.dispatchEvent(new Event('change', { bubbles: true }));
        }
      } else if (input.type === 'checkbox') {
        input.checked = !input.checked;
        this.classList.toggle('selected', input.checked);
        input.dispatchEvent(new Event('change', { bubbles: true }));
      }
    });
    card.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        this.click();
      }
    });
  });
}

/**
 * 停止 HTMX 轮询
 */
function stopPolling(elementId) {
  const el = document.getElementById(elementId || 'progress-area');
  if (el) {
    el.removeAttribute('hx-trigger');
    el.removeAttribute('hx-get');
    if (typeof htmx !== 'undefined') htmx.process(el);
  }
}

/* ─── 全局元素去重守卫 ───
   背景：hx-boost 导航竞态（快速连续点击 / bfcache 恢复 / 某些 HTMX 端点返回完整页面
   而非片段）时，完整文档里的 nav/footer 等全局元素会被错误 swap 进 <main>，导致
   顶部出现重复的导航条。此函数扫描 body 直系子节点，对每个"应全局唯一"的元素只保留
   第一个，移除其余副本。幂等、安全（找不到目标时无操作）。 */
var GLOBAL_UNIQUE_SELECTORS = [
  'nav.app-nav',
  'footer.app-footer',
  '#toast-container',
  '.page-progress-bar',
  'a.sr-only' // 跳转到主内容
];

function dedupeGlobalElements() {
  GLOBAL_UNIQUE_SELECTORS.forEach(function (sel) {
    var all = document.querySelectorAll(sel);
    if (all.length <= 1) return;
    // 保留第一个（通常是 base.html 里静态渲染的），移除后续所有副本
    for (var i = 1; i < all.length; i++) {
      var el = all[i];
      // 仅清理 body 直系或经错误 swap 进入 main 的副本
      if (el.parentNode) el.parentNode.removeChild(el);
    }
  });
}

/* ─── Theme ─── */

(function () {
  const saved = localStorage.getItem('theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const theme = saved || (prefersDark ? 'dark' : 'light');
  document.documentElement.setAttribute('data-theme', theme);
  updateThemeColor(theme);
  const icon = document.getElementById('theme-icon');
  if (icon) icon.textContent = theme === 'dark' ? '☀️' : '🌙';
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function (e) {
    if (!localStorage.getItem('theme')) {
      const t = e.matches ? 'dark' : 'light';
      document.documentElement.setAttribute('data-theme', t);
      updateThemeColor(t);
      if (icon) icon.textContent = e.matches ? '☀️' : '🌙';
    }
  });
})();

function updateThemeColor(theme) {
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) {
    meta.content = theme === 'dark' ? '#111113' : '#F8FAFC';
  }
}

function toggleTheme() {
  const html = document.documentElement;
  const current = html.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-theme', next);
  localStorage.setItem('theme', next);
  updateThemeColor(next);
  const icon = document.getElementById('theme-icon');
  if (icon) icon.textContent = next === 'dark' ? '☀️' : '🌙';
}

/* ─── Global HTMX Events ───
   关键设计：错误去重 + 限频 + 上限，避免轮询失败时无限刷屏 toast。
   设计目标：
   - 同一错误（status + target）全局最多弹 3 次 toast，之后静默
   - 冷却窗口（4s）内只弹一次
   - 404/410 等资源不存在错误：立即停止该目标的轮询
   - 5xx 连续失败 3 次以上：停止轮询，注入重试 UI
   - 所有错误都向目标元素注入 inline 错误 UI（含手动重试按钮）
   - toast 容器上限 5 条，超出自动剔除最早的，防止 DOM 堆积   */

var _htmxErrorState = {}; // { [key]: { count, lastTs, toastShownCount, lastToastTs } }
var MAX_ERROR_TOASTS_PER_KEY = 3;  // 同一错误最多弹 3 次
var ERROR_COOLDOWN_MS = 4000;     // 冷却窗口
var MAX_FAIL_BEFORE_STOP = 3;     // 5xx 连续失败几次后停止轮询

function _htmxErrorKey(evt) {
  var xhr = evt.detail.xhr;
  var status = xhr ? xhr.status : 'network';
  var target = evt.detail.target;
  var targetId = target ? (target.id || target.getAttribute('hx-get') || 'unknown') : 'unknown';
  return status + ':' + targetId;
}

function _stopHtmxPolling(target) {
  if (!target) return;
  // 1. 保存原始请求 URL（重试时需要），data-retry-url 优先
  if (!target.getAttribute('data-retry-url')) {
    var origGet = target.getAttribute('hx-get') || target.getAttribute('hx-post');
    if (origGet) target.setAttribute('data-retry-url', origGet);
  }
  // 2. 移除触发属性（hx-trigger / hx-get / hx-post）
  target.removeAttribute('hx-trigger');
  target.removeAttribute('hx-get');
  target.removeAttribute('hx-post');
  // 3. 清空 htmx 内部已计算的触发器规格，确保正在排队的 every 轮询被取消
  try {
    var internal = target['htmx-internal-data'];
    if (internal) {
      internal.triggerSpecs = [];
      internal.lastSetValue = null;
    }
  } catch (e) { /* ignore */ }
  // 4. 让 htmx 重新扫描（此时已无 hx-trigger，不会重建轮询）
  if (typeof htmx !== 'undefined') {
    try { htmx.process(target); } catch (e) { /* ignore */ }
  }
}

// 全局重试函数（重试按钮调用，不使用脆弱的 inline onclick）
function htmxRetryTarget(targetSelector) {
  var target = document.querySelector(targetSelector);
  if (!target) return;
  // 清理错误 UI
  var panel = target.querySelector('.htmx-error-panel');
  if (panel) panel.remove();
  // 从 data-retry-url 恢复 hx-get，恢复轮询触发
  var retryUrl = target.getAttribute('data-retry-url');
  if (retryUrl) {
    target.setAttribute('hx-get', retryUrl);
    target.setAttribute('hx-trigger', 'load, every 2s');
  } else {
    target.setAttribute('hx-trigger', 'load');
  }
  // 恢复加载占位
  target.innerHTML = '<div style="text-align:center; padding:40px 0;"><div class="spinner spinner-lg"></div><p class="text-muted mt-md">正在重新加载...</p></div>';
  if (typeof htmx !== 'undefined') {
    htmx.process(target);
    htmx.trigger(target, 'load');
  }
  // 重置该目标的错误状态
  var tid = target.id || 'unknown';
  for (var k in _htmxErrorState) {
    if (k.indexOf(':' + tid) !== -1) {
      delete _htmxErrorState[k];
    }
  }
}

function _injectErrorUI(target, status, message) {
  if (!target) return;
  // 避免重复注入
  if (target.querySelector('.htmx-error-panel')) return;

  var isNotFound = status === 404 || status === 410;
  var isNetwork = status === 'network' || status === 0;
  var retryAttr = target.getAttribute('data-retry-url') || target.getAttribute('hx-get') || '';
  var retryable = !isNotFound && retryAttr;

  var html = '<div class="htmx-error-panel" role="alert" style="padding:32px 24px;text-align:center;">'
    + '<div style="font-size:2.5rem;margin-bottom:12px;opacity:0.4;">' + (isNotFound ? '🔍' : '⚠️') + '</div>'
    + '<div style="font-weight:600;font-size:1.05rem;color:var(--text-primary);margin-bottom:8px;">'
    + (isNotFound ? '任务不存在或已被清理' : (isNetwork ? '网络连接失败' : '加载失败'))
    + '</div>'
    + '<div style="font-size:0.85rem;color:var(--text-tertiary);margin-bottom:20px;">'
    + (message || ('HTTP ' + status))
    + '</div>';
  if (retryable) {
    var sel = '#' + (target.id || '');
    html += '<button type="button" class="btn btn-primary btn-sm" '
      + 'onclick="htmxRetryTarget(\'' + sel + '\')" '
      + 'style="min-width:120px;">重试</button>';
  }
  html += '<a href="/" class="btn btn-secondary btn-sm" style="margin-left:8px;min-width:120px;">返回首页</a>';
  html += '</div>';
  target.innerHTML = html;

  // 任务不可达时，禁用页面上的"取消"按钮（无法取消一个不存在的任务）
  var cancelBtn = document.getElementById('cancel-btn');
  if (cancelBtn) {
    cancelBtn.disabled = true;
    cancelBtn.style.display = 'none';
  }
}

document.addEventListener('DOMContentLoaded', function () {
  document.body.addEventListener('htmx:responseError', function (evt) {
    var xhr = evt.detail.xhr;
    var status = xhr ? xhr.status : 0;
    var target = evt.detail.target;
    var key = _htmxErrorKey(evt);
    var now = Date.now();

    var state = _htmxErrorState[key] || { count: 0, lastTs: 0, toastShownCount: 0, lastToastTs: 0 };
    state.count++;
    state.lastTs = now;

    // 冷却窗口判断
    var inCooldown = (now - state.lastToastTs) < ERROR_COOLDOWN_MS;
    var underCap = state.toastShownCount < MAX_ERROR_TOASTS_PER_KEY;

    // 只在：未在冷却内 + 未超上限 时弹 toast
    if (!inCooldown && underCap) {
      var msg = status === 404 || status === 410
        ? '任务不存在（' + status + '），可能已被清理'
        : '请求失败: HTTP ' + (status || '未知');
      showToast(msg, 'error');
      state.toastShownCount++;
      state.lastToastTs = now;
    }

    _htmxErrorState[key] = state;

    // 404/410：资源不存在，必须停止轮询，否则无限重试
    if (status === 404 || status === 410) {
      _stopHtmxPolling(target);
      var errMsg = '该 Pipeline 任务不存在或已被系统清理（HTTP ' + status + '）。';
      _injectErrorUI(target, status, errMsg);
    } else if (state.count >= MAX_FAIL_BEFORE_STOP) {
      // 5xx 等连续失败：停止轮询，注入重试 UI
      _stopHtmxPolling(target);
      _injectErrorUI(target, status, '接口连续失败 ' + state.count + ' 次，已暂停自动刷新。');
    }
  });

  document.body.addEventListener('htmx:sendError', function (evt) {
    var target = evt.detail.target;
    var tid = target ? (target.id || 'unknown') : 'unknown';
    var key = 'network:' + tid;
    var now = Date.now();
    var state = _htmxErrorState[key] || { count: 0, lastTs: 0, toastShownCount: 0, lastToastTs: 0 };
    state.count++;
    state.lastTs = now;
    var inCooldown = (now - state.lastToastTs) < ERROR_COOLDOWN_MS;
    var underCap = state.toastShownCount < MAX_ERROR_TOASTS_PER_KEY;
    if (!inCooldown && underCap) {
      showToast('网络错误，请检查连接', 'error');
      state.toastShownCount++;
      state.lastToastTs = now;
    }
    _htmxErrorState[key] = state;
    // 网络错误连续多次也停止轮询
    if (state.count >= MAX_FAIL_BEFORE_STOP) {
      _stopHtmxPolling(target);
      _injectErrorUI(target, 'network', '网络连续失败 ' + state.count + ' 次，请检查连接后重试。');
    }
  });

  document.body.addEventListener('htmx:beforeRequest', function (evt) {
    const target = evt.detail.target;
    if (target) target.setAttribute('aria-busy', 'true');
  });

  document.body.addEventListener('htmx:afterRequest', function (evt) {
    const target = evt.detail.target;
    if (target) target.removeAttribute('aria-busy');
    // 请求成功：重置该目标的错误计数
    if (evt.detail.successful && evt.detail.xhr && evt.detail.xhr.status >= 200 && evt.detail.xhr.status < 300) {
      var key = _htmxErrorKey(evt);
      if (_htmxErrorState[key]) _htmxErrorState[key].count = 0;
    }
  });
});

/* ─── Intersection Observer: Staggered card entrance ─── */
(function () {
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry, i) {
        if (entry.isIntersecting) {
          setTimeout(function () {
            entry.target.style.opacity = '1';
            entry.target.style.transform = 'translateY(0)';
          }, i * 60);
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.1, rootMargin: '0px 0px -20px 0px' });

    document.addEventListener('htmx:afterSwap', function () {
      document.querySelectorAll('.card, .pipeline-item, .kb-stat-card, .step-summary-card, .artifact-card, .search-result-item').forEach(function (el) {
        if (!el.dataset.observed) {
          el.dataset.observed = '1';
          el.style.opacity = '0';
          el.style.transform = 'translateY(12px)';
          el.style.transition = 'opacity 0.4s ease-out, transform 0.4s ease-out';
          observer.observe(el);
        }
      });
    });

    // Initial scan
    document.querySelectorAll('.card, .pipeline-item, .kb-stat-card, .step-summary-card, .artifact-card, .search-result-item').forEach(function (el) {
      el.dataset.observed = '1';
      el.style.opacity = '0';
      el.style.transform = 'translateY(12px)';
      el.style.transition = 'opacity 0.4s ease-out, transform 0.4s ease-out';
      observer.observe(el);
    });
  }
})();

/* ──────────────────────────────────────────────────────────
   Tab/Content Swap Smooth Transitions
   HTMX 事件处理：消除内容切换时的闪烁
   ────────────────────────────────────────────────────────── */

(function () {
  'use strict';

  // ── 配置 ──
  var SWAP_FADE_DURATION = 150;  // 旧内容淡出时长 (ms)
  var ENTER_DURATION = 200;      // 新内容淡入时长 (ms)

  // ── 判断是否为轮询区域（every Ns 触发）──
  function _isPollingTarget(target) {
    if (!target) return false;
    var trigger = target.getAttribute('hx-trigger');
    return !!(trigger && trigger.indexOf('every') !== -1);
  }

  // ── HTMX 内容交换前：给旧内容添加淡出动画 ──
  document.body.addEventListener('htmx:beforeSwap', function (evt) {
    var target = evt.detail.target;
    if (!target) return;

    // 轮询区域：完全跳过过渡动画，避免每次刷新都闪烁
    if (_isPollingTarget(target)) return;

    // 跳过没有子元素的空目标
    if (!target.children || target.children.length === 0) return;

    // 给旧内容添加淡出类（HTMX 会在事件返回后立即替换 DOM，
    // 这里主要确保过渡类不会残留影响新内容）
    if (target._swapLeaveTimer) clearTimeout(target._swapLeaveTimer);
  });

  // ── HTMX 内容交换后：给新内容添加淡入动画 ──
  document.body.addEventListener('htmx:afterSwap', function (evt) {
    var target = evt.detail.target;
    if (!target) return;

    // ★ 关键修复：轮询区域不加淡入动画，否则每 2s/10s 闪烁一次
    if (_isPollingTarget(target)) {
      // 确保没有残留的过渡类
      target.classList.remove('content-enter');
      target.classList.remove('content-leave');
      return;
    }

    // 清除可能的遗留定时器
    if (target._swapEnterTimer) {
      clearTimeout(target._swapEnterTimer);
      target._swapEnterTimer = null;
    }

    // 延迟一帧确保新内容已渲染，然后添加淡入动画
    target._swapEnterTimer = requestAnimationFrame(function () {
      target.classList.add('content-enter');
      target._swapEnterTimer = setTimeout(function () {
        target.classList.remove('content-enter');
        target._swapEnterTimer = null;
      }, ENTER_DURATION);
    });
  });

  // ── 轮询区域的特殊处理：避免每次轮询都触发过渡动画 ──
  document.body.addEventListener('htmx:beforeRequest', function (evt) {
    var target = evt.detail.target;
    if (!target) return;

    if (_isPollingTarget(target)) {
      // 轮询区域：清除所有过渡类，确保内容直接替换无动画
      target.classList.remove('content-enter');
      target.classList.remove('content-leave');
      if (target._swapLeaveTimer) {
        clearTimeout(target._swapLeaveTimer);
        target._swapLeaveTimer = null;
      }
      if (target._swapEnterTimer) {
        clearTimeout(target._swapEnterTimer);
        target._swapEnterTimer = null;
      }
    }
  });

  // ── 导航链接预加载 (Prefetch) ──
  // 使用 IntersectionObserver 和 mouseenter 预加载导航目标页面
  var prefetchCache = {};

  function prefetchPage(url) {
    if (prefetchCache[url]) return;
    prefetchCache[url] = true;

    // 使用 fetch 预加载，但不影响当前页面
    try {
      var controller = new AbortController();
      // 只缓存预加载状态，不实际缓存响应
      fetch(url, {
        method: 'GET',
        signal: controller.signal,
        priority: 'low'
      }).catch(function () {
        // 静默处理预加载失败
      });
      // 请求发起后立即释放控制权
      setTimeout(function () { controller.abort(); }, 2000);
    } catch (e) {
      // 不支持 AbortController 的浏览器静默降级
    }
  }

  // 为导航链接添加预加载
  function initPrefetch() {
    var links = document.querySelectorAll('.app-nav-links a, .back-link, .btn[href]');
    links.forEach(function (link) {
      var href = link.getAttribute('href');
      if (!href || href.startsWith('#') || href.startsWith('javascript')) return;

      // mouseenter 时预加载（比 click 更早触发）
      link.addEventListener('mouseenter', function () {
        prefetchPage(href);
      }, { passive: true });

      // 移动端：touchstart 时预加载
      link.addEventListener('touchstart', function () {
        prefetchPage(href);
      }, { passive: true });
    });
  }

  // 初始化和监听 HTMX 交换后重新扫描
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPrefetch);
  } else {
    initPrefetch();
  }

  document.addEventListener('htmx:afterSwap', function () {
    // 重新扫描导航链接，为新注入的内容添加预加载
    initPrefetch();
    // 全局元素去重：防止 hx-boost 竞态导致 nav/footer 重复
    dedupeGlobalElements();
  });

  // 页面恢复（bfcache）和初始加载时也执行一次去重
  window.addEventListener('pageshow', dedupeGlobalElements);
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', dedupeGlobalElements);
  } else {
    dedupeGlobalElements();
  }

  // ── 消除页面导航时的白屏闪烁 ──
  // 在页面加载完成前保持背景色连续性
  (function () {
    // 如果页面是从缓存加载（bfcache），跳过动画
    if (window.performance && window.performance.navigation &&
        window.performance.navigation.type === 2) {
      var main = document.querySelector('.app-main');
      if (main) {
        main.style.animation = 'none';
        main.style.opacity = '1';
      }
    }
  })();
})();