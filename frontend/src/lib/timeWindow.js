import { formatEnvDateTime } from './envVars';
import { setTimePreset } from './time';

/** 运行级 preset → 前端 env 预览 */
export function runTimeWindowToEnv(spec) {
  if (spec?.start_time && spec?.end_time) {
    return { START_TIME: spec.start_time, END_TIME: spec.end_time };
  }
  const preset = spec?.preset || 'yesterday';
  const mapped = preset === 'last_7d' ? '7days' : preset;
  const r = setTimePreset(mapped === 'last_7d' ? '7days' : mapped);
  return {
    START_TIME: formatEnvDateTime(r.start),
    END_TIME: formatEnvDateTime(r.end),
  };
}
