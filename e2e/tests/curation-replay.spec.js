import { test, expect } from '@playwright/test';
import { installApiMocks, E2E_JOB_ID, E2E_TASK_ID } from '../fixtures/mock-api.js';

test.describe('筛选归档 · 历史回跑向导', () => {
  test.beforeEach(async ({ page }) => {
    await installApiMocks(page);
    page.on('dialog', (d) => d.accept());
  });

  test('归档页渲染与打开回跑向导', async ({ page }) => {
    await page.goto('/curation');
    await expect(page.getByRole('heading', { name: '筛选归档' })).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId('scene-loop-hub')).toBeVisible();
    await page.getByTestId('hub-start-replay').click();
    await expect(page.getByTestId('replay-eval-wizard')).toBeVisible();
    await expect(page.getByRole('heading', { name: '历史回跑' })).toBeVisible();
  });

  test('回跑向导：选 job → 预览 → 创建批次', async ({ page }) => {
    await page.goto(`/curation?replay=1&job_id=${E2E_JOB_ID}`);
    await expect(page.getByTestId('replay-eval-wizard')).toBeVisible({ timeout: 60_000 });
    await expect(page.getByTestId('replay-job-select')).toHaveValue(String(E2E_JOB_ID));
    await expect(page.getByTestId('replay-preview-matched')).toContainText('2');

    await page.getByTestId('replay-create-batch').click();
    await expect(page).toHaveURL(/\/curation\?id=701/);
    await expect(page.getByRole('heading', { name: 'cb_e2e_replay_001' })).toBeVisible();
    await expect(page.getByText('历史回跑').first()).toBeVisible();
  });

  test('删除批次需二次确认', async ({ page }) => {
    await page.goto(`/curation?replay=1&job_id=${E2E_JOB_ID}`);
    await page.getByTestId('replay-create-batch').click();
    await expect(page.getByTestId('curation-delete-batch')).toBeVisible({ timeout: 60_000 });
    await page.getByTestId('curation-delete-batch').click();
    await expect(page.getByTestId('curation-delete-confirm')).toBeVisible();
    await page.getByTestId('curation-delete-confirm').click();
    await expect(page).not.toHaveURL(/id=701/);
  });

  test('筛选归档：出站 → COCO 回传步骤可见', async ({ page }) => {
    await page.goto(`/curation?replay=1&job_id=${E2E_JOB_ID}`);
    await page.getByTestId('replay-create-batch').click();
    await expect(page.getByTestId('curation-flow-progress')).toBeVisible();
    await expect(page.getByTestId('curation-next-step')).toHaveText(/生成出站包/);

    await page.getByTestId('curation-next-step').click();
    await expect(page.getByTestId('curation-next-step')).toHaveText(/上传筛选后的 COCO/);
    await expect(page.getByTestId('curation-export-path')).toContainText('/tmp/e2e-curation-export');
  });

  test('从预测任务页跳转回跑向导', async ({ page }) => {
    await page.goto('/jobs');
    await expect(page.getByText('预测任务').first()).toBeVisible({ timeout: 60_000 });
    await page.locator('.pjobs-table').getByRole('button', { name: '详情', exact: true }).click();
    await expect(page.getByRole('link', { name: '查询页筛选' }).first()).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole('link', { name: '回跑筛选批次' })).toBeVisible();
    await page.getByRole('link', { name: '回跑筛选批次' }).click();
    await expect(page).toHaveURL(new RegExp(`/curation\\?replay=1&job_id=${E2E_JOB_ID}`));
    await expect(page.getByTestId('replay-eval-wizard')).toBeVisible();
  });
});

test.describe('筛选归档 · 查询页创建批次入口', () => {
  test.beforeEach(async ({ page }) => {
    await installApiMocks(page);
  });

  test('查询结果页「归档此批」跳转', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByTestId('query-execute')).toBeVisible({ timeout: 60_000 });
    await page.locator('#data-source').selectOption('detail');
    await expect(page.getByRole('button', { name: '今天' })).toBeVisible({ timeout: 30_000 });
    await page.getByRole('button', { name: '今天' }).click();
    await page.getByTestId('query-execute').click();
    await expect(page.locator('.image-grid .img-card')).toHaveCount(2, { timeout: 45_000 });

    await expect(page.getByTestId('results-create-curation')).toBeVisible();
    await expect(page.getByTestId('results-create-curation')).toHaveText(/归档此批/);
    await page.getByTestId('results-create-curation').click();
    await expect(page).toHaveURL(/\/curation\?id=702/);
    await expect(page.getByRole('heading', { name: 'cb_e2e_query_001' })).toBeVisible();
  });
});
