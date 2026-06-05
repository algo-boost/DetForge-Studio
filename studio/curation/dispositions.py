"""样本处置标签：三场景（每日捞 / 历史回跑 / 人工质检）统一枚举。"""

INTENT_DAILY_NG = 'daily_ng'
INTENT_REPLAY_EVAL = 'replay_eval'
INTENT_CUSTOMER_QC = 'customer_qc'

INTENT_LABELS = {
    INTENT_DAILY_NG: '每日 NG 捞取',
    INTENT_REPLAY_EVAL: '历史回跑评测',
    INTENT_CUSTOMER_QC: '人工质检',
}

# 筛选归档 COCO / 条目 disposition
DISP_NG_CONFIRMED = 'ng_confirmed'
DISP_NEED_LABEL = 'need_label'
DISP_FP_MODEL = 'fp_model'
DISP_FN_MISSED = 'fn_missed'
DISP_TP_DETECTED = 'tp_detected'
DISP_QC_NO_SHOT = 'qc_no_shot'
DISP_QC_BLUR = 'qc_blur'
DISP_QC_MATCHED = 'qc_matched'
DISP_REJECTED = 'rejected'

DISPOSITION_LABELS = {
    DISP_NG_CONFIRMED: '确认 NG',
    DISP_NEED_LABEL: '待平台打标',
    DISP_FP_MODEL: '模型误检',
    DISP_FN_MISSED: '漏检',
    DISP_TP_DETECTED: '已检出',
    DISP_QC_NO_SHOT: '拍不到',
    DISP_QC_BLUR: '成像不清',
    DISP_QC_MATCHED: '质检已对齐',
    DISP_REJECTED: '已剔除',
}

# 人工质检成像类别 → disposition（兼容旧配置项）
QC_CATEGORY_TO_DISPOSITION = {
    '未拍到': DISP_QC_NO_SHOT,
    '拍不到': DISP_QC_NO_SHOT,
    '成像不清': DISP_QC_BLUR,
    '成像不清晰': DISP_QC_BLUR,
    '检出': DISP_TP_DETECTED,
    '漏检': DISP_FN_MISSED,
    '成像清晰': DISP_QC_MATCHED,
    '拍到了': DISP_QC_MATCHED,
}

TRAINING_PENDING = 'pending'
TRAINING_HANDOFF_READY = 'handoff_ready'
TRAINING_CLOSED = 'closed'


def normalize_disposition(raw, default=DISP_NG_CONFIRMED):
    if raw is None:
        return default
    s = str(raw).strip().lower()
    if not s:
        return default
    aliases = {
        'ng': DISP_NG_CONFIRMED,
        'confirmed': DISP_NG_CONFIRMED,
        '确认ng': DISP_NG_CONFIRMED,
        'need_label': DISP_NEED_LABEL,
        '待打标': DISP_NEED_LABEL,
        '打标': DISP_NEED_LABEL,
        'label': DISP_NEED_LABEL,
        'fp': DISP_FP_MODEL,
        '误检': DISP_FP_MODEL,
        'fn': DISP_FN_MISSED,
        '漏检': DISP_FN_MISSED,
        'tp': DISP_TP_DETECTED,
        '检出': DISP_TP_DETECTED,
        'reject': DISP_REJECTED,
        '剔除': DISP_REJECTED,
    }
    if s in aliases:
        return aliases[s]
    if s in DISPOSITION_LABELS:
        return s
    return default


def disposition_from_qc_record(record):
    """从 manual_qc 行推断 disposition。"""
    if record.get('match_status') == 'not_found' or record.get('no_match'):
        return DISP_QC_NO_SHOT
    cat = str(record.get('qc_category') or '').strip()
    if cat in QC_CATEGORY_TO_DISPOSITION:
        d = QC_CATEGORY_TO_DISPOSITION[cat]
        if d == DISP_QC_MATCHED and record.get('defect_type'):
            # 有缺陷类型且匹配到平台图：漏检 vs 已检出来自业务标注（note 或 defect）
            note = str(record.get('note') or '')
            if '漏检' in note:
                return DISP_FN_MISSED
        return d
    if record.get('matched_detail_id'):
        return DISP_FN_MISSED
    return DISP_QC_MATCHED


def need_platform_label(disposition):
    return disposition in (DISP_NEED_LABEL, DISP_FN_MISSED, DISP_FP_MODEL)


def parse_image_disposition(img, default=DISP_NG_CONFIRMED):
    """从 COCO image 条目解析 disposition / need_label。"""
    if not isinstance(img, dict):
        return default, False
    extra = img.get('extra') if isinstance(img.get('extra'), dict) else {}
    attrs = img.get('attributes') if isinstance(img.get('attributes'), dict) else {}
    for src in (img, extra, attrs):
        if src.get('disposition'):
            d = normalize_disposition(src.get('disposition'), default=default)
            nl = need_platform_label(d) or _truthy(src.get('need_platform_label') or src.get('need_label'))
            return d, nl
    for src in (img, extra, attrs):
        if _truthy(src.get('need_platform_label') or src.get('need_label')):
            return DISP_NEED_LABEL, True
    return default, False


def _truthy(v):
    if v is True or v == 1:
        return True
    return str(v).strip().lower() in ('1', 'true', 'yes', 'y', '是')
