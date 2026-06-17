import FlowsSceneShell from '../components/flows/FlowsSceneShell';
import FlowAssistantPanel from '../components/flows/FlowAssistantPanel';

export default function FlowAssistantPage() {
  return (
    <FlowsSceneShell layout="wide">
      <header className="flows-page-header">
        <div>
          <h1 className="flows-page-title">编排助手</h1>
          <p className="flows-page-desc">
            用自然语言起草 legacy Pipeline YAML，校验 tool_id 并预览流程图；生产链请用「组合编排」。
          </p>
        </div>
      </header>
      <section className="flows-section">
        <FlowAssistantPanel />
      </section>
    </FlowsSceneShell>
  );
}
