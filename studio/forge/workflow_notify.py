"""工作流通知：可扩展渠道（ui / feishu / email / webhook）。"""
from __future__ import annotations

import json
import logging
import smtplib
import urllib.request
from email.mime.text import MIMEText

from studio.forge import forge_db

logger = logging.getLogger('detforge.workflow.notify')

DEFAULT_NOTIFY_POLICY = {
    'channels': {},
    'events': {
        'workflow_started': ['ui'],
        'step_skipped': ['ui'],
        'waiting_human': ['ui', 'feishu'],
        'workflow_done': ['ui'],
        'workflow_failed': ['ui', 'feishu', 'email'],
    },
}


def _load_notify_config():
    try:
        from server.core import load_config
        cfg = load_config()
    except Exception:
        cfg = {}
    wf = cfg.get('workflow_notify') or {}
    return {
        'feishu_webhook_url': str(wf.get('feishu_webhook_url') or '').strip(),
        'email': wf.get('email') or {},
        'webhook_url': str(wf.get('webhook_url') or '').strip(),
        'base_url': str(wf.get('base_url') or 'http://127.0.0.1:5050').rstrip('/'),
    }


def merge_notify_policy(schedule_policy=None):
    policy = json.loads(json.dumps(DEFAULT_NOTIFY_POLICY))
    if schedule_policy:
        events = schedule_policy.get('events') or {}
        policy['events'].update(events)
        if schedule_policy.get('channels'):
            policy['channels'] = schedule_policy['channels']
    return policy


def _action_url(run_id, batch_id=None):
    cfg = _load_notify_config()
    base = cfg['base_url']
    if batch_id:
        return f'{base}/curation?batch_id={batch_id}'
    return f'{base}/workflows?run={run_id}'


def emit_event(event, *, run=None, schedule=None, step=None, extra=None):
    """按策略发送通知。"""
    run = run or {}
    schedule = schedule or {}
    policy = merge_notify_policy(schedule.get('notify_policy'))
    channels = policy.get('events', {}).get(event) or ['ui']
    run_id = run.get('id')
    schedule_id = schedule.get('id') or run.get('schedule_id')

    batch_id = None
    if step:
        batch_id = step.get('child_batch_id') or (step.get('output') or {}).get('batch_id')
        if not batch_id and isinstance(step.get('human_action'), dict):
            batch_id = step['human_action'].get('batch_id')

    title_map = {
        'workflow_started': f"编排已启动 · {run.get('name') or run.get('template_id')}",
        'step_skipped': f"步骤已跳过 · {run.get('name') or run.get('template_id')}",
        'waiting_human': f"待人工上传 COCO · {run.get('name') or run.get('template_id')}",
        'workflow_done': f"编排已完成 · {run.get('name') or run.get('template_id')}",
        'workflow_failed': f"编排失败 · {run.get('name') or run.get('template_id')}",
    }
    title = title_map.get(event, event)
    message = (extra or {}).get('message') or title
    if step and step.get('step_id'):
        message = f"{message}（步骤 {step['step_id']}）"

    payload = {
        'event': event,
        'run_id': run_id,
        'template_id': run.get('template_id'),
        'schedule_id': schedule_id,
        'step_id': (step or {}).get('step_id'),
        'batch_id': batch_id,
        'action_url': _action_url(run_id, batch_id),
        'extra': extra or {},
    }

    results = []
    for ch in channels:
        ok, detail = _dispatch_channel(ch, title=title, message=message, payload=payload)
        forge_db.insert_workflow_notification({
            'run_id': run_id,
            'schedule_id': schedule_id,
            'channel': ch,
            'event': event,
            'title': title,
            'message': message,
            'payload': payload,
            'status': 'sent' if ok else 'failed',
        })
        results.append({'channel': ch, 'ok': ok, 'detail': detail})
    return results


def _dispatch_channel(channel, *, title, message, payload):
    ch = str(channel or 'ui').strip().lower()
    if ch == 'ui':
        return True, 'stored'
    if ch == 'feishu':
        return _send_feishu(title, message, payload)
    if ch == 'email':
        return _send_email(title, message, payload)
    if ch in ('webhook', 'http'):
        return _send_webhook(title, message, payload)
    return False, f'unknown channel: {channel}'


def _send_feishu(title, message, payload):
    cfg = _load_notify_config()
    url = cfg.get('feishu_webhook_url')
    if not url:
        return False, 'feishu_webhook_url not configured'
    text = f"{title}\n{message}"
    if payload.get('action_url'):
        text += f"\n{payload['action_url']}"
    body = json.dumps({
        'msg_type': 'text',
        'content': {'text': text},
    }, ensure_ascii=False).encode('utf-8')
    try:
        req = urllib.request.Request(
            url, data=body, headers={'Content-Type': 'application/json'}, method='POST',
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status < 300, resp.read().decode('utf-8', errors='replace')[:500]
    except Exception as e:  # noqa: BLE001
        logger.warning('飞书通知失败: %s', e)
        return False, str(e)


def _send_email(title, message, payload):
    cfg = _load_notify_config()
    em = cfg.get('email') or {}
    host = str(em.get('smtp_host') or '').strip()
    port = int(em.get('smtp_port') or 587)
    user = str(em.get('username') or '').strip()
    password = str(em.get('password') or '').strip()
    sender = str(em.get('from') or user).strip()
    recipients = em.get('to') or []
    if isinstance(recipients, str):
        recipients = [recipients]
    recipients = [str(x).strip() for x in recipients if str(x).strip()]
    if not host or not recipients:
        return False, 'email smtp/to not configured'

    body = message
    if payload.get('action_url'):
        body += f"\n\n链接: {payload['action_url']}"
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = title
    msg['From'] = sender
    msg['To'] = ', '.join(recipients)
    try:
        with smtplib.SMTP(host, port, timeout=20) as smtp:
            if em.get('use_tls', True):
                smtp.starttls()
            if user and password:
                smtp.login(user, password)
            smtp.sendmail(sender, recipients, msg.as_string())
        return True, f'sent to {len(recipients)}'
    except Exception as e:  # noqa: BLE001
        logger.warning('邮件通知失败: %s', e)
        return False, str(e)


def _send_webhook(title, message, payload):
    cfg = _load_notify_config()
    url = cfg.get('webhook_url')
    if not url:
        return False, 'webhook_url not configured'
    body = json.dumps({
        'title': title,
        'message': message,
        'payload': payload,
    }, ensure_ascii=False).encode('utf-8')
    try:
        req = urllib.request.Request(
            url, data=body, headers={'Content-Type': 'application/json'}, method='POST',
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status < 300, resp.read().decode('utf-8', errors='replace')[:500]
    except Exception as e:  # noqa: BLE001
        logger.warning('Webhook 通知失败: %s', e)
        return False, str(e)
