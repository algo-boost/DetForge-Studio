"""SKILL.md 解析（共享库，兼容 COCOVisualizer skill_service 规则）。"""
from __future__ import annotations

import re
from pathlib import Path


def parse_frontmatter(text: str) -> dict:
    text = str(text or '')
    lines = text.splitlines()
    if not lines or lines[0].strip() != '---':
        return {'name': '', 'description': '', 'body': text, 'has_frontmatter': False}
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == '---':
            end = i
            break
    if end is None:
        return {'name': '', 'description': '', 'body': text, 'has_frontmatter': False}
    raw_fm = '\n'.join(lines[1:end])
    body = '\n'.join(lines[end + 1:])
    name, description = '', ''
    data = None
    try:
        import yaml
        data = yaml.safe_load(raw_fm)
    except Exception:
        data = None
    if isinstance(data, dict):
        name = str(data.get('name') or '').strip()
        d = data.get('description')
        description = str(d).strip() if d is not None else ''
    if not name:
        for ln in lines[1:end]:
            m = re.match(r'^name:\s*["\']?([^"\'\n#]+?)["\']?\s*$', ln.strip())
            if m:
                name = m.group(1).strip()
                break
    return {
        'name': name.strip()[:80],
        'description': description.strip()[:2048],
        'body': body,
        'has_frontmatter': True,
    }


def validate_parsed(parsed: dict, full_text: str, path: str = '') -> dict:
    body = (parsed.get('body') or '') if parsed.get('has_frontmatter') else full_text
    warnings: list[str] = []
    if not parsed.get('has_frontmatter'):
        warnings.append('缺少 YAML frontmatter')
    else:
        nm = (parsed.get('name') or '').strip()
        if not nm:
            warnings.append('frontmatter 缺少 name')
        elif not re.match(r'^[a-z0-9][a-z0-9-]{0,62}$', nm):
            warnings.append('name 建议使用小写字母、数字、连字符')
    return {'valid': len(warnings) == 0, 'warnings': warnings}


def _parse_section_schema(body: str) -> dict:
    """从 ## 输入 / ## 输出 章节提取简易 schema。"""
    inputs: list[str] = []
    outputs: list[str] = []
    artifacts: list[str] = []
    params_schema: dict = {'type': 'object', 'properties': {}}

    for section, target in (
        (r'##\s*(输入|Inputs?)\s*\n(.*?)(?=\n##|\Z)', 'inputs'),
        (r'##\s*(输出|Outputs?)\s*\n(.*?)(?=\n##|\Z)', 'outputs'),
    ):
        m = re.search(section, body, re.DOTALL | re.IGNORECASE)
        if not m:
            continue
        block = m.group(2)
        for line in block.splitlines():
            line = line.strip().lstrip('-').strip()
            if not line:
                continue
            key = re.split(r'[:：\s]', line, maxsplit=1)[0].strip()
            if key:
                if target == 'inputs':
                    inputs.append(key)
                    params_schema['properties'][key] = {'type': 'string'}
                else:
                    outputs.append(key)

    if 'coco' in body.lower() or 'csv' in body.lower():
        if 'csv' in body.lower():
            artifacts.append('csv')
        if 'coco' in body.lower():
            artifacts.append('coco')

    return {
        'inputs': inputs,
        'output_keys': outputs,
        'artifacts': artifacts,
        'params_schema': params_schema,
    }


def parse_skill_file(path: str) -> dict:
    text = Path(path).read_text(encoding='utf-8')
    parsed = parse_frontmatter(text)
    validation = validate_parsed(parsed, text, path=path)
    body = parsed.get('body') or text
    title = ''
    for ln in body.splitlines():
        if ln.strip().startswith('# '):
            title = ln.lstrip('#').strip()
            break
    schema = _parse_section_schema(body)
    return {
        **parsed,
        **schema,
        'title': title or parsed.get('name') or '',
        'valid': validation['valid'],
        'warnings': validation['warnings'],
        'path': path,
    }
