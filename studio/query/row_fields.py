"""查询结果行字段归一化（SN / 型号 / 产品 ID）。"""
import pandas as pd


def _row_cell_str(row, *cols):
    for col in cols:
        if col not in row.index:
            continue
        val = row.get(col)
        if val is None or (isinstance(val, float) and pd.isna(val)):
            continue
        text = str(val).strip()
        if text and text.lower() != 'nan':
            return text
    return ''


def sn_from_path(path):
    parts = str(path or '').replace('\\', '/').split('/')
    for i, part in enumerate(parts):
        if part == 'process' and i > 0:
            cand = parts[i - 1].strip()
            if cand.isdigit() and len(cand) >= 8:
                return cand
    return ''


def normalize_result_row_fields(row):
    """与 vision_backend 列名一致。

    - 产品型号 → product_type（空时用 result_product_type）
    - SN 码     → product_no（及 SN/sn/code 别名）
    - 产品 ID   → product_id
    """
    product_no = _row_cell_str(row, 'product_no', 'SN', 'sn', 'code')
    product_id = _row_cell_str(row, 'product_id')
    product_type = _row_cell_str(row, 'product_type') or _row_cell_str(row, 'result_product_type')

    if not product_no:
        product_no = sn_from_path(row.get('origin_object_key')) or sn_from_path(row.get('img_path'))

    return {
        'product_no': product_no,
        'product_id': product_id,
        'product_type': product_type,
        'position': _row_cell_str(row, 'position'),
        'defect_type': _row_cell_str(row, 'defect_type'),
    }


def enrich_df_product_fields(df):
    """在 DataFrame 层补全型号/SN（不覆盖已有非空值）。"""
    if df is None or df.empty:
        return df
    out = df.copy()
    if 'product_no' not in out.columns:
        out['product_no'] = ''
    if 'product_type' not in out.columns:
        out['product_type'] = ''
    if 'result_product_type' not in out.columns:
        out['result_product_type'] = ''

    for idx in out.index:
        norm = normalize_result_row_fields(out.loc[idx])
        for col in ('product_no', 'product_id', 'product_type', 'position'):
            cur = out.at[idx, col] if col in out.columns else ''
            if pd.isna(cur) or str(cur).strip() == '':
                if col in out.columns and norm.get(col):
                    out.at[idx, col] = norm[col]
        pt = out.at[idx, 'product_type'] if 'product_type' in out.columns else ''
        rpt = out.at[idx, 'result_product_type'] if 'result_product_type' in out.columns else ''
        if (pd.isna(pt) or str(pt).strip() == '') and rpt and str(rpt).strip():
            out.at[idx, 'product_type'] = str(rpt).strip()
    return out
