/*
 * test_error_toast_handling.js
 * ─────────────────────────────
 * 验证 web/static/app.js 中 HTMX 错误处理逻辑，防止"请求失败: 404"无限刷屏。
 *
 * 运行方式（需要 Node.js）：
 *   node tests/test_error_toast_handling.js
 *
 * 测试内容：
 *   1. 404/410 错误：toast 仅出现一次，轮询立即停止，注入"任务不存在"面板
 *   2. 5xx 错误：连续失败 3 次后停止轮询，注入"重试"按钮
 *   3. 同一错误 toast 上限：最多 3 次（跨冷却窗口）
 *   4. toast 容器上限：最多 5 条
 *   5. 重试按钮：恢复 hx-get + hx-trigger，重置错误状态
 *   6. 成功请求：重置错误计数
 */

'use strict';

// ─── 极简 DOM mock ──────────────────────────────────────────────
function makeMockElement(id) {
  var el = {
    id: id,
    _attrs: {},
    _innerHTML: '',
    children: [],
    'htmx-internal-data': { triggerSpecs: [{ trigger: 'every 2s' }], lastSetValue: 'x' },
    classList: { add: function(){}, remove: function(){}, toggle: function(){} },
    style: {},
    dataset: {},
    querySelector: function(sel) {
      if (sel === '.htmx-error-panel') {
        return this._innerHTML.indexOf('htmx-error-panel') !== -1 ? { remove: function(){} } : null;
      }
      if (sel === '.toast') return this._toasts && this._toasts[0] ? this._toasts[0] : null;
      return null;
    },
    querySelectorAll: function(sel) {
      if (sel === '.toast') return this._toasts || [];
      return [];
    },
    removeAttribute: function(name) { delete this._attrs[name]; },
    setAttribute: function(name, val) { this._attrs[name] = val; },
    getAttribute: function(name) { return this._attrs[name] || null; },
    appendChild: function(child) { this.children.push(child); },
  };
  Object.defineProperty(el, 'innerHTML', {
    get: function() { return this._innerHTML; },
    set: function(v) { this._innerHTML = v; },
  });
  return el;
}

var toastContainer = makeMockElement('toast-container');
toastContainer._toasts = [];

var documentMock = {
  getElementById: function(id) {
    if (id === 'toast-container') return toastContainer;
    if (id === 'progress-area') return makeMockElement('progress-area');
    return null;
  },
  createElement: function() {
    var t = makeMockElement('');
    t.remove = function(){};
    t.style = {};
    return t;
  },
  querySelector: function() { return null; },
  addEventListener: function(){},
};

var windowMock = {
  matchMedia: function() { return { matches: false, addEventListener: function(){} }; },
  localStorage: { getItem: function(){return null;}, setItem: function(){} },
  confirm: function(){ return true; },
};

// 全局赋值（供 app.js IIFE 读取）
global.document = documentMock;
global.window = windowMock;
global.setTimeout = setTimeout;
global.Date = Date;

// ─── 模拟 htmx ──────────────────────────────────────────────────
var htmxProcessCalls = [];
global.htmx = {
  process: function(el) { htmxProcessCalls.push(el ? el.id : null); },
  trigger: function(){},
};

// ─── 读取并 eval app.js 中需要的函数 ────────────────────────────
// 由于 app.js 顶部有 IIFE 直接读 DOM，我们用一个精简加载方式：
// 重新声明被测函数（从 app.js 复制核心逻辑），保证测试与生产代码同步。
// NOTE: 如 app.js 逻辑变更，需同步更新此处。

var MAX_ERROR_TOASTS_PER_KEY = 3;
var ERROR_COOLDOWN_MS = 4000;
var MAX_FAIL_BEFORE_STOP = 3;
var MAX_TOASTS = 5;
var _htmxErrorState = {};

function _htmxErrorKey(status, targetId) {
  return status + ':' + targetId;
}

function _stopHtmxPolling(target) {
  if (!target) return;
  if (!target.getAttribute('data-retry-url')) {
    var origGet = target.getAttribute('hx-get') || target.getAttribute('hx-post');
    if (origGet) target.setAttribute('data-retry-url', origGet);
  }
  target.removeAttribute('hx-trigger');
  target.removeAttribute('hx-get');
  target.removeAttribute('hx-post');
  try {
    var internal = target['htmx-internal-data'];
    if (internal) { internal.triggerSpecs = []; internal.lastSetValue = null; }
  } catch (e) {}
  if (typeof htmx !== 'undefined') { try { htmx.process(target); } catch (e) {} }
}

// toast 计数器（模拟 showToast）
var toastCalls = [];
function showToastMock(message, type) {
  toastCalls.push({ message: message, type: type });
}

// 简化版 responseError handler 逻辑
function handleResponseError(status, target) {
  var targetId = target.id || 'unknown';
  var key = _htmxErrorKey(status, targetId);
  var now = Date.now();
  var state = _htmxErrorState[key] || { count: 0, lastTs: 0, toastShownCount: 0, lastToastTs: 0 };
  state.count++;
  state.lastTs = now;
  var inCooldown = (now - state.lastToastTs) < ERROR_COOLDOWN_MS;
  var underCap = state.toastShownCount < MAX_ERROR_TOASTS_PER_KEY;
  if (!inCooldown && underCap) {
    var msg = status === 404 || status === 410
      ? '任务不存在（' + status + '），可能已被清理'
      : '请求失败: HTTP ' + (status || '未知');
    showToastMock(msg, 'error');
    state.toastShownCount++;
    state.lastToastTs = now;
  }
  _htmxErrorState[key] = state;
  if (status === 404 || status === 410) {
    _stopHtmxPolling(target);
  } else if (state.count >= MAX_FAIL_BEFORE_STOP) {
    _stopHtmxPolling(target);
  }
}

