import { USER_TIERS } from '../config/nav';
import { useUserPrefs } from '../context/UserPrefsContext';

const MODES = [
  { id: USER_TIERS.OPERATOR, label: '作业' },
  { id: USER_TIERS.CONFIGURER, label: '配置' },
];

/**
 * 顶栏双模式切换：作业（精简） / 配置（完整）
 * @param {{ compact?: boolean, className?: string }} props
 */
export default function ModeSwitch({ compact = false, className = '' }) {
  const { tier, setTier } = useUserPrefs();

  return (
    <div
      className={`mode-switch${compact ? ' mode-switch--compact' : ''}${className ? ` ${className}` : ''}`}
      role="radiogroup"
      aria-label="使用模式"
    >
      {MODES.map((mode) => {
        const active = tier === mode.id;
        return (
          <button
            key={mode.id}
            type="button"
            role="radio"
            aria-checked={active}
            className={`mode-switch-btn${active ? ' is-active' : ''}`}
            onClick={() => {
              if (!active) setTier(mode.id);
            }}
          >
            {mode.label}
          </button>
        );
      })}
    </div>
  );
}
