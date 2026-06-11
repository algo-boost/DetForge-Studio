import WorkflowParamsForm from '../forge/WorkflowParamsForm';

/** 从 Catalog params_schema 生成运行表单（复用 WorkflowParamsForm） */
export default function FlowParamsForm(props) {
  return <WorkflowParamsForm {...props} />;
}
