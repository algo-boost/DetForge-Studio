import { test, expect } from '@playwright/test';
import { installApiMocks } from '../fixtures/mock-api.js';

const SIDEBAR_ROUTES = [
  { path: '/', title: '数据查询' },
  { path: '/history', title: '查询历史' },
  { path: '/online-predict', heading: '在线预测' },
  { path: '/jobs', title: '预测任务' },
  { path: '/models', title: '模型' },
  { path: '/training', heading: '训练平台' },
  { path: '/manual-qc', title: '人工质检' },
  { path: '/curation', title: '筛选归档' },
  { path: '/config', title: '设置' },
];

test.describe('侧栏导航与 SPA 路由', () => {
  test.beforeEach(async ({ page }) => {
    await installApiMocks(page);
  });

  for (const route of SIDEBAR_ROUTES) {
    test(`访问 ${route.path} 渲染主界面`, async ({ page }) => {
      await page.goto(route.path);
      if (route.heading) {
        await expect(page.getByRole('heading', { name: route.heading })).toBeVisible();
      } else {
        await expect(page.getByText(route.title).first()).toBeVisible();
      }
    });
  }

  test('预测场景 Hub Tab 切换', async ({ page }) => {
    await page.goto('/online-predict');
    await expect(page.getByRole('heading', { name: '在线预测' })).toBeVisible();
    await page.getByRole('link', { name: '预测任务' }).first().click();
    await expect(page).toHaveURL(/\/jobs/);
  });

  test('查询场景 Hub Tab 切换', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: '查询历史' }).first().click();
    await expect(page).toHaveURL(/\/history/);
  });
});