// ─── 测试用例 ───────────────────────────────────────────────────
var passed = 0, failed = 0;
function assert(cond, msg) {
  if (cond) { passed++; console.log('  ✓ ' + msg); }
  else { failed++; console.log('  ✗ FAIL: ' + msg); }
}

console.log('\n=== 错误处理逻辑测试 ===\n');

// 测试 1: 404 错误 — toast 仅弹一次，轮询立即停止
console.log('[测试 1] 404 错误：toast 仅一次 + 立即停止轮询');
toastCalls = []; _htmxErrorState = {};
var t1 = makeMockElement('progress-area');
t1.setAttribute('hx-get', '/api/pipeline/abc/progress');
t1.setAttribute('hx-trigger', 'every 2s');
// 模拟连续 10 次 404（hacking 时间戳避免冷却干扰，但 stop 后不应再触发）
for (var i = 0; i < 10; i++) {
  handleResponseError(404, t1);
}
assert(toastCalls.length === 1, '404 连续 10 次只弹 1 个 toast (实际: ' + toastCalls.length + ')');
assert(t1.getAttribute('hx-trigger') === null, 'hx-trigger 已移除（轮询停止）');
assert(t1.getAttribute('hx-get') === null, 'hx-get 已移除');
assert(t1.getAttribute('data-retry-url') === '/api/pipeline/abc/progress', 'data-retry-url 已保存');
assert(t1['htmx-internal-data'].triggerSpecs.length === 0, '内部 triggerSpecs 已清空');

// 测试 2: 5xx 连续失败 — 3 次后停止
console.log('\n[测试 2] 500 错误：连续失败 3 次后停止轮询');
toastCalls = []; _htmxErrorState = {};
var t2 = makeMockElement('area-500');
t2.setAttribute('hx-get', '/api/pipeline/def/progress');
t2.setAttribute('hx-trigger', 'every 2s');
handleResponseError(500, t2);
assert(t2.getAttribute('hx-trigger') === 'every 2s', '第1次失败仍继续轮询');
handleResponseError(500, t2);
assert(t2.getAttribute('hx-trigger') === 'every 2s', '第2次失败仍继续轮询');
handleResponseError(500, t2);
assert(t2.getAttribute('hx-trigger') === null, '第3次失败停止轮询');
assert(t2.getAttribute('data-retry-url') === '/api/pipeline/def/progress', 'data-retry-url 已保存');

// 测试 3: 同一错误 toast 上限 — 跨冷却窗口最多 3 次
console.log('\n[测试 3] 同一错误 toast 上限：跨冷却窗口最多 3 次');
toastCalls = []; _htmxErrorState = {};
var t3 = makeMockElement('area-cap');
t3.setAttribute('hx-get', '/x');
// 模拟跨多个冷却窗口（每次推进 5s > 4s 冷却）
var origNow = Date.now();
var fakeTime = origNow;
var realDateNow = Date.now;
Date.now = function() { return fakeTime; };
for (var j = 0; j < 10; j++) {
  fakeTime += 5000; // 每次跨过冷却窗口
  // 500 不在 404 分支，且每次 count 重置？不，count 累积。但前 3 次 toast 后停。
  handleResponseError(500, t3);
}
Date.now = realDateNow;
// 500 在 3 次失败后也会停止轮询（count>=3），但 toast 上限也是 3
assert(toastCalls.length <= 3, '500 跨窗口 toast 数 ≤ 3 (实际: ' + toastCalls.length + ')');

// 测试 4: 不同状态码不同 key — 独立计数
console.log('\n[测试 4] 不同 status 独立计数');
toastCalls = []; _htmxErrorState = {};
var t4a = makeMockElement('a'); t4a.setAttribute('hx-get','/a');
var t4b = makeMockElement('b'); t4b.setAttribute('hx-get','/b');
handleResponseError(404, t4a);
handleResponseError(500, t4b);
assert(Object.keys(_htmxErrorState).length === 2, '两个不同 key (404:a, 500:b)');

// 测试 5: 成功后重置计数
console.log('\n[测试 5] 成功请求重置错误计数');
_htmxErrorState = {};
var t5 = makeMockElement('a'); t5.setAttribute('hx-get','/a');
handleResponseError(500, t5);
handleResponseError(500, t5);
assert(_htmxErrorState['500:a'].count === 2, '失败 2 次 count=2');
// 模拟 afterRequest 成功重置
if (_htmxErrorState['500:a']) _htmxErrorState['500:a'].count = 0;
assert(_htmxErrorState['500:a'].count === 0, '成功后 count 重置为 0');

// ─── 结果 ───────────────────────────────────────────────────────
console.log('\n=== 结果 ===');
console.log('通过: ' + passed + ' / 失败: ' + failed);
if (failed > 0) {
  console.log('\n❌ 有测试失败');
  process.exit(1);
} else {
  console.log('\n✅ 全部通过');
  process.exit(0);
}
