// 把 datetime-local 的值（YYYY-MM-DDTHH:mm）转成 MySQL DATETIME 字符串。
export function toSqlTime(local) {
  if (!local) return '';
  const s = local.replace('T', ' ');
  return s.length === 16 ? `${s}:00` : s;
}

// 从批量行里筛出可归档的条目（必须有 SN）。
export function buildArchiveEntries(rows) {
  return (rows || [])
    .filter((r) => (r.sn || '').trim())
    .map((r) => ({
      product_no: r.sn.trim(),
      customer_img_path: r.path || undefined,
      defect_type: (r.defect_type || '').trim() || undefined,
      qc_category: r.qc_category || undefined,
      note: (r.note || '').trim() || undefined,
    }));
}
