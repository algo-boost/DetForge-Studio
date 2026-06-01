import { test, expect } from '@playwright/test';
import {
  E2E_JOB_ID,
  E2E_TASK_ID,
  SAMPLE_QUERY_ROWS,
  ensureTestImage,
  installApiMocks,
} from '../fixtures/mock-api.js';

async function runQuery(page) {
  await page.goto('/');
  await expect(page.getByTestId('query-execute')).toBeVisible({ timeout: 60_000 });
  await page.locator('#data-source').selectOption('detail');
  await expect(page.getByRole('button', { name: '今天' })).toBeVisible({ timeout: 30_000 });
  await page.getByRole('button', { name: '今天' }).click();
  await page.getByTestId('query-execute').click();
  await expect(page.locator('.image-grid .img-card')).toHaveCount(SAMPLE_QUERY_ROWS.length, { timeout: 30_000 });
}

async function exportCocoZip(page) {
  await page.getByTestId('results-export-toggle').click();
  await expect(page.getByTestId('results-export-coco')).toBeVisible();
  await expect(page.getByText('下载 CSV')).toBeVisible();
  await page.getByTestId('results-export-coco').click();
}

async function openMqcQueryExportTab(page) {
  await page.goto('/manual-qc');
  await expect(page.getByTestId('mqc-tab-query')).toBeVisible({ timeout: 60_000 });
  await page.getByTestId('mqc-tab-query').evaluate((el) => el.click());
  await expect(page.getByTestId('mqc-tab-query')).toHaveClass(/is-active/);
  await expect(page.getByTestId('mqc-query-export-query')).toBeVisible({ timeout: 15_000 });
}

async function createPredictFromResults(page) {
  await page.getByTestId('results-predict').click();
  await expect(page).toHaveURL(new RegExp(`/online-predict\\?task=${E2E_TASK_ID}`));
  await page.getByRole('button', { name: '已注册' }).click();
  await expect(page.getByText('E2E-Registry-Model')).toBeVisible();
  await page.getByText('E2E-Registry-Model').click();
  await Promise.all([
    page.waitForResponse((r) => r.url().includes('/api/forge/jobs/predict') && r.ok()),
    page.getByTestId('predict-submit').click(),
  ]);
  await expect(page.getByText(/已创建.*预测任务/i)).toBeVisible();
}

test.describe('完整业务链路：查询 → 导出 → 预测 → 质检', () => {
  test.beforeEach(async ({ page }) => {
    await installApiMocks(page);
    page.on('dialog', (d) => d.accept());
  });

  test('Step 1：数据查询 — 切换明细表、执行查询、展示结果', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByText('数据查询').first()).toBeVisible();
    await runQuery(page);
    await expect(page.locator('.img-name').first()).toContainText('e2e_sample_001');
  });

  test('Step 2：查询结果 — 导出 COCO ZIP', async ({ page }) => {
    await runQuery(page);
    await exportCocoZip(page);
  });

  test('Step 3：查询结果 — 跳转在线预测并创建任务', async ({ page }) => {
    await runQuery(page);
    await createPredictFromResults(page);
  });

  test('Step 4：预测任务页 — 列表展示 mock 作业', async ({ page }) => {
    await page.goto('/jobs');
    await expect(page.getByText('预测任务').first()).toBeVisible();
    await expect(page.getByText('E2E 预测')).toBeVisible();
    await expect(page.locator('.pjobs-id').filter({ hasText: String(E2E_JOB_ID) })).toBeVisible();
  });

  test('Step 5：人工质检 — 单条归档上传 + SN 匹配', async ({ page }) => {
    const imgPath = ensureTestImage();
    await page.goto('/manual-qc');
    await expect(page.getByText('人工质检').first()).toBeVisible();

    await page.locator('.mqc-dropzone input[type="file"]').setInputFiles(imgPath);
    await expect(page.getByText(/客户图已导入/i)).toBeVisible();

    await page.getByPlaceholder('客户提供 SN').fill('SN-E2E-001');
    await page.getByRole('button', { name: '查图' }).click();
    await expect(page.locator('.mqc-tile').first()).toBeVisible();
  });

  test('Step 6：人工质检 — 查询导出 Tab 查询与导出', async ({ page }) => {
    await openMqcQueryExportTab(page);

    await page.getByTestId('mqc-query-export-query').click();
    await expect(page.locator('.mqc-query-results')).toBeVisible();
    await expect(page.getByText('SN-E2E-001')).toBeVisible();

    await page.getByTestId('mqc-query-export-dir').click();
    await expect(page.locator('.forge-banner-ok')).toContainText(/导出完成/i);
  });

  test('完整链路串联（单会话）', async ({ page }) => {
    const imgPath = ensureTestImage();

    await runQuery(page);
    await exportCocoZip(page);
    await createPredictFromResults(page);

    await page.goto('/jobs');
    await expect(page.locator('.pjobs-id').filter({ hasText: String(E2E_JOB_ID) })).toBeVisible();

    await page.goto('/manual-qc');
    await page.locator('.mqc-dropzone input[type="file"]').setInputFiles(imgPath);
    await page.getByPlaceholder('客户提供 SN').fill('SN-E2E-001');
    await page.getByRole('button', { name: '查图' }).click();
    await expect(page.locator('.mqc-tile').first()).toBeVisible();

    await openMqcQueryExportTab(page);
    await page.getByTestId('mqc-query-export-query').click();
    await page.getByTestId('mqc-query-export-dir').click();
    await expect(page.locator('.forge-banner-ok')).toContainText(/导出完成/i);
  });
});
