export const DEFAULT_RESULT_FILTER = {
  timeStart: '',
  timeEnd: '',
  productType: '',
  productNo: '',
  productId: '',
  position: '',
  status: '',
  category: '',
  minScore: '',
  name: '',
};

export function getProductType(item) {
  return item?.product_type || item?.result_product_type || '';
}

/** SN 码：仅 product_no（及 SN 别名），不含 product_id */
export function getProductNo(item) {
  return item?.product_no || item?.SN || '';
}

function parseTime(val) {
  if (!val) return NaN;
  const s = String(val).trim().replace(' ', 'T');
  const t = new Date(s).getTime();
  return Number.isFinite(t) ? t : NaN;
}

function timeInRange(cTime, start, end) {
  if (!start && !end) return true;
  const t = parseTime(cTime);
  if (Number.isNaN(t)) return !(start || end);
  if (start) {
    const s = parseTime(start);
    if (!Number.isNaN(s) && t < s) return false;
  }
  if (end) {
    const e = parseTime(end);
    if (!Number.isNaN(e) && t > e) return false;
  }
  return true;
}

function includesText(haystack, needle) {
  if (!needle) return true;
  return String(haystack || '').includes(needle);
}

export function itemMatchesFilter(item, f) {
  if (!timeInRange(item.c_time, f.timeStart, f.timeEnd)) return false;
  if (f.productType && !includesText(getProductType(item), f.productType)) return false;
  if (f.productNo && !includesText(getProductNo(item), f.productNo)) return false;
  if (f.productId && !includesText(item.product_id, f.productId)) return false;
  if (f.position && !includesText(item.position, f.position)) return false;
  if (f.status) {
    const want = String(f.status);
    if (want === '1' || want === '0') {
      if (String(item.check_status) !== want) return false;
    } else if (/^ng$/i.test(want)) {
      if (String(item.check_status) !== '1') return false;
    } else if (/^ok$/i.test(want)) {
      if (String(item.check_status) !== '0') return false;
    }
  }
  if (f.category && !(item.annotations || []).some((a) => (a.category || '').includes(f.category))) return false;
  if (f.minScore != null && f.minScore !== '') {
    const min = parseFloat(f.minScore);
    if (Number.isFinite(min)) {
      const scores = (item.annotations || []).map((a) => a.score).filter((s) => s != null);
      if (!scores.length || Math.max(...scores) < min) return false;
    }
  }
  if (f.name && !includesText(item.img_name, f.name)) return false;
  return true;
}

export function isFilterActive(f) {
  return Object.entries(f || {}).some(([, v]) => v != null && v !== '');
}

export function collectFilterOptions(rawData) {
  const productTypes = new Set();
  const positions = new Set();
  const productNos = new Set();
  const productIds = new Set();
  const categories = new Set();
  const fileNames = new Set();
  (rawData || []).forEach((item) => {
    const pt = getProductType(item);
    if (pt) productTypes.add(String(pt));
    if (item.position) positions.add(String(item.position));
    if (item.product_no) productNos.add(String(item.product_no));
    else if (item.SN) productNos.add(String(item.SN));
    if (item.product_id) productIds.add(String(item.product_id));
    if (item.img_name) fileNames.add(String(item.img_name));
    (item.annotations || []).forEach((a) => {
      if (a.category) categories.add(String(a.category));
    });
  });
  const sortLimit = (set, max = 80) => [...set].sort().slice(0, max);
  return {
    productTypes: sortLimit(productTypes),
    positions: sortLimit(positions),
    productNos: sortLimit(productNos),
    productIds: sortLimit(productIds),
    categories: sortLimit(categories),
    fileNames: sortLimit(fileNames),
  };
}

export function buildFilterHint(filter) {
  const parts = [];
  if (filter.timeStart || filter.timeEnd) {
    const a = filter.timeStart ? filter.timeStart.replace('T', ' ') : '…';
    const b = filter.timeEnd ? filter.timeEnd.replace('T', ' ') : '…';
    parts.push(`检测时间 ${a} ~ ${b}`);
  }
  if (filter.productType) parts.push(`型号 ${filter.productType}`);
  if (filter.productNo) parts.push(`SN 含「${filter.productNo}」`);
  if (filter.productId) parts.push(`产品 ID 含「${filter.productId}」`);
  if (filter.position) parts.push(`部位 ${filter.position}`);
  if (filter.status === '1') parts.push('状态 NG');
  else if (filter.status === '0') parts.push('状态 OK');
  if (filter.category) parts.push(`类别含「${filter.category}」`);
  if (filter.minScore !== '' && filter.minScore != null) parts.push(`score ≥ ${filter.minScore}`);
  if (filter.name) parts.push(`文件名含「${filter.name}」`);
  return parts;
}
