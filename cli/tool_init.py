"""从 SKILL.md 生成工具包骨架。"""
from __future__ import annotations

import json
import os
from pathlib import Path

from capabilities.skill_parser import parse_skill_file


CAPABILITY_TEMPLATE = '''"""Auto-generated from SKILL.md — 请实现 execute 逻辑。"""
from __future__ import annotations

from capabilities.base import CapabilityResult, CapabilitySpec, RunContext


class {class_name}:
    id = "{tool_id}"

    def describe(self) -> CapabilitySpec:
        return CapabilitySpec(
            id=self.id,
            label="{label}",
            description="{description}",
            params_schema={params_schema},
            output_keys={output_keys},
        )

    def preview(self, ctx: RunContext) -> CapabilityResult | None:
        return None

    def execute(self, ctx: RunContext) -> CapabilityResult:
        # TODO: 实现业务逻辑
        return CapabilityResult(status="done", outputs={{"ok": True}})
'''

CLI_TEMPLATE = '''"""CLI 入口：stdin JSON → stdout JSON。"""
from __future__ import annotations

import json
import sys

from {module}.capability import {class_name}


def main():
    raw = sys.stdin.read() or "{{}}"
    payload = json.loads(raw)
    cap = {class_name}()
    from capabilities.base import RunContext
    ctx = RunContext(
        run_id=payload.get("run_id"),
        step_id=payload.get("step_id"),
        params=payload.get("params") or {{}},
        inputs=payload.get("inputs") or {{}},
    )
    result = cap.execute(ctx)
    print(json.dumps({{
        "status": result.status,
        "outputs": result.outputs,
        "reason": result.reason,
    }}, ensure_ascii=False))


if __name__ == "__main__":
    main()
'''


def _class_name(tool_id: str) -> str:
    parts = tool_id.replace('-', '_').split('_')
    return ''.join(p.capitalize() for p in parts if p) + 'Capability'


def init_tool_from_skill(skill_path: str, out_dir: str) -> dict:
    parsed = parse_skill_file(skill_path)
    if not parsed.get('valid'):
        return {'success': False, 'error': 'SKILL 校验未通过', 'warnings': parsed.get('warnings')}

    tool_id = parsed['name']
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    module = out.name.replace('-', '_')
    class_name = _class_name(tool_id)

    cap_path = out / 'capability.py'
    cap_path.write_text(
        CAPABILITY_TEMPLATE.format(
            class_name=class_name,
            tool_id=tool_id,
            label=parsed.get('title') or tool_id,
            description=(parsed.get('description') or '')[:500],
            params_schema=json.dumps(parsed.get('params_schema') or {}, ensure_ascii=False),
            output_keys=json.dumps(parsed.get('output_keys') or [], ensure_ascii=False),
        ),
        encoding='utf-8',
    )

    cli_path = out / 'cli.py'
    cli_path.write_text(
        CLI_TEMPLATE.format(module=module, class_name=class_name),
        encoding='utf-8',
    )

    manifest = {
        'id': tool_id,
        'version': '0.1.0',
        'label': parsed.get('title') or tool_id,
        'description': parsed.get('description') or '',
        'kind': 'hybrid',
        'entry': {
            'capability': f'{module}.capability:{class_name}',
            'cli': f'python -m {module}.cli',
            'blueprint': None,
        },
        'params_schema': parsed.get('params_schema') or {},
        'inputs': parsed.get('inputs') or [],
        'outputs': parsed.get('output_keys') or [],
        'artifacts': parsed.get('artifacts') or [],
        'skill_source': str(Path(skill_path).as_posix()),
    }
    manifest_path = out / 'tool.manifest.json'
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    (out / '__init__.py').write_text('', encoding='utf-8')
    tests_dir = out / 'tests'
    tests_dir.mkdir(exist_ok=True)
    (tests_dir / 'test_capability.py').write_text(
        f'def test_describe():\n    from {module}.capability import {class_name}\n'
        f'    spec = {class_name}().describe()\n    assert spec.id == "{tool_id}"\n',
        encoding='utf-8',
    )

    skill_dest = out / 'SKILL.md'
    if not skill_dest.exists():
        skill_dest.write_text(Path(skill_path).read_text(encoding='utf-8'), encoding='utf-8')

    return {
        'success': True,
        'tool_id': tool_id,
        'out_dir': str(out),
        'files': [
            str(cap_path), str(cli_path), str(manifest_path), str(skill_dest),
        ],
    }
