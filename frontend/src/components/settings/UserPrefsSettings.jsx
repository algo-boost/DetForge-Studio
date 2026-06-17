import { Link } from 'react-router-dom';
import { navGroupsForTier, USER_TIERS } from '../../config/nav';
import { useUserPrefs } from '../../context/UserPrefsContext';
import ModeSwitch from '../ModeSwitch';

export default function UserPrefsSettings() {
  const {
    tier,
    defaultHome,
    defaultHomeOverride,
    setDefaultHome,
    resetDefaultHome,
  } = useUserPrefs();

  const suggestedHome = tier === USER_TIERS.OPERATOR ? '/' : '/flows/compose';

  const homeOptions = [];
  for (const group of navGroupsForTier(tier)) {
    for (const item of group.items) {
      if (item.to.startsWith('__')) continue;
      homeOptions.push({ path: item.to, label: `${group.label} · ${item.label}` });
    }
  }

  return (
    <section className="platform-surface-card settings-surface-card">
      <div className="platform-surface-card-head settings-surface-head">
        <div>
          <h4>界面偏好</h4>
          <p className="settings-surface-desc">
            作业模式精简导航；配置模式显示策略、流水线与工具箱等完整能力。也可在顶栏随时切换。
          </p>
        </div>
      </div>
      <div className="config-card-body config-grid-2 settings-form">
        <div className="config-field config-span-2">
          <label>使用模式</label>
          <ModeSwitch />
        </div>
        <div className="config-field config-span-2">
          <label htmlFor="prefs-home">默认首页</label>
          <select
            id="prefs-home"
            value={defaultHomeOverride || suggestedHome}
            onChange={(e) => {
              const v = e.target.value;
              if (v === suggestedHome) resetDefaultHome();
              else setDefaultHome(v);
            }}
          >
            {homeOptions.map((opt) => (
              <option key={opt.path} value={opt.path}>{opt.label} ({opt.path})</option>
            ))}
          </select>
          <p className="config-hint">
            当前生效：<code>{defaultHome}</code>
            {defaultHomeOverride ? '（已自定义）' : '（默认）'}
            {' · '}
            按 <kbd>⌘K</kbd> 打开命令面板快速跳转。
            <Link to="/"> 返回工作台</Link>
          </p>
        </div>
      </div>
    </section>
  );
}
