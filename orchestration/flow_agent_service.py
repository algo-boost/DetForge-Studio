"""Flow 编排助手：上下文、LLM 草稿、校验与流程图预览。"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from typing import Any, NamedTuple

try:
    import yaml
except ImportError:
    yaml = None

from orchestration.agent_compiler import extract_yaml_from_text
from orchestration.pipeline_validate import validate_pipeline_text
from studio.paths import APP_ROOT


_EXAMPLE_YAMLS = {
    'daily_ng_curation': os.path.join(
        APP_ROOT, 'iisp-catalog', 'pipelines', 'legacy', 'daily_ng_curation.yaml',
    ),
    'welcome_demo': os.path.join(
        APP_ROOT, 'iisp-catalog', 'pipelines', 'demo', 'welcome_flow.yaml',
    ),
}

_TEMPLATE_HINTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r'捞图|daily|ng|curation|定时|归档', re.I), 'daily_ng_curation'),
    (re.compile(r'smoke|demo|闭环|演示|样本|welcome', re.I), 'welcome_demo'),
]

_PROVIDER_LABELS = {
    'openai': 'OpenAI 兼容 API',
    'anthropic': 'Anthropic API',
    'claude_code': 'Claude Code CLI',
}


class LlmResult(NamedTuple):
    text: str | None
    error: str | None


def _agent_provider() -> str:
    raw = (os.environ.get('IISP_FLOW_AGENT_PROVIDER') or '').strip().lower()
    if not raw:
        return 'claude_code' if _claude_available() else 'openai'
    if raw in ('openai', 'anthropic', 'claude_code', 'claude-code', 'claude'):
        return 'claude_code' if raw.startswith('claude') else raw
    return 'openai'


def _npm_prefixes() -> list[str]:
    prefixes: list[str] = []
    for key in ('NPM_CONFIG_PREFIX', 'npm_config_prefix'):
        val = os.environ.get(key, '').strip()
        if val:
            prefixes.append(val)
    try:
        r = subprocess.run(
            ['npm', 'prefix', '-g'],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if r.returncode == 0 and r.stdout.strip():
            prefixes.append(r.stdout.strip())
    except (OSError, subprocess.TimeoutExpired):
        pass
    prefixes.extend(['/opt/homebrew', '/usr/local', os.path.expanduser('~/.npm-global')])
    seen: set[str] = set()
    out: list[str] = []
    for p in prefixes:
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _npm_claude_cli_paths() -> list[str]:
    paths: list[str] = []
    for prefix in _npm_prefixes():
        cli_js = os.path.join(
            prefix, 'lib', 'node_modules', '@anthropic-ai', 'claude-code', 'cli.js',
        )
        if os.path.isfile(cli_js):
            paths.append(cli_js)
    return paths


def _resolve_claude_cmd() -> list[str] | None:
    """解析 claude 可执行命令：PATH 二进制或 npm 全局 cli.js + node。"""
    explicit = os.environ.get('IISP_FLOW_AGENT_CLAUDE_BIN', '').strip()
    if explicit:
        if os.path.isfile(explicit):
            if explicit.endswith('.js') or not os.access(explicit, os.X_OK):
                node = shutil.which('node') or 'node'
                return [node, explicit]
            return [explicit]
        found = shutil.which(explicit)
        if found:
            return [found]

    found = shutil.which('claude')
    if found:
        return [found]

    for cli_js in _npm_claude_cli_paths():
        node = shutil.which('node') or 'node'
        return [node, cli_js]
    return None


def _claude_available() -> bool:
    return _resolve_claude_cmd() is not None


def _probe_claude() -> dict[str, Any]:
    base_cmd = _resolve_claude_cmd()
    if not base_cmd:
        return {'ok': False, 'error': '未找到 Claude Code CLI'}
    try:
        result = subprocess.run(
            [*base_cmd, '--version'],
            capture_output=True,
            text=True,
            timeout=15,
            stdin=subprocess.DEVNULL,
        )
        line = ((result.stdout or result.stderr) or '').strip().split('\n')[0]
        if result.returncode == 0 and line:
            return {'ok': True, 'version': line}
        err = (result.stderr or result.stdout or f'exit {result.returncode}').strip()
        return {'ok': False, 'error': err[:300]}
    except (subprocess.TimeoutExpired, OSError) as exc:
        return {'ok': False, 'error': str(exc)}


def _llm_configured() -> bool:
    provider = _agent_provider()
    if provider == 'anthropic':
        return bool(os.environ.get('IISP_FLOW_AGENT_API_KEY') or os.environ.get('ANTHROPIC_API_KEY'))
    if provider == 'claude_code':
        probe = _probe_claude()
        return probe.get('ok', False)
    return bool(os.environ.get('IISP_FLOW_AGENT_API_URL') and os.environ.get('IISP_FLOW_AGENT_API_KEY'))


def build_flow_compose_prompt(tools: list[dict]) -> str:
    tool_lines = []
    for t in tools[:50]:
        tool_lines.append(f"- {t.get('id')}: {t.get('label')} — {(t.get('description') or '')[:100]}")
    tools_block = '\n'.join(tool_lines) or '- （暂无注册工具）'
    return (
        '你是 IISP 编排助手，产出 legacy Pipeline YAML（nodes/steps 格式，不是 tasks）。\n'
        '约束：\n'
        '- 顶层：id, name, description, params_schema（可选）, nodes 或 steps\n'
        '- 每步：id, tool/kind, params；需要顺序依赖时用 requires\n'
        '- 必须写中文注释（文件头 + 每步说明）\n'
        '- tool/kind 只能来自下方清单，禁止编造\n'
        '可用工具：\n'
        f'{tools_block}\n'
        '参考：iisp-catalog/pipelines/demo/welcome_flow.yaml\n'
        '复杂生产链推荐用户使用「组合编排」页（/flows/compose）。\n'
        '当用户描述的是编排需求时，只输出一个 ```yaml 代码块（可附一句话说明）。\n'
        '当用户只是寒暄或提问（非编排需求）时，简短回应并主动引导其描述要编排的流程。'
    )


build_kestra_compose_prompt = build_flow_compose_prompt


def _read_example_yaml(key: str) -> str:
    path = _EXAMPLE_YAMLS.get(key, '')
    if path and os.path.isfile(path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    return ''


def _suggest_template_key(description: str) -> str | None:
    text = str(description or '')
    for pattern, key in _TEMPLATE_HINTS:
        if pattern.search(text):
            return key
    return None


def _build_user_prompt(user: str, history: list[dict] | None = None) -> str:
    lines: list[str] = []
    for item in history or []:
        role = item.get('role')
        content = item.get('content')
        if role in ('user', 'assistant') and content:
            lines.append(f'{role.upper()}: {content}')
    lines.append(f'USER: {user}')
    return '\n\n'.join(lines)


def _openai_chat(system: str, user: str, history: list[dict] | None = None) -> LlmResult:
    base = os.environ.get('IISP_FLOW_AGENT_API_URL', '').rstrip('/')
    key = os.environ.get('IISP_FLOW_AGENT_API_KEY', '')
    model = os.environ.get('IISP_FLOW_AGENT_MODEL', 'gpt-4o-mini')
    if not base or not key:
        return LlmResult(None, '未配置 IISP_FLOW_AGENT_API_URL / API_KEY')
    messages: list[dict[str, str]] = [{'role': 'system', 'content': system}]
    for item in history or []:
        role = item.get('role')
        content = item.get('content')
        if role in ('user', 'assistant') and content:
            messages.append({'role': role, 'content': str(content)})
    messages.append({'role': 'user', 'content': user})
    payload = json.dumps({'model': model, 'messages': messages, 'temperature': 0.2}).encode('utf-8')
    url = f'{base}/v1/chat/completions' if not base.endswith('/v1/chat/completions') else base
    req = urllib.request.Request(
        url,
        data=payload,
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {key}'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        return LlmResult(str(data['choices'][0]['message']['content']), None)
    except (urllib.error.URLError, KeyError, json.JSONDecodeError, IndexError) as exc:
        return LlmResult(None, str(exc))


def _anthropic_chat(system: str, user: str, history: list[dict] | None = None) -> LlmResult:
    key = os.environ.get('IISP_FLOW_AGENT_API_KEY') or os.environ.get('ANTHROPIC_API_KEY', '')
    model = os.environ.get('IISP_FLOW_AGENT_MODEL', 'claude-sonnet-4-20250514')
    if not key:
        return LlmResult(None, '未配置 ANTHROPIC_API_KEY')
    messages: list[dict[str, str]] = []
    for item in history or []:
        role = item.get('role')
        content = item.get('content')
        if role in ('user', 'assistant') and content:
            messages.append({'role': role, 'content': str(content)})
    messages.append({'role': 'user', 'content': user})
    payload = json.dumps({
        'model': model,
        'max_tokens': 8192,
        'system': system,
        'messages': messages,
    }).encode('utf-8')
    req = urllib.request.Request(
        'https://api.anthropic.com/v1/messages',
        data=payload,
        headers={
            'Content-Type': 'application/json',
            'x-api-key': key,
            'anthropic-version': '2023-06-01',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        blocks = data.get('content') or []
        texts = [b.get('text', '') for b in blocks if b.get('type') == 'text']
        text = '\n'.join(texts).strip() or None
        return LlmResult(text, None if text else '空响应')
    except (urllib.error.URLError, KeyError, json.JSONDecodeError, IndexError) as exc:
        return LlmResult(None, str(exc))


def _claude_code_chat(system: str, user: str, history: list[dict] | None = None) -> LlmResult:
    """调用本机 Claude Code CLI（claude -p），加载项目 CLAUDE.md / Skills / MCP。"""
    base_cmd = _resolve_claude_cmd()
    if not base_cmd:
        return LlmResult(None, '未找到 Claude Code CLI')
    cwd = os.environ.get('IISP_FLOW_AGENT_CWD') or str(APP_ROOT)
    timeout = int(os.environ.get('IISP_FLOW_AGENT_TIMEOUT', '180'))
    use_bare = os.environ.get('IISP_FLOW_AGENT_CLAUDE_BARE', '0') == '1'
    prompt = _build_user_prompt(user, history)

    # prompt 必须紧跟 -p，否则 CLI 报 "Input must be provided"
    cmd = [*base_cmd, '-p', prompt, '--output-format', 'text']
    if use_bare:
        cmd.append('--bare')
    cmd.extend(['--append-system-prompt', system])
    cmd.extend(['--permission-mode', 'dontAsk', '--allowedTools', 'Read'])

    mcp_cfg = os.environ.get('IISP_FLOW_AGENT_MCP_CONFIG', '')
    if not mcp_cfg:
        for candidate in (
            os.path.join(APP_ROOT, 'agent', 'mcp.json'),
            os.path.join(APP_ROOT, 'agent', 'mcp.json.example'),
        ):
            if os.path.isfile(candidate):
                mcp_cfg = candidate
                break
    if mcp_cfg and os.path.isfile(mcp_cfg):
        cmd.extend(['--mcp-config', mcp_cfg])

    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=os.environ.copy(),
            stdin=subprocess.DEVNULL,
        )
        if result.returncode != 0:
            err = (result.stderr or result.stdout or f'exit {result.returncode}').strip()
            return LlmResult(None, err[:500])
        out = (result.stdout or '').strip()
        return LlmResult(out or None, None if out else 'Claude Code 返回空响应')
    except subprocess.TimeoutExpired:
        return LlmResult(None, f'Claude Code 超时（>{timeout}s）')
    except OSError as exc:
        return LlmResult(None, str(exc))


def _llm_chat(system: str, user: str, history: list[dict] | None = None) -> LlmResult:
    provider = _agent_provider()
    if provider == 'anthropic':
        return _anthropic_chat(system, user, history=history)
    if provider == 'claude_code':
        return _claude_code_chat(system, user, history=history)
    return _openai_chat(system, user, history=history)


def get_compose_context(flow_id: str | None = None) -> dict[str, Any]:
    from capabilities.registry import init_registry
    from server.services.flows import get_pipeline_yaml

    reg = init_registry()
    tools = reg.list_tools()
    current_yaml = ''
    if flow_id:
        try:
            current_yaml = get_pipeline_yaml(flow_id).get('yaml') or ''
        except (FileNotFoundError, OSError):
            current_yaml = ''
    probe = _probe_claude() if _agent_provider() == 'claude_code' else None
    return {
        'llm_configured': _llm_configured(),
        'provider': _agent_provider(),
        'provider_label': _PROVIDER_LABELS.get(_agent_provider(), _agent_provider()),
        'claude_code_available': _claude_available(),
        'claude_probe': probe,
        'claude_cmd': ' '.join(_resolve_claude_cmd() or []),
        'system_prompt': build_kestra_compose_prompt(tools),
        'tools_count': len(tools),
        'examples': [
            {'id': k, 'path': v, 'label': k.replace('_', ' ')}
            for k, v in _EXAMPLE_YAMLS.items()
            if os.path.isfile(v)
        ],
        'current_yaml': current_yaml,
        'flow_id': flow_id,
    }


def validate_yaml_text(yaml_text: str) -> dict[str, Any]:
    return validate_pipeline_text(yaml_text or '')


_SAFE_ID = re.compile(r'^[a-z0-9][a-z0-9_.-]{1,63}$')


def save_flow_yaml(yaml_text: str, *, overwrite: bool = False) -> dict[str, Any]:
    """把助手生成的 legacy Pipeline YAML 保存到 Catalog。"""
    if yaml is None:
        return {'success': False, 'error': '需要 PyYAML'}
    validation = validate_yaml_text(yaml_text)
    if not validation.get('valid'):
        return {'success': False, 'error': '校验未通过，请先修正', 'validation': validation}
    if validation.get('engine') != 'legacy':
        return {'success': False, 'error': '仅支持 legacy nodes/steps 格式；生产链请用组合编排', 'validation': validation}

    flow_id = str(validation.get('id') or '').strip()
    if not _SAFE_ID.match(flow_id):
        return {'success': False, 'error': f'非法 flow id: {flow_id!r}（仅小写字母/数字/_-.）'}

    target_dir = os.path.join(APP_ROOT, 'iisp-catalog', 'pipelines', 'legacy')
    os.makedirs(target_dir, exist_ok=True)
    target = os.path.join(target_dir, f'{flow_id}.yaml')
    existed = os.path.isfile(target)
    if existed and not overwrite:
        return {
            'success': False,
            'error': f'已存在同名 Flow：{flow_id}',
            'flow_id': flow_id,
            'exists': True,
        }
    with open(target, 'w', encoding='utf-8') as f:
        f.write(yaml_text if yaml_text.endswith('\n') else yaml_text + '\n')
    return {
        'success': True,
        'flow_id': flow_id,
        'path': target,
        'overwritten': existed,
        'validation': validation,
    }


def preview_graph_from_yaml(yaml_text: str) -> dict[str, Any]:
    if yaml is None:
        return {'success': False, 'error': '需要 PyYAML'}
    validation = validate_yaml_text(yaml_text)
    try:
        defn = yaml.safe_load(yaml_text)
    except Exception as exc:
        return {'success': False, 'error': f'YAML 解析失败: {exc}', 'validation': validation}
    if not isinstance(defn, dict):
        return {'success': False, 'error': 'Flow 必须是 YAML 对象', 'validation': validation}
    from orchestration.flow_graph import build_flow_graph

    if defn.get('tasks'):
        return {'success': False, 'error': '不再支持 Kestra tasks 格式', 'validation': validation}
    graph = build_flow_graph(defn, engine='legacy', yaml_text=yaml_text)
    return {
        'success': True,
        'validation': validation,
        'graph': graph,
        'engine': engine,
        'flow_id': defn.get('id'),
    }


def _finalize_llm_reply(reply: str, provider: str) -> dict[str, Any]:
    """从模型回复提取 YAML、校验并生成预览图。"""
    yaml_text = extract_yaml_from_text(reply)
    if yaml_text:
        validation = validate_yaml_text(yaml_text)
        preview = preview_graph_from_yaml(yaml_text) if validation.get('valid') else None
        return {
            'success': True,
            'mode': 'llm',
            'provider': provider,
            'reply': reply,
            'yaml': yaml_text,
            'validation': validation,
            'graph': (preview or {}).get('graph'),
        }
    return {
        'success': True,
        'mode': 'llm',
        'provider': provider,
        'reply': reply,
        'yaml': '',
        'validation': None,
        'hint': '模型回复中未找到 YAML 代码块，请粘贴或重试。',
    }


def _manual_fallback(desc: str, provider: str, *, llm_error: str | None = None) -> dict[str, Any]:
    if llm_error and (_llm_configured() or _claude_available()):
        return {
            'success': False,
            'mode': 'error',
            'provider': provider,
            'reply': f'调用失败：{llm_error}',
            'llm_error': llm_error,
            'yaml': '',
        }

    template_key = _suggest_template_key(desc)
    suggested = _read_example_yaml(template_key) if template_key else ''
    template_label = template_key or ''
    provider_hint = {
        'claude_code': '请确认 Claude Code 已登录（终端运行 claude 可交互）',
        'anthropic': '设置 ANTHROPIC_API_KEY',
        'openai': '设置 IISP_FLOW_AGENT_API_URL 与 IISP_FLOW_AGENT_API_KEY',
    }.get(provider, '')
    reply_lines = [
        f'LLM 未就绪（{provider}）。{provider_hint}',
        '',
        '你仍可以：',
        '· 在「YAML」页粘贴/编辑后校验与预览',
        '· 复制 Prompt 到 Cursor / Claude Code 终端生成',
    ]
    if template_label:
        reply_lines.append(f'· 已匹配范例 {template_label}，可作为起点修改')
    else:
        reply_lines.append('· 描述里可含「捞图」「闭环演示」等关键词以匹配范例')

    from capabilities.registry import init_registry

    return {
        'success': True,
        'mode': 'manual',
        'provider': provider,
        'reply': '\n'.join(reply_lines),
        'yaml': suggested,
        'validation': validate_yaml_text(suggested) if suggested else None,
        'system_prompt': build_kestra_compose_prompt(init_registry().list_tools()),
        'template_id': template_key,
    }


def stream_compose(
    description: str,
    *,
    flow_id: str | None = None,
    history: list[dict] | None = None,
):
    """SSE 流式编排：yield 形如 {'type': 'delta'|'final'|'error', ...} 的事件。"""
    from capabilities.registry import init_registry

    desc = str(description or '').strip()
    if not desc:
        yield {'type': 'error', 'error': '缺少描述'}
        return

    provider = _agent_provider()
    reg = init_registry()
    system = build_kestra_compose_prompt(reg.list_tools())

    yield {'type': 'start', 'provider': provider, 'provider_label': _PROVIDER_LABELS.get(provider, provider)}

    collected: list[str] = []
    error: str | None = None

    if provider == 'claude_code':
        for ev in _stream_claude_code(system, desc, history=history):
            if ev.get('type') == 'delta':
                collected.append(ev.get('text', ''))
                yield ev
            elif ev.get('type') == 'error':
                error = ev.get('error')
            elif ev.get('type') == 'text':
                collected = [ev.get('text', '')]
    else:
        llm = _llm_chat(system, desc, history=history)
        if llm.text:
            collected = [llm.text]
            yield {'type': 'delta', 'text': llm.text}
        else:
            error = llm.error

    full = ''.join(collected).strip()
    if full:
        result = _finalize_llm_reply(full, provider)
    else:
        result = _manual_fallback(desc, provider, llm_error=error)
    yield {'type': 'final', 'data': result}


def _stream_claude_code(system: str, user: str, history: list[dict] | None = None):
    base_cmd = _resolve_claude_cmd()
    if not base_cmd:
        yield {'type': 'error', 'error': '未找到 Claude Code CLI'}
        return
    cwd = os.environ.get('IISP_FLOW_AGENT_CWD') or str(APP_ROOT)
    use_bare = os.environ.get('IISP_FLOW_AGENT_CLAUDE_BARE', '0') == '1'
    prompt = _build_user_prompt(user, history)

    cmd = [*base_cmd, '-p', prompt, '--output-format', 'stream-json',
           '--include-partial-messages', '--verbose']
    if use_bare:
        cmd.append('--bare')
    cmd.extend(['--append-system-prompt', system])
    cmd.extend(['--permission-mode', 'dontAsk', '--allowedTools', 'Read'])

    mcp_cfg = os.environ.get('IISP_FLOW_AGENT_MCP_CONFIG', '')
    if not mcp_cfg:
        for candidate in (
            os.path.join(APP_ROOT, 'agent', 'mcp.json'),
            os.path.join(APP_ROOT, 'agent', 'mcp.json.example'),
        ):
            if os.path.isfile(candidate):
                mcp_cfg = candidate
                break
    if mcp_cfg and os.path.isfile(mcp_cfg):
        cmd.extend(['--mcp-config', mcp_cfg])

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            env=os.environ.copy(),
            bufsize=1,
        )
    except OSError as exc:
        yield {'type': 'error', 'error': str(exc)}
        return

    result_text: str | None = None
    try:
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            etype = ev.get('type')
            if etype == 'stream_event':
                delta = (ev.get('event') or {}).get('delta') or {}
                if delta.get('type') == 'text_delta' and delta.get('text'):
                    yield {'type': 'delta', 'text': delta['text']}
            elif etype == 'result':
                res = ev.get('result')
                if isinstance(res, str) and res.strip():
                    result_text = res
        proc.wait(timeout=5)
    except Exception as exc:  # noqa: BLE001
        yield {'type': 'error', 'error': str(exc)}
        return

    if proc.returncode not in (0, None):
        err = (proc.stderr.read() if proc.stderr else '') or f'exit {proc.returncode}'
        yield {'type': 'error', 'error': err.strip()[:500]}
        return
    if result_text:
        yield {'type': 'text', 'text': result_text}


def compose_from_description(
    description: str,
    *,
    flow_id: str | None = None,
    history: list[dict] | None = None,
) -> dict[str, Any]:
    from capabilities.registry import init_registry

    desc = str(description or '').strip()
    if not desc:
        return {'success': False, 'error': '缺少描述'}

    reg = init_registry()
    tools = reg.list_tools()
    system = build_kestra_compose_prompt(tools)

    llm = _llm_chat(system, desc, history=history)
    provider = _agent_provider()

    if llm.text:
        return _finalize_llm_reply(llm.text, provider)

    fallback = _manual_fallback(desc, provider, llm_error=llm.error)
    return fallback
