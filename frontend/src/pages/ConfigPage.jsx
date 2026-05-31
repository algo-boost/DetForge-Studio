import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import SettingsTabBar, { StatusPill } from '../components/settings/SettingsTabBar';
import {
  id2nameToText, rootsToText, textToId2name, textToRoots,
} from '../components/settings/settingsUtils';
import { api, toast, getApiToken, setApiToken } from '../api/client';

function SurfaceCard({ title, desc, badge, actions, children }) {
  return (
    <section className="platform-surface-card settings-surface-card">
      {(title || actions) && (
        <div className="platform-surface-card-head settings-surface-head">
          <div>
            <div className="settings-surface-title-row">
              {title && <h4>{title}</h4>}
              {badge}
            </div>
            {desc && <p className="settings-surface-desc">{desc}</p>}
          </div>
          {actions && <div className="settings-surface-actions">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

function ReadonlyRow({ label, value }) {
  return (
    <div className="settings-readonly-row">
      <span className="settings-readonly-label">{label}</span>
      <code className="settings-readonly-value">{value ?? '—'}</code>
    </div>
  );
}

export default function ConfigPage({ embedded = false }) {
  const [config, setConfig] = useState({});
  const [loaded, setLoaded] = useState({});
  const [pathChecks, setPathChecks] = useState({});
  const [dbOk, setDbOk] = useState(null);
  const [mfOk, setMfOk] = useState(null);
  const [clientApiToken, setClientApiToken] = useState(() => getApiToken());
  const [activeTab, setActiveTab] = useState('connection');
  const [id2nameText, setId2nameText] = useState('');
  const [syncRootsText, setSyncRootsText] = useState('');

  const load = async () => {
    const r = await api.getConfig();
    if (r.success) {
      const c = r.config || {};
      setConfig(c);
      setLoaded(c);
      setPathChecks(r.path_checks || {});
      setId2nameText(id2nameToText(c.id2name));
      setSyncRootsText(rootsToText(c.dataset_sync_roots));
      setDbOk(c.db_connected);
      setMfOk(c.magic_fox_configured ? true : null);
    }
  };

  useEffect(() => { load(); }, []);

  const set = (k, v) => setConfig((c) => ({ ...c, [k]: v }));

  const buildSavePayload = () => ({
    ...config,
    id2name: textToId2name(id2nameText),
    dataset_sync_roots: textToRoots(syncRootsText),
  });

  const onSave = async () => {
    try {
      const payload = buildSavePayload();
      const res = await api.saveConfig(payload);
      if (!res.success) throw new Error(res.error);
      toast(res.message || '配置已保存');
      res.warnings?.forEach((w) => toast(w, 'error'));
      setLoaded({ ...payload });
      setConfig(payload);
      const fresh = await api.getConfig();
      if (fresh.success) setPathChecks(fresh.path_checks || {});
    } catch (e) { toast(e.message, 'error'); }
  };

  const onTest = async () => {
    const res = await api.testConnection({ host: config.db_host, user: config.db_user, password: config.db_password, database: config.db_database });
    setDbOk(res.success);
    toast(res.success ? res.message : res.error, res.success ? 'info' : 'error');
  };

  const onTestMagicFox = async () => {
    try {
      const res = await api.testMagicFoxConnection({
        magic_fox_api_base: config.magic_fox_api_base,
        magic_fox_auth_mode: config.magic_fox_auth_mode,
        magic_fox_username: config.magic_fox_username,
        magic_fox_password: config.magic_fox_password,
        magic_fox_access_token: config.magic_fox_access_token,
      });
      setMfOk(true);
      toast(res.message || 'Magic-Fox 认证成功');
      if (res.saved) load();
      else if (res.auth) {
        setConfig((c) => ({
          ...c,
          magic_fox_configured: res.auth.magic_fox_configured,
          magic_fox_password_set: res.auth.magic_fox_password_set,
          magic_fox_token_set: res.auth.magic_fox_token_set,
        }));
      }
    } catch (e) {
      setMfOk(false);
      toast(e.message, 'error');
    }
  };

  const onSaveClientToken = () => {
    setApiToken(clientApiToken.trim());
    toast(clientApiToken.trim() ? '前端 API Token 已保存到本浏览器' : '已清除前端 API Token');
  };

  const onSync = async () => {
    const res = await api.syncPlatformPaths({ drive: config.platform_root_drive });
    if (res.success) { set('img_base_path', res.img_base_path || config.img_base_path); toast('路径已同步'); load(); }
    else toast(res.error, 'error');
  };

  const onRefreshCats = async () => {
    const res = await api.getDefectCategories(true, config.defect_approach_id);
    if (res.success) setConfig((c) => ({ ...c, defect_categories: res.categories, defect_categories_source: res.source, defect_categories_meta: res.meta }));
  };

  const approachChanged = Number(config.defect_approach_id) !== Number(loaded.defect_approach_id || 18);
  const concatMode = (config.img_path_mode || 'concat') === 'concat';
  const mfPasswordMode = (config.magic_fox_auth_mode || 'password') === 'password';
  const predictRuntime = config.predict_runtime || {};
  const catMeta = config.defect_categories_meta || {};

  return (
    <div className={`config-page settings-page${embedded ? ' settings-page-embedded' : ''}`}>
      {!embedded ? (
        <header className="settings-header">
          <div>
            <div className="topbar-title">设置</div>
            <p className="settings-header-desc">数据库、路径、预测环境、Magic-Fox 认证、COCO 类别映射与系统运行参数</p>
          </div>
          <div className="settings-header-right">
            <div className="settings-header-stats">
              <StatusPill ok={dbOk} labelOk="数据库已连接" labelErr="数据库未连接" labelPending="数据库待验证" />
              <StatusPill
                ok={mfOk === true ? true : mfOk === false ? false : config.magic_fox_configured ? true : null}
                labelOk="Magic-Fox 已配置"
                labelErr="Magic-Fox 认证失败"
                labelPending="Magic-Fox 未验证"
              />
              {config.viz_available != null && (
                <StatusPill ok={config.viz_available} labelOk="样本图库可用" labelErr="样本图库不可用" labelPending="图库未检测" />
              )}
            </div>
            <div className="settings-header-actions">
              <Link className="btn btn-sm btn-ghost" to="/">返回查询</Link>
              <button type="button" className="btn btn-sm btn-primary" onClick={onSave}>保存配置</button>
            </div>
          </div>
        </header>
      ) : (
        <div className="settings-embedded-toolbar">
          <div className="settings-header-stats">
            <StatusPill ok={dbOk} labelOk="数据库已连接" labelErr="数据库未连接" labelPending="数据库待验证" />
            <StatusPill
              ok={mfOk === true ? true : mfOk === false ? false : config.magic_fox_configured ? true : null}
              labelOk="Magic-Fox 已配置"
              labelErr="Magic-Fox 认证失败"
              labelPending="Magic-Fox 未验证"
            />
            {config.viz_available != null && (
              <StatusPill ok={config.viz_available} labelOk="样本图库可用" labelErr="样本图库不可用" labelPending="图库未检测" />
            )}
          </div>
          <button type="button" className="btn btn-sm btn-primary" onClick={onSave}>保存配置</button>
        </div>
      )}

      <SettingsTabBar activeTab={activeTab} onTabChange={setActiveTab} />

      <div className="settings-workspace">
        {activeTab === 'connection' && (
          <SurfaceCard
            title="数据库连接"
            desc="查询页、部署/训练模型列表与归档功能依赖的 MySQL 数据源（vision_backend）"
            badge={<StatusPill ok={dbOk} labelOk="已连接" labelErr="未连接" labelPending="待验证" />}
            actions={<button type="button" className="btn btn-sm btn-ghost" onClick={onTest}>测试连接</button>}
          >
            <div className="config-card-body config-grid-2 settings-form">
              <div className="config-field"><label>主机 db_host</label><input value={config.db_host || ''} onChange={(e) => set('db_host', e.target.value)} placeholder="localhost" /></div>
              <div className="config-field"><label>数据库 db_database</label><input value={config.db_database || ''} onChange={(e) => set('db_database', e.target.value)} placeholder="vision_backend" /></div>
              <div className="config-field"><label>用户 db_user</label><input value={config.db_user || ''} onChange={(e) => set('db_user', e.target.value)} /></div>
              <div className="config-field"><label>密码 db_password</label><input type="password" placeholder="留空保持原密码" value={config.db_password || ''} onChange={(e) => set('db_password', e.target.value)} /></div>
            </div>
            <p className="config-hint">也可通过环境变量 DB_HOST / DB_USER / DB_PASSWORD / DB_DATABASE 覆盖（优先级高于配置文件）。</p>
          </SurfaceCard>
        )}

        {activeTab === 'project' && (
          <>
            <SurfaceCard
              title="检测项目（Approach）"
              desc="Approach ID 决定缺陷类别来源、查询范围与模型列表筛选"
              actions={<button type="button" className="btn btn-sm btn-ghost" onClick={onRefreshCats}>刷新类别</button>}
            >
              <div className="config-card-body settings-form">
                <div className="config-field">
                  <label>defect_approach_id</label>
                  <select value={config.defect_approach_id || 18} onChange={(e) => set('defect_approach_id', +e.target.value)}>
                    {(config.approaches || []).map((a) => <option key={a.id} value={a.id}>{a.id} — {a.approach_name}{a.approach_type ? ` (${a.approach_type})` : ''}</option>)}
                  </select>
                  {approachChanged && <div className="config-hint-warn">已切换检测项目，保存后生效</div>}
                </div>
                <div className="config-info-box">
                  类别来源：{config.defect_categories_source || '—'}
                  {catMeta.table && <> · 表 <code>{catMeta.table}</code></>}
                  {' · '}共 {(config.defect_categories || []).length} 个类别
                </div>
                <div className="config-chips">{(config.defect_categories || []).map((c) => <span key={c} className="config-chip">{c}</span>)}</div>
              </div>
            </SurfaceCard>
          </>
        )}

        {activeTab === 'labels' && (
          <SurfaceCard
            title="缺陷类别 id2name 映射"
            desc="COCO 导出与查询结果标注使用的 category_id → 名称映射；与数据库类别合并，此处可扩展或覆盖"
          >
            <div className="config-card-body settings-form">
              <div className="config-field">
                <label>id2name（每行一条：数字ID: 名称）</label>
                <textarea
                  rows={14}
                  className="settings-code-area"
                  value={id2nameText}
                  onChange={(e) => setId2nameText(e.target.value)}
                  placeholder={'0: 其他\n1: 划伤\n14: 脏污'}
                />
              </div>
              <p className="config-hint">保存时将解析为 JSON 对象写入 config.json。以 <code>#</code> 开头的行会被忽略。</p>
            </div>
          </SurfaceCard>
        )}

        {activeTab === 'paths' && (
          <>
            <SurfaceCard title="图片路径解析" desc="控制查询结果如何从数据库字段解析本地图片路径">
              <div className="config-card-body settings-form">
                <div className="config-field">
                  <label>img_path_mode 路径模式</label>
                  <select value={config.img_path_mode || 'concat'} onChange={(e) => set('img_path_mode', e.target.value)}>
                    <option value="concat">concat — 基础路径 + 相对字段拼接</option>
                    <option value="full_path">full_path — 使用完整路径字段</option>
                  </select>
                </div>
                {concatMode ? (
                  <>
                    <div className="config-grid-2">
                      <div className="config-field">
                        <label>img_base_path 图片基础路径</label>
                        <input value={config.img_base_path || ''} onChange={(e) => set('img_base_path', e.target.value)} />
                        {pathChecks.img_base_path_exists === false && <span className="config-hint-warn">目录不存在</span>}
                      </div>
                      <div className="config-field">
                        <label>img_path_field 相对路径字段</label>
                        <input value={config.img_path_field || 'origin_object_key'} onChange={(e) => set('img_path_field', e.target.value)} />
                      </div>
                    </div>
                    <div className="config-field settings-field-narrow">
                      <label>platform_root_drive 平台盘符</label>
                      <input maxLength={1} value={(config.platform_root_drive || 'D').toUpperCase()} onChange={(e) => set('platform_root_drive', e.target.value.toUpperCase())} />
                    </div>
                    <div className="config-info-box">
                      {config.platform_root && <div>推断平台根 platform_root：<code>{config.platform_root}</code></div>}
                      {config.local_file_base && <div>local_file 基址：<code>{config.local_file_base}</code></div>}
                      {config.platform_paths_source && <div>推断来源：{config.platform_paths_source}</div>}
                    </div>
                    {(config.platform_root_candidates || []).length > 0 && (
                      <div className="config-field">
                        <label>候选平台根（只读）</label>
                        <div className="settings-readonly-list">
                          {config.platform_root_candidates.map((p) => <code key={p}>{p}</code>)}
                        </div>
                      </div>
                    )}
                    <div className="config-actions">
                      <button type="button" className="btn btn-sm btn-ghost" onClick={onSync}>从数据库同步 img_base_path</button>
                    </div>
                  </>
                ) : (
                  <div className="config-field">
                    <label>img_full_path_field 完整路径字段</label>
                    <input value={config.img_full_path_field || 'local_pic_url'} onChange={(e) => set('img_full_path_field', e.target.value)} />
                  </div>
                )}
              </div>
            </SurfaceCard>
            <SurfaceCard title="归档目录" desc="查询页归档导出文件的本地根目录">
              <div className="config-card-body settings-form">
                <div className="config-field">
                  <label>archive_base_path</label>
                  <input value={config.archive_base_path || ''} onChange={(e) => set('archive_base_path', e.target.value)} placeholder="留空则使用默认 exports 目录" />
                  {pathChecks.archive_base_path_exists === false && config.archive_base_path && <span className="config-hint-warn">目录不存在</span>}
                </div>
              </div>
            </SurfaceCard>
          </>
        )}

        {activeTab === 'viz' && (
          <SurfaceCard
            title="样本图库（COCOVisualizer）"
            desc="查询完成后打开 COCO 样本图库预览；需配置 COCOVisualizer 仓库路径"
            badge={config.viz_available
              ? <span className="settings-pill settings-pill-ok">图库可用</span>
              : <span className="settings-pill settings-pill-warn">未检测到图库</span>}
          >
            <div className="config-card-body settings-form">
              <div className="config-field config-span-2">
                <label>coco_visualizer_root</label>
                <input
                  value={config.coco_visualizer_root || ''}
                  onChange={(e) => set('coco_visualizer_root', e.target.value)}
                  placeholder="COCOVisualizer 仓库根目录，默认同 monorepo ../COCOVisualizer"
                />
              </div>
              <div className="config-field config-span-2">
                <label>viz_open_mode 查询后打开图库</label>
                <select value={config.viz_open_mode || 'prompt'} onChange={(e) => set('viz_open_mode', e.target.value)}>
                  <option value="prompt">prompt — 弹窗询问是否打开</option>
                  <option value="auto">auto — ≤50 条结果自动跳转</option>
                  <option value="off">off — 不自动提示</option>
                </select>
              </div>
                <Link className="btn btn-sm btn-ghost" to="/viewer">打开样本图库</Link>
            </div>
          </SurfaceCard>
        )}

        {activeTab === 'predict' && (
          <SurfaceCard
            title="预测环境（DetUnify）"
            desc="本地注册/部署模型预测时使用的 Python 子进程环境"
            badge={pathChecks.use_subprocess
              ? <span className="settings-pill settings-pill-ok">子进程模式就绪</span>
              : <span className="settings-pill settings-pill-warn">未配置完整</span>}
          >
            <div className="config-card-body config-grid-2 settings-form">
              <div className="config-field config-span-2">
                <label>detunify_studio_root</label>
                <input placeholder="如 D:/tools/DetUnify-Studio" value={config.detunify_studio_root || ''} onChange={(e) => set('detunify_studio_root', e.target.value)} />
                {pathChecks.detunify_studio_root_exists === false && config.detunify_studio_root && <span className="config-hint-warn">目录不存在</span>}
              </div>
              <div className="config-field config-span-2">
                <label>predict_python_executable</label>
                <input placeholder="如 C:/conda/envs/hq_det/python.exe" value={config.predict_python_executable || ''} onChange={(e) => set('predict_python_executable', e.target.value)} />
                {pathChecks.predict_python_exists === false && config.predict_python_executable && <span className="config-hint-warn">解释器不存在</span>}
              </div>
              <div className="config-field config-span-2">
                <label>predict_script（可选）</label>
                <input placeholder="留空 → DetUnify/scripts/predict_job_worker.py" value={config.predict_script || ''} onChange={(e) => set('predict_script', e.target.value)} />
                {pathChecks.predict_script_exists === false && (config.predict_script || config.detunify_studio_root) && <span className="config-hint-warn">脚本不存在</span>}
              </div>
              <div className="config-field config-span-2">
                <Link className="btn btn-sm btn-ghost" to="/online-predict">打开在线预测</Link>
                <span className="config-hint">上传模型与图片，即时预测并查看结果（DetUnify Web UI）</span>
              </div>
              {Object.keys(predictRuntime).length > 0 && (
                <div className="config-field config-span-2">
                  <label>运行时解析（只读）</label>
                  <div className="settings-readonly-block">
                    {Object.entries(predictRuntime).map(([k, v]) => (
                      <ReadonlyRow key={k} label={k} value={String(v)} />
                    ))}
                  </div>
                </div>
              )}
              <p className="config-hint config-span-2">
                训练平台模型走 Magic-Fox 线上 API，不依赖此项。未配置完整时回退进程内 import（仅适合开发 / 单测）。
              </p>
            </div>
          </SurfaceCard>
        )}

        {activeTab === 'platform' && (
          <>
            <SurfaceCard
              title="Magic-Fox 认证"
              desc="训练平台同步、线上 model_validation 预测与 Playwright 抓取所需的凭据"
              badge={
                <StatusPill
                  ok={mfOk === true ? true : mfOk === false ? false : config.magic_fox_configured ? true : null}
                  labelOk="已配置"
                  labelErr="认证失败"
                  labelPending="未验证"
                />
              }
              actions={
                <>
                  <button type="button" className="btn btn-sm btn-ghost" onClick={onTestMagicFox}>测试认证</button>
                  <Link className="btn btn-sm btn-ghost" to="/training">训练平台</Link>
                </>
              }
            >
              <div className="config-card-body settings-form">
                <p className="config-hint config-span-2">
                  保存后写入 <code>config.json</code>（敏感字段 Fernet 加密，密钥在 <code>.config.key</code>，均勿提交 git）。测试成功后会自动保存凭据。
                  {config.magic_fox_credential_source === 'env' && (
                    <span className="config-hint-warn"> 当前凭据来自环境变量（MAGIC_FOX_*）。</span>
                  )}
                  {config.magic_fox_username && <> 当前用户：<code>{config.magic_fox_username}</code></>}
                </p>
                <div className="config-field config-span-2">
                  <label>magic_fox_api_base</label>
                  <input value={config.magic_fox_api_base || 'https://www.ai.magic-fox.com/api/v1'} onChange={(e) => set('magic_fox_api_base', e.target.value)} />
                </div>
                <div className="config-field config-span-2">
                  <label>magic_fox_auth_mode</label>
                  <div className="settings-auth-tabs">
                    <button type="button" className={`settings-auth-tab${mfPasswordMode ? ' is-active' : ''}`} onClick={() => set('magic_fox_auth_mode', 'password')}>账号密码</button>
                    <button type="button" className={`settings-auth-tab${!mfPasswordMode ? ' is-active' : ''}`} onClick={() => set('magic_fox_auth_mode', 'token')}>Access Token</button>
                  </div>
                </div>
                {mfPasswordMode ? (
                  <div className="config-grid-2 config-span-2">
                    <div className="config-field"><label>magic_fox_username</label><input value={config.magic_fox_username || ''} onChange={(e) => set('magic_fox_username', e.target.value)} autoComplete="username" /></div>
                    <div className="config-field"><label>magic_fox_password</label><input type="password" placeholder={config.magic_fox_password_set ? '留空保持已保存' : '请输入'} value={config.magic_fox_password || ''} onChange={(e) => set('magic_fox_password', e.target.value)} autoComplete="current-password" /></div>
                  </div>
                ) : (
                  <div className="config-field config-span-2">
                    <label>magic_fox_access_token</label>
                    <input type="password" placeholder={config.magic_fox_token_set ? '留空保持已保存' : '粘贴 Token'} value={config.magic_fox_access_token || ''} onChange={(e) => set('magic_fox_access_token', e.target.value)} />
                  </div>
                )}
              </div>
            </SurfaceCard>
            <SurfaceCard title="数据集同步路径" desc="训练平台数据集同步到本地的目录配置">
              <div className="config-card-body settings-form">
                <div className="config-field config-span-2">
                  <label>dataset_sync_root（相对项目根或绝对路径）</label>
                  <input value={config.dataset_sync_root || 'datasets'} onChange={(e) => set('dataset_sync_root', e.target.value)} />
                  {pathChecks.dataset_sync_root_exists === false && <span className="config-hint-warn">目录不存在（首次同步会自动创建）</span>}
                </div>
                <div className="config-field config-span-2">
                  <label>dataset_sync_roots 额外根目录（每行一个，用于解析同步数据集图片路径）</label>
                  <textarea
                    rows={4}
                    className="settings-code-area"
                    value={syncRootsText}
                    onChange={(e) => setSyncRootsText(e.target.value)}
                    placeholder="/path/to/datasets&#10;/another/sync/root"
                  />
                </div>
              </div>
            </SurfaceCard>
            <SurfaceCard
              title="平台预测上传"
              desc="Magic-Fox model_validation 预测时的批大小与上传超时；网络慢时可减小单次上传张数、增大超时"
            >
              <div className="config-card-body config-grid-2 settings-form">
                <div className="config-field">
                  <label>platform_predict_batch_size 每批预测张数</label>
                  <input
                    type="number"
                    min={1}
                    max={50}
                    value={config.platform_predict_batch_size ?? 10}
                    onChange={(e) => set('platform_predict_batch_size', Number(e.target.value) || 10)}
                  />
                </div>
                <div className="config-field">
                  <label>platform_upload_chunk 单次 multipart 上传张数</label>
                  <input
                    type="number"
                    min={1}
                    max={20}
                    value={config.platform_upload_chunk ?? 3}
                    onChange={(e) => set('platform_upload_chunk', Number(e.target.value) || 3)}
                  />
                </div>
                <div className="config-field">
                  <label>platform_upload_connect_timeout 连接超时（秒）</label>
                  <input
                    type="number"
                    min={5}
                    max={300}
                    value={config.platform_upload_connect_timeout ?? 30}
                    onChange={(e) => set('platform_upload_connect_timeout', Number(e.target.value) || 30)}
                  />
                </div>
                <div className="config-field">
                  <label>platform_upload_read_timeout 读取超时（秒）</label>
                  <input
                    type="number"
                    min={30}
                    max={7200}
                    value={config.platform_upload_read_timeout ?? 1800}
                    onChange={(e) => set('platform_upload_read_timeout', Number(e.target.value) || 1800)}
                  />
                </div>
                <div className="config-field config-span-2">
                  <label>platform_upload_write_timeout 写入超时（秒）</label>
                  <input
                    type="number"
                    min={30}
                    max={7200}
                    value={config.platform_upload_write_timeout ?? 1800}
                    onChange={(e) => set('platform_upload_write_timeout', Number(e.target.value) || 1800)}
                  />
                </div>
                <p className="config-hint config-span-2">
                  批量上传失败时会自动降级为逐张上传。出现 write timeout 时建议先将「单次上传张数」改为 1–3，并将写入超时提高到 1800 以上。
                </p>
              </div>
            </SurfaceCard>
          </>
        )}

        {activeTab === 'security' && (
          <SurfaceCard title="写库与安全" desc="Forge 独立写库、设备并发与 API 鉴权">
            <div className="config-card-body config-grid-2 settings-form">
              <div className="config-field">
                <label>forge_database 写库名</label>
                <input value={config.forge_database || 'detforge'} onChange={(e) => set('forge_database', e.target.value)} />
              </div>
              <div className="config-field">
                <label>device_max_concurrency 单设备并发上限</label>
                <input type="number" min={1} value={config.device_max_concurrency ?? 1} onChange={(e) => set('device_max_concurrency', Number(e.target.value) || 1)} />
              </div>
              <div className="config-field config-span-2">
                <label>api_token 服务端 Token（非空则所有 /api/* 需鉴权）</label>
                <input type="password" placeholder={config.api_token_set ? '留空保持已保存' : '留空 = 关闭鉴权'} value={config.api_token || ''} onChange={(e) => set('api_token', e.target.value)} />
              </div>
              <div className="config-field config-span-2">
                <label>浏览器 API Token（localStorage）</label>
                <div className="config-inline-row">
                  <input type="password" placeholder="与上方服务端 Token 一致" value={clientApiToken} onChange={(e) => setClientApiToken(e.target.value)} />
                  <button type="button" className="btn btn-sm btn-ghost" onClick={onSaveClientToken}>保存到浏览器</button>
                </div>
              </div>
              <p className="config-hint config-span-2">
                敏感字段（数据库口令、Magic-Fox 密码/Token、api_token）保存时加密写入 <code>config.json</code>；
                解密密钥在服务器本地 <code>.config.key</code>（首次保存时自动生成）。密码 / Token 留空表示不修改已保存的值。
              </p>
            </div>
          </SurfaceCard>
        )}

        {activeTab === 'query' && (
          <SurfaceCard title="自由查询" desc="查询页首次加载时的 default_sql 模板；支持 ${START_TIME} / ${END_TIME} 占位符">
            <div className="config-card-body settings-form">
              <div className="config-field">
                <label>default_sql</label>
                <textarea rows={10} className="settings-code-area" value={config.default_sql || ''} onChange={(e) => set('default_sql', e.target.value)} />
              </div>
            </div>
          </SurfaceCard>
        )}

        {activeTab === 'system' && (
          <SurfaceCard title="系统状态" desc="当前运行环境与只读诊断信息（保存配置后部分项会刷新）">
            <div className="config-card-body settings-form">
              <div className="settings-readonly-block">
                <ReadonlyRow label="数据库连接" value={config.db_connected ? '已连接' : '未连接'} />
                <ReadonlyRow label="写库 forge_database" value={config.forge_database || 'detforge'} />
                <ReadonlyRow label="样本图库 viz_available" value={config.viz_available ? '是' : '否'} />
                <ReadonlyRow label="Magic-Fox 已配置" value={config.magic_fox_configured ? '是' : '否'} />
                <ReadonlyRow label="Magic-Fox 凭据来源" value={config.magic_fox_credential_source || '—'} />
                <ReadonlyRow label="API Token 已设置" value={config.api_token_set ? '是' : '否'} />
                <ReadonlyRow label="预测子进程模式" value={pathChecks.use_subprocess ? '就绪' : '未就绪'} />
                <ReadonlyRow label="img_base_path 存在" value={pathChecks.img_base_path_exists ? '是' : '否'} />
                <ReadonlyRow label="dataset_sync_root 存在" value={pathChecks.dataset_sync_root_exists ? '是' : '否'} />
                <ReadonlyRow label="platform_root" value={config.platform_root || '—'} />
                <ReadonlyRow label="local_file_base" value={config.local_file_base || '—'} />
              </div>
              <div className="config-actions">
                <button type="button" className="btn btn-sm btn-ghost" onClick={load}>刷新状态</button>
                <Link className="btn btn-sm btn-ghost" to="/config?section=docs">使用手册</Link>
              </div>
            </div>
          </SurfaceCard>
        )}
      </div>
    </div>
  );
}
