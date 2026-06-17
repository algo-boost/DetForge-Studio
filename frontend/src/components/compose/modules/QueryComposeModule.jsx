import QueryPage from '../../../pages/QueryPage';

/** 嵌入完整查询页 UI（策略 / SQL / 规则 / 环境参数 / 预览） */
export default function QueryComposeModule({
  value,
  onChange,
  lockDataSource = null,
  bindHints = [],
}) {
  const upstreamPredictJob = bindHints.some((h) => h.param === 'predict_job_id' && h.ok);

  return (
    <div className="compose-module-embed compose-module-query">
      <QueryPage
        embedded
        composeParams={value}
        onComposeParamsChange={onChange}
        lockDataSource={lockDataSource}
        upstreamPredictJobBound={upstreamPredictJob}
      />
    </div>
  );
}
