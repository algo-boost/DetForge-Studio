import SceneHubNav from '../components/SceneHubNav';
import FlowAssistantPanel from '../components/flows/FlowAssistantPanel';

export default function FlowAssistantPage() {
  return (
    <div className="panel active flows-page flows-page--wide">
      <SceneHubNav variant="flows" />
      <header className="flows-page-header">
        <div>
          <h1 className="flows-page-title">编排助手</h1>
          <p className="flows-page-desc">
            用自然语言起草 Kestra Flow，校验 tool_id 并预览流程图。落库请编辑 Git YAML 并走 Catalog 同步。
          </p>
        </div>
      </header>
      <section className="flows-section">
        <FlowAssistantPanel />
      </section>
    </div>
  );
}
