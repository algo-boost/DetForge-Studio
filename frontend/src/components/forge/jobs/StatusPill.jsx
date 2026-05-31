import { STATUS_LABEL, STATUS_PILL_CLASS } from './jobUtils';

export default function StatusPill({ status }) {
  const cls = STATUS_PILL_CLASS[status] || 'pjobs-pill';
  return <span className={cls}>{STATUS_LABEL[status] || status || '—'}</span>;
}

export { STATUS_LABEL };
