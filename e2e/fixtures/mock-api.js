/** Playwright 路由 mock：在无 MySQL 时支撑完整 UI 链路测试。 */
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export const E2E_TASK_ID = 'e2e-task-001';
export const E2E_JOB_ID = 9001;

const TINY_PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
  'base64',
);

const MINI_ZIP = Buffer.from([
  0x50, 0x4b, 0x03, 0x04, 0x0a, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
  0x50, 0x4b, 0x05, 0x06, 0x00, 0x00, 0x00, 0x00, 0x01, 0x00,
  0x01, 0x00, 0x1e, 0x00, 0x00, 0x00, 0x1e, 0x00, 0x00, 0x00,
  0x00, 0x00,
]);

export const SAMPLE_QUERY_ROWS = [
  {
    img_name: 'e2e_sample_001.jpg',
    img_path: '/tmp/e2e_sample_001.jpg',
    check_status: '1',
    product_no: 'SN-E2E-001',
    product_type: 'TestPanel',
    product_id: 'PID-E2E-1',
    position: 'front',
    c_time: '2026-05-30 12:00:00',
    annotations: [{ category: 'scratch', score: 0.92, bbox: [10, 20, 30, 40] }],
  },
  {
    img_name: 'e2e_sample_002.jpg',
    img_path: '/tmp/e2e_sample_002.jpg',
    check_status: '0',
    product_no: 'SN-E2E-002',
    product_type: 'TestPanel',
    c_time: '2026-05-30 13:00:00',
    annotations: [],
  },
];

const MOCK_JOBS = [
  {
    id: E2E_JOB_ID,
    job_type: 'predict',
    name: 'E2E 预测 · TestModel',
    status: 'done',
    done: 2,
    total: 2,
    params: { model_name: 'TestModel' },
    c_time: '2026-05-30T14:00:00',
  },
];

const MOCK_CURATION_ITEMS = [
  {
    id: 1,
    batch_row_id: 'cb_e2e-r00001',
    img_name: 'e2e_sample_001.jpg',
    product_no: 'SN-E2E-001',
    product_type: 'TestPanel',
    decision: 'pending',
    disposition: 'ng_confirmed',
    need_platform_label: 0,
    check_status: '1',
  },
  {
    id: 2,
    batch_row_id: 'cb_e2e-r00002',
    img_name: 'e2e_sample_002.jpg',
    product_no: 'SN-E2E-002',
    product_type: 'TestPanel',
    decision: 'pending',
    disposition: 'fn_missed',
    need_platform_label: 1,
    check_status: '0',
  },
];

let mockCurationBatch = null;

function defaultCurationBatch(overrides = {}) {
  return {
    id: 701,
    batch_code: 'cb_e2e_replay_001',
    source_task_id: E2E_TASK_ID,
    strategy_id: `replay_job_${E2E_JOB_ID}`,
    strategy_name: `回跑 #${E2E_JOB_ID} · TestModel`,
    data_source: 'predict_result',
    intent_type: 'replay_eval',
    status: 'created',
    total_count: 2,
    keep_count: 0,
    reject_count: 0,
    pending_count: 2,
    export_dir: null,
    archive_dir: null,
    handoff_dir: null,
    ...overrides,
  };
}

function archiveHandoffPayload() {
  const batches = mockCurationBatch ? [mockCurationBatch] : [];
  return {
    curation_batches: batches,
    manual_qc_summary: { pending: 1, handoff_ready: 0, closed: 0, total: 1 },
    total_curation: batches.length,
  };
}

const MOCK_REGISTRY_MODEL = {
  id: 501,
  name: 'E2E-Registry-Model',
  framework: 'pytorch',
  sub_type: 'detection',
  source: 'manual',
  enabled: true,
  path_resolvable: true,
};

const MOCK_MQC_RECORDS = [
  {
    id: 1,
    product_no: 'SN-E2E-001',
    qc_category: '拍不到',
    defect_type: '划伤',
    match_status: 'matched',
    customer_img_path: '/uploads/manual_qc/e2e/customer.jpg',
    platform_img_path: '/uploads/manual_qc/e2e/platform.jpg',
    archived_at: '2026-05-30 15:00:00',
  },
];

const MOCK_STRATEGIES = [
  { id: 'daily_trawl', name: '日常捞图', sql_template: 'SELECT 1' },
  { id: 'replay_post_ng', name: '回跑后筛 FP', sql_template: 'SELECT * FROM predict_result WHERE job_id = ${JOB_ID}' },
];

