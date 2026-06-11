import ToolHost from './ToolHost';

/**
 * DetUnify 临时上传对比 — embedded 挂载 /unify 或 remote 独立部署。
 */
export default function UnifyToolHost({
  returnTo = '/online-predict',
  returnLabel = '返回批量预测',
} = {}) {
  return (
    <ToolHost
      toolId="unify"
      segment=""
      embedProps={{
        returnTo,
        returnLabel,
        wrapClassName: 'predict-quick-frame tool-embed tool-embed-unify',
        iframeClassName: 'predict-quick-iframe',
        unavailableTitle: '临时上传对比',
        unavailableHintMounted: 'DetUnify 尚未挂载到 /unify，请重启 Flask 服务。',
        unavailableHintMissing: '未找到 DetUnify-Studio，请在设置中配置 detunify_studio_root。',
        configLink: '/config?section=predict',
        unavailableClassName: 'platform-surface-card predict-quick-unavailable',
      }}
    />
  );
}
