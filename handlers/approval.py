"""
approval.py — 飞书审批状态变更事件处理器。
"""
import json
import logging
import threading
from typing import Dict

import lark_oapi as lark

from config import APPROVAL_CODES, ALERT_WEBHOOK
from handlers.process import run_process

logger = logging.getLogger(__name__)


def _send_alert(title: str, content: str) -> None:
    """向 webhook 发送红色告警卡片。"""
    import requests as _req
    card = {
        "msg_type": "interactive",
        "card": {
            "schema": "2.0",
            "body": {
                "elements": [
                    {
                        "tag": "markdown",
                        "content": f"**{title}**\n\n{content}",
                        "text_align": "left",
                    }
                ]
            },
            "header": {
                "title": {"tag": "plain_text", "content": f"🚨 {title}"},
                "template": "red",
            },
        },
    }
    try:
        _req.post(ALERT_WEBHOOK, json=card, timeout=10)
    except Exception as exc:
        logger.warning("发送告警 webhook 失败: %s", exc)


def _parse_instance_code_from_v1(event: Dict) -> str:
    """从 v1 approval 事件体提取实例 ID。"""
    candidate_keys = [
        "instance_code",
        "instanceCode",
        "instance_id",
        "instanceId",
        "process_instance_id",
        "processInstanceId",
    ]
    for key in candidate_keys:
        value = event.get(key)
        if value:
            return str(value)
    return ""



def handle_approval_v1(data: lark.CustomizedEvent) -> None:
    """处理 v1 approval 自定义事件。"""
    event = data.event or {}
    event_type = getattr(data, "type", "unknown")
    logger.info("[p1.%s] 收到原始事件: %s", event_type, event)

    approval_code = event.get("approval_code") or event.get("approvalCode")
    if approval_code not in APPROVAL_CODES:
        logger.debug("[p1.%s] 忽略审批事件：approval_code=%s", event_type, approval_code)
        return

    instance_code = _parse_instance_code_from_v1(event)
    if not instance_code:
        logger.warning("[p1.%s] 无法提取 instance_code，event=%s", event_type, event)
        return

    ev_status = event.get("status") or ""

    # 审批通过：进行拉群 / 执行脚本主流程
    if ev_status == "APPROVED":
        def _run(ic=instance_code, ac=approval_code):
            try:
                run_process(ic, ac, f"p1.{event_type}")
            except Exception as exc:
                logger.exception("处理审批事件失败 instance_code=%s: %s", ic, exc)
                _send_alert(
                    "审批自动化处理失败",
                    f"instance_code: `{ic}`\n"
                    f"approval_code: `{ac}`\n"
                    f"错误信息: {exc}\n\n"
                    "请前往 (/admin) 手动重试。",
                )
        threading.Thread(target=_run, daemon=True, name=f"approval-{instance_code[:8]}").start()
        return

    # 审批待审批：尝试自动执行预检查节点
    if ev_status == "PENDING":
        def _run_precheck(ic=instance_code, ac=approval_code):
            from handlers.precheck import run_precheck
            try:
                run_precheck(ic, approval_code=ac)
            except Exception as exc:
                logger.exception("预检查处理失败 instance_code=%s: %s", ic, exc)
                _send_alert(
                    "审批预检查失败",
                    f"instance_code: `{ic}`\n"
                    f"approval_code: `{ac}`\n"
                    f"错误信息: {exc}\n\n"
                    "请前往 (/admin) 预检查记录表手动重试。",
                )
        threading.Thread(target=_run_precheck, daemon=True,
                         name=f"precheck-{instance_code[:8]}").start()
        return

    logger.info("[p1.%s] 审批状态为 %s，无需处理", event_type, ev_status)
