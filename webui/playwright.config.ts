import { defineConfig, devices } from '@playwright/test'

/**
 * Playwright 端到端测试配置
 *
 * 策略：
 *  - 前端 e2e 通过 page.route() 拦截 /api/v1/* 请求，注入确定性 mock 响应，
 *    覆盖完整 UI 流程（路由、Pinia store、组件交互、真实 DOM）。
 *  - 后端 API 行为由独立后端 e2e 套件（tests/e2e/）覆盖。
 *  - 这样前端测试不依赖后端运行状态，CI 稳定且快速。
 *
 * 运行：
 *  npx playwright test            # 全部
 *  npx playwright test --ui       # 交互模式
 *  npx playwright test --project=chromium
 *  npx playwright test --grep "Provider"
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
    ['list'],
  ],
  timeout: 30_000,
  expect: { timeout: 7_000 },

  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    // 拦截后端 API（见 e2e/fixtures/api-mocks.ts），默认在 beforeEach 中装配
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'mobile-chromium',
      use: { ...devices['Pixel 7'] },
      testMatch: /.*\.spec\.ts/, // 移动端只跑核心流程
    },
  ],

  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
    stdout: 'ignore',
    stderr: 'pipe',
  },
})