function json(route, body, status = 200) {
  return route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

function pathname(url) {
  try {
    return new URL(url).pathname;
  } catch {
    return url;
  }
}

/**
 * 安装 API mock；未匹配的 /api/* 请求继续走真实 Flask。
 * @param {import('@playwright/test').Page} page
 */
export async function installApiMocks(page) {
  mockCurationBatch = null;
  const context = page.context();
  await context.route('**/api/**', async (route) => {
    const req = route.request();
    const p = pathname(req.url());
    const method = req.method();

    // ── 查询 ──
    if (p === '/api/query' && method === 'POST') {
      return json(route, {
        success: true,
        data: SAMPLE_QUERY_ROWS,
        count: SAMPLE_QUERY_ROWS.length,
        task_id: E2E_TASK_ID,
        input_rows: SAMPLE_QUERY_ROWS.length,
        output_rows: SAMPLE_QUERY_ROWS.length,
        sample_size: 300,
        post_sample_skipped: false,
      });
    }

    if (p === '/api/preview-filter' && method === 'POST') {
      return json(route, {
        success: true,
        count: SAMPLE_QUERY_ROWS.length,
        preview_count: Math.min(5, SAMPLE_QUERY_ROWS.length),
        message: '预览完成',
      });
    }

    if (p === '/api/strategies' && method === 'GET') {
      return json(route, { success: true, data: MOCK_STRATEGIES });
    }

    const strategyVars = p.match(/^\/api\/strategies\/([^/]+)\/variables$/);
    if (strategyVars && method === 'GET') {
      const sid = strategyVars[1];
      const custom = sid === 'replay_post_ng'
        ? [
          { key: 'MIN_SCORE', label: '最低 max_score', type: 'number', default: '0.1' },
          { key: 'PRODUCT_TYPE', label: '款型过滤', type: 'text' },
        ]
        : [];
      return json(route, {
        success: true,
        data: { strategy_id: sid, custom_vars: custom, template_vars: [], system_vars: [] },
      });
    }

    // ── 导出 ──
    if (p.startsWith('/api/export/') && (method === 'GET' || method === 'POST')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/zip',
        headers: { 'Content-Disposition': `attachment; filename="coco_${E2E_TASK_ID}.zip"` },
        body: MINI_ZIP,
      });
    }

    if (p.startsWith('/api/export-csv/')) {
      return route.fulfill({
        status: 200,
        contentType: 'text/csv',
        body: 'img_name,check_status\n',
      });
    }

    // ── 图片 ──
    if (p.startsWith('/api/image/')) {
      return route.fulfill({
        status: 200,
        contentType: 'image/png',
        body: TINY_PNG,
      });
    }

    // ── Forge 预测 ──
    if (p === '/api/forge/schema/status' && method === 'GET') {
      return json(route, { success: true, database: 'detforge_e2e', ready: true });
    }

    if (p === '/api/forge/jobs' && method === 'GET') {
      return json(route, { success: true, total: MOCK_JOBS.length, data: MOCK_JOBS });
    }

    if (p === '/api/forge/jobs/predict' && method === 'POST') {
      return json(route, {
        success: true,
        model_count: 1,
        total_images: 2,
        jobs: [{ job_id: E2E_JOB_ID, model_name: 'E2E-Registry-Model' }],
      });
    }

    if (p === `/api/forge/jobs/${E2E_JOB_ID}` && method === 'GET') {
      return json(route, {
        success: true,
        data: { ...MOCK_JOBS[0], log: 'E2E mock job done' },
      });
    }

    if (p === `/api/forge/jobs/${E2E_JOB_ID}/log` && method === 'GET') {
      return json(route, { success: true, lines: ['E2E mock predict done'] });
    }

    if (p === `/api/forge/jobs/${E2E_JOB_ID}/items` && method === 'GET') {
      return json(route, { success: true, data: [], total: 0 });
    }

    if (p === `/api/forge/jobs/${E2E_JOB_ID}/results` && method === 'GET') {
      return json(route, { success: true, data: [], total: 2 });
    }

    if (p === '/api/forge/models' && method === 'GET') {
      return json(route, { success: true, data: [MOCK_REGISTRY_MODEL] });
    }

    if (p === '/api/forge/predict-result/source' && method === 'GET') {
      return json(route, {
        success: true,
        table: '`detforge`.`predict_result`',
        default_sql: 'SELECT * FROM `detforge`.`predict_result`',
      });
    }

    // ── 训练平台项目（在线预测页） ──
    if (p === '/api/forge/sync/projects' && method === 'GET') {
      return json(route, {
        success: true,
        data: [{ id: 1, name: 'E2E Project', approach_id: 598 }],
      });
    }

    if (p === '/api/forge/sync/datasets' && method === 'GET') {
      return json(route, { success: true, data: [] });
    }

    if (p === '/api/deployed-models' && method === 'GET') {
      return json(route, { success: true, models: [] });
    }

    if (p === '/api/training-models' && method === 'GET') {
      return json(route, { success: true, models: [] });
    }

    // ── Viz / Unify ──
    if (p === '/api/viz/status') {
      return json(route, { success: true, available: false, mount_prefix: '/viz' });
    }

    if (p === '/api/unify/status') {
      return json(route, {
        success: true,
        available: false,
        mounted: false,
        mount_prefix: '/unify',
        viewer_path: '/online-predict',
      });
    }

    // ── 人工质检 ──
    if (p === '/api/forge/manual-qc/categories' && method === 'GET') {
      return json(route, {
        success: true,
        imaging_categories: ['拍不到', '拍到了'],
        defect_types: ['划伤', '破损'],
        defect_strict: false,
      });
    }

    if (p === '/api/forge/manual-qc' && method === 'GET') {
      return json(route, {
        success: true,
        data: MOCK_MQC_RECORDS,
        total: MOCK_MQC_RECORDS.length,
      });
    }

    if (p === '/api/forge/manual-qc/upload' && method === 'POST') {
      return json(route, {
        success: true,
        data: [{ path: '/uploads/manual_qc/e2e/customer.jpg', name: 'e2e-upload.jpg' }],
      });
    }

    if (p === '/api/forge/manual-qc/lookup' && method === 'GET') {
      const sn = new URL(req.url()).searchParams.get('sn') || '';
      const records = sn.includes('E2E') || sn.includes('SN')
        ? [{ id: 101, img_path: '/tmp/platform.jpg', product_no: sn, defect_type: '划伤' }]
        : [];
      return json(route, { success: true, sn, count: records.length, records });
    }

    if (p === '/api/forge/manual-qc/export' && method === 'POST') {
      const body = req.postDataJSON() || {};
      if (body.async) {
        return json(route, { success: true, mode: 'async', job_id: 8001 });
      }
      return json(route, {
        success: true,
        copied: 1,
        records: 1,
        missing: 0,
        out_dir: '/tmp/e2e-mqc-export',
      });
    }

    if (p === '/api/forge/manual-qc' && method === 'POST') {
      return json(route, { success: true, id: 999 });
    }

    // ── 筛选归档 / 历史回跑 ──
    if (p === '/api/forge/archive-handoff' && method === 'GET') {
      return json(route, { success: true, ...archiveHandoffPayload() });
    }

    if (p === '/api/forge/replay-eval/preview' && method === 'POST') {
      return json(route, {
        success: true,
        job_id: E2E_JOB_ID,
        filter_mode: 'ng_only',
        counts: { total_all: 2, matched: 2, ng_boxes: 2, zero_boxes: 0 },
        sample: [
          { id: 1, product_no: 'SN-E2E-001', product_type: 'TestPanel', box_count: 1, max_score: 0.92 },
        ],
        job: { id: E2E_JOB_ID, model_name: 'TestModel', status: 'done', done: 2, total: 2 },
      });
    }

    if (p === '/api/forge/replay-eval/create' && method === 'POST') {
      mockCurationBatch = defaultCurationBatch();
      return json(route, {
        success: true,
        task_id: E2E_TASK_ID,
        matched_count: 2,
        filter_mode: 'ng_only',
        batch: mockCurationBatch,
      });
    }

    if (p === '/api/forge/replay-runs/preview' && method === 'POST') {
      return json(route, {
        success: true,
        stages: {
          stage1: { count: 42, data_source: 'detail' },
        },
      });
    }

    if (p === '/api/forge/replay-runs/variables' && method === 'POST') {
      return json(route, {
        success: true,
        stages: {},
        system_preview: {
          START_TIME: '2026-05-29 00:00:00',
          END_TIME: '2026-05-29 23:59:59',
          THRESHOLD: '0.1',
        },
      });
    }

    if (p === '/api/forge/replay-runs' && method === 'POST') {
      return json(route, {
        success: true,
        data: {
          id: 8801,
          status: 'running',
          stage: 'stage1',
          spec_json: {},
        },
      });
    }

    const replayRunDetail = p.match(/^\/api\/forge\/replay-runs\/(\d+)$/);
    if (replayRunDetail && method === 'GET') {
      return json(route, {
        success: true,
        data: {
          id: Number(replayRunDetail[1]),
          status: 'done',
          stage: 'done',
          curation_batch_id: 701,
          result_json: { curation: { batch_id: 701 } },
        },
      });
    }

    if (p === '/api/forge/curation' && method === 'GET') {
      const data = mockCurationBatch ? [mockCurationBatch] : [];
      return json(route, { success: true, data, total: data.length });
    }

    if (p === '/api/forge/curation' && method === 'POST') {
      mockCurationBatch = defaultCurationBatch({
        id: 702,
        batch_code: 'cb_e2e_query_001',
        intent_type: 'daily_ng',
        strategy_id: 'daily_trawl',
        strategy_name: 'Daily Trawl',
        data_source: 'detail',
      });
      return json(route, { success: true, data: mockCurationBatch });
    }

    const curationDetail = p.match(/^\/api\/forge\/curation\/(\d+)$/);
    if (curationDetail && method === 'GET') {
      const batch = mockCurationBatch || defaultCurationBatch({ id: Number(curationDetail[1]) });
      return json(route, { success: true, data: batch });
    }

    if (curationDetail && method === 'DELETE') {
      const id = Number(curationDetail[1]);
      if (mockCurationBatch?.id === id) mockCurationBatch = null;
      return json(route, { success: true, id, batch_code: 'cb_deleted' });
    }

    const curationItems = p.match(/^\/api\/forge\/curation\/(\d+)\/items$/);
    if (curationItems && method === 'GET') {
      return json(route, { success: true, data: MOCK_CURATION_ITEMS, total: MOCK_CURATION_ITEMS.length });
    }

    const curationExport = p.match(/^\/api\/forge\/curation\/(\d+)\/export$/);
    if (curationExport && method === 'POST') {
      if (mockCurationBatch) {
        mockCurationBatch = { ...mockCurationBatch, status: 'exported', export_dir: '/tmp/e2e-curation-export' };
      }
      return json(route, {
        success: true,
        out_dir: '/tmp/e2e-curation-export',
        batch_code: mockCurationBatch?.batch_code || 'cb_e2e',
        items: 2,
        images_copied: 2,
      });
    }

    const curationImport = p.match(/^\/api\/forge\/curation\/(\d+)\/import$/);
    if (curationImport && method === 'POST') {
      if (mockCurationBatch) {
        mockCurationBatch = {
          ...mockCurationBatch,
          status: 'imported',
          keep_count: 1,
          reject_count: 1,
          pending_count: 0,
          imported_at: '2026-05-30 16:00:00',
        };
      }
      return json(route, {
        success: true,
        matched_keep: 1,
        keep: 1,
        reject: 1,
      });
    }

    const curationArchive = p.match(/^\/api\/forge\/curation\/(\d+)\/archive$/);
    if (curationArchive && method === 'POST') {
      if (mockCurationBatch) {
        mockCurationBatch = {
          ...mockCurationBatch,
          status: 'archived',
          archive_dir: '/tmp/e2e-curation-archive',
        };
      }
      return json(route, {
        success: true,
        archive_dir: '/tmp/e2e-curation-archive',
        keep_count: 1,
        batch: mockCurationBatch,
      });
    }

    const curationHandoff = p.match(/^\/api\/forge\/curation\/(\d+)\/handoff$/);
    if (curationHandoff && method === 'POST') {
      if (mockCurationBatch) {
        mockCurationBatch = {
          ...mockCurationBatch,
          status: 'handoff_ready',
          handoff_dir: '/tmp/e2e-training-inbox/cb_e2e',
        };
      }
      return json(route, {
        success: true,
        handoff_dir: '/tmp/e2e-training-inbox/cb_e2e',
        keep_count: 1,
        packs: { all_kept: {}, to_label: {} },
        batch: mockCurationBatch,
      });
    }

    return route.continue();
  });
}

export function testImagePath() {
  return path.join(__dirname, 'test-image.png');
}

export function ensureTestImage() {
  const p = testImagePath();
  if (!fs.existsSync(p)) {
    fs.writeFileSync(p, TINY_PNG);
  }
  return p;
}
