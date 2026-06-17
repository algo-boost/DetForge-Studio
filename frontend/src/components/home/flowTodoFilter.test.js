import { describe, expect, it } from 'vitest';
import { filterNonFlowTodos, isNonFlowTodo } from './flowTodoFilter';

describe('flowTodoFilter', () => {
  it('filters flow human gates from workbench todos', () => {
    const items = [
      { id: '1', kind: 'manual_qc' },
      { id: '2', kind: 'workflow_human_gate' },
      { id: '3', kind: 'flow_human_gate' },
      { id: '4', kind: 'curation_batch' },
    ];
    expect(filterNonFlowTodos(items).map((i) => i.id)).toEqual(['1', '4']);
    expect(isNonFlowTodo(items[1])).toBe(false);
  });
});
