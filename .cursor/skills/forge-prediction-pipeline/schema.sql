-- DetForge-Studio 模型预测升级 — 写库 DDL
-- 独立新库 detforge（与平台库 vision_backend 同一 MySQL 实例）；表不加前缀。
-- 与 studio/forge/forge_db.py:schema_statements 保持一致；执行入口 POST /api/forge/schema/init。

CREATE DATABASE IF NOT EXISTS detforge DEFAULT CHARSET=utf8mb4;

-- 1. 模型注册（导入/登记模型）
CREATE TABLE IF NOT EXISTS detforge.model_registry (
  id              BIGINT AUTO_INCREMENT PRIMARY KEY,
  name            VARCHAR(255) NOT NULL,
  framework       VARCHAR(32)  NOT NULL COMMENT 'dino | hq_det',
  sub_type        VARCHAR(32)  DEFAULT NULL COMMENT 'hq_det 子类型 rtdetr/yolo/dino/...',
  checkpoint_path TEXT         NOT NULL COMMENT '权重绝对路径',
  labels          JSON         DEFAULT NULL COMMENT '类别名列表',
  source          VARCHAR(32)  DEFAULT 'manual' COMMENT 'manual|modeldeploy|modeltrainconfig',
  source_ref      VARCHAR(64)  DEFAULT NULL COMMENT '来源记录 id',
  approach_id     INT          DEFAULT NULL,
  default_params  JSON         DEFAULT NULL COMMENT '{threshold,max_size,device}',
  enabled         TINYINT      DEFAULT 1,
  c_time          DATETIME     DEFAULT CURRENT_TIMESTAMP,
  u_time          DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_path (checkpoint_path(255))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2. 通用作业（predict / manual_qc_archive 共用，预留 sampling_export）
CREATE TABLE IF NOT EXISTS detforge.job (
  id                BIGINT AUTO_INCREMENT PRIMARY KEY,
  job_type          VARCHAR(32)  NOT NULL COMMENT 'predict | manual_qc_archive',
  name              VARCHAR(255) DEFAULT NULL,
  params            JSON         NOT NULL COMMENT '模型id/阈值/图片来源/items_meta/并发等',
  status            VARCHAR(16)  NOT NULL DEFAULT 'pending' COMMENT 'pending/running/paused/done/failed/canceled',
  priority          INT          DEFAULT 100 COMMENT '越小越先',
  intra_concurrency INT          DEFAULT 1 COMMENT '任务内图片并发',
  total             INT          DEFAULT 0,
  done              INT          DEFAULT 0,
  failed            INT          DEFAULT 0,
  error             TEXT         DEFAULT NULL,
  worker_id         VARCHAR(64)  DEFAULT NULL,
  heartbeat         DATETIME     DEFAULT NULL,
  created_at        DATETIME     DEFAULT CURRENT_TIMESTAMP,
  started_at        DATETIME     DEFAULT NULL,
  finished_at       DATETIME     DEFAULT NULL,
  KEY idx_status (status, priority, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3. 作业项（断点续跑粒度，每图/每 SN 一行）
CREATE TABLE IF NOT EXISTS detforge.job_item (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  job_id      BIGINT       NOT NULL,
  seq         INT          DEFAULT 0,
  ref_key     VARCHAR(512) NOT NULL COMMENT '图片路径 / 批量条目索引',
  status      VARCHAR(16)  NOT NULL DEFAULT 'pending' COMMENT 'pending/running/done/failed/skipped',
  attempts    INT          DEFAULT 0,
  result_ref  BIGINT       DEFAULT NULL COMMENT '指向 predict_result.id / manual_qc.id',
  error       TEXT         DEFAULT NULL,
  updated_at  DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_job (job_id, status),
  UNIQUE KEY uk_job_ref (job_id, ref_key(255))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4. 预测结果（一图一行；ext 与平台同形 → 复用筛选管线）
CREATE TABLE IF NOT EXISTS detforge.predict_result (
  id                BIGINT AUTO_INCREMENT PRIMARY KEY,
  job_id            BIGINT       NOT NULL,
  model_id          BIGINT       NOT NULL,
  model_name        VARCHAR(255) DEFAULT NULL,
  source_detail_id  BIGINT       DEFAULT NULL COMMENT 'vision_backend.product_detection_detail_result.id',
  origin_object_key TEXT         DEFAULT NULL COMMENT '与平台一致，拼 img_path',
  img_path          TEXT         DEFAULT NULL,
  product_no        VARCHAR(128) DEFAULT NULL COMMENT 'SN',
  product_id        VARCHAR(128) DEFAULT NULL,
  product_type      VARCHAR(128) DEFAULT NULL COMMENT '款型',
  position          VARCHAR(128) DEFAULT NULL,
  img_width         INT          DEFAULT NULL,
  img_height        INT          DEFAULT NULL,
  ext               JSON         DEFAULT NULL COMMENT '{original_predictions:[{name,confidence,type,points:[{x,y,w,h}]}]}',
  box_count         INT          DEFAULT 0,
  max_score         FLOAT        DEFAULT NULL,
  threshold         FLOAT        DEFAULT NULL,
  predict_status    VARCHAR(16)  DEFAULT 'done' COMMENT 'done/failed',
  c_time            DATETIME     DEFAULT CURRENT_TIMESTAMP,
  KEY idx_job (job_id),
  KEY idx_sn (product_no),
  KEY idx_type (product_type),
  UNIQUE KEY uk_job_img (job_id, img_path(255))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 5. 人工质检归档（客户图 + SN → 人工选中的平台缺陷图 + 缺陷类型 + 成像情况）
CREATE TABLE IF NOT EXISTS detforge.manual_qc (
  id                 BIGINT AUTO_INCREMENT PRIMARY KEY,
  batch_id           VARCHAR(64)  DEFAULT NULL COMMENT '一次批量归档共享',
  product_no         VARCHAR(128) NOT NULL COMMENT '客户提供 SN',
  customer_img_path  TEXT         DEFAULT NULL COMMENT '导入(拖拽上传)的客户拍摄图',
  matched_detail_id  BIGINT       DEFAULT NULL COMMENT '人工选中的 vision_backend.product_detection_detail_result.id',
  matched_img_path   TEXT         DEFAULT NULL,
  matched_object_key TEXT         DEFAULT NULL,
  defect_info        JSON         DEFAULT NULL COMMENT '选中记录的 ext 缺陷类别/框',
  defect_type        VARCHAR(128) DEFAULT NULL COMMENT '缺陷类型(可配置 manual_qc_defect_types)',
  qc_category        VARCHAR(64)  DEFAULT NULL COMMENT '成像情况(可配置 manual_qc_imaging_categories：成像清晰/成像不清/拍不到…)，导出按此分类筛选',
  product_type       VARCHAR(128) DEFAULT NULL,
  position           VARCHAR(128) DEFAULT NULL,
  match_status       VARCHAR(16)  DEFAULT 'matched' COMMENT 'matched/not_found/multiple',
  note               TEXT         DEFAULT NULL,
  archived_at        DATETIME     DEFAULT CURRENT_TIMESTAMP,
  KEY idx_sn (product_no),
  KEY idx_batch (batch_id),
  KEY idx_category (qc_category),
  KEY idx_archived (archived_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 6. 筛选批次（捞图 → 外部筛选 → 归档 → 训练交接）
CREATE TABLE IF NOT EXISTS detforge.curation_batch (
  id                BIGINT AUTO_INCREMENT PRIMARY KEY,
  batch_code        VARCHAR(64)  NOT NULL,
  source_task_id    VARCHAR(64)  NOT NULL,
  strategy_id       VARCHAR(128) DEFAULT NULL,
  strategy_name     VARCHAR(255) DEFAULT NULL,
  data_source       VARCHAR(32)  DEFAULT 'detail',
  status            VARCHAR(32)  NOT NULL DEFAULT 'created',
  reviewer          VARCHAR(128) DEFAULT NULL,
  note              TEXT         DEFAULT NULL,
  total_count       INT          DEFAULT 0,
  keep_count        INT          DEFAULT 0,
  reject_count      INT          DEFAULT 0,
  pending_count     INT          DEFAULT 0,
  export_dir        TEXT         DEFAULT NULL,
  archive_dir       TEXT         DEFAULT NULL,
  handoff_dir       TEXT         DEFAULT NULL,
  sync_dataset_id   BIGINT       DEFAULT NULL,
  created_at        DATETIME     DEFAULT CURRENT_TIMESTAMP,
  exported_at       DATETIME     DEFAULT NULL,
  imported_at       DATETIME     DEFAULT NULL,
  archived_at       DATETIME     DEFAULT NULL,
  handoff_at        DATETIME     DEFAULT NULL,
  UNIQUE KEY uk_batch_code (batch_code),
  KEY idx_status (status),
  KEY idx_task (source_task_id),
  KEY idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS detforge.curation_item (
  id                  BIGINT AUTO_INCREMENT PRIMARY KEY,
  batch_id            BIGINT       NOT NULL,
  batch_row_id        VARCHAR(96)  NOT NULL,
  seq                 INT          DEFAULT 0,
  img_name            VARCHAR(512) DEFAULT NULL,
  img_path            TEXT         DEFAULT NULL,
  product_no          VARCHAR(128) DEFAULT NULL,
  product_type        VARCHAR(128) DEFAULT NULL,
  check_status        VARCHAR(32)  DEFAULT NULL,
  categories_summary  VARCHAR(512) DEFAULT NULL,
  decision            VARCHAR(16)  DEFAULT 'pending' COMMENT 'keep|reject|pending',
  reject_reason       VARCHAR(255) DEFAULT NULL,
  note                TEXT         DEFAULT NULL,
  source_meta         JSON         DEFAULT NULL,
  KEY idx_batch (batch_id),
  KEY idx_decision (batch_id, decision),
  UNIQUE KEY uk_batch_row (batch_id, batch_row_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
