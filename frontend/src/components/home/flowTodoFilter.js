/** 工作台「待办」不含流水线人工卡点（由「流水线运行」区块展示） */
export function isNonFlowTodo(item) {
  return item?.kind !== 'flow_human_gate' && item?.kind !== 'workflow_human_gate';
}

export function filterNonFlowTodos(items = []) {
  return items.filter(isNonFlowTodo);
}
