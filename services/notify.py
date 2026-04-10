"""
notify.py — 飞书应用消息发送服务。

支持通过 open_id / user_id / email 向用户发送飞书交互卡片消息。
使用主应用 lark.Client（SDK 内部自动管理并刷新 tenant_access_token）。
"""
import json
import logging
from typing import List

import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
)
from services import lark_client as _lark_client

logger = logging.getLogger(__name__)

RECEIVER_ID_TYPES = frozenset({"open_id", "user_id", "email", "chat_id"})

CARD_TEMPLATES = frozenset({
    "blue", "wathet", "turquoise", "green",
    "yellow", "orange", "red", "carmine",
    "violet", "purple", "indigo", "grey",
})


def _build_card(title: str, content: str, template: str) -> str:
    """.生成飞书交互卡片 JSON 字符串。content 支持 lark_md（飞书 Markdown）。"""
    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": title or "通知"},
            "template": template if template in CARD_TEMPLATES else "blue",
        },
        "elements": [
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": content or ""},
            }
        ],
    }
    return json.dumps(card, ensure_ascii=False)


def send_feishu_message(
    receiver_ids: List[str],
    receiver_id_type: str,
    title: str = "",
    content: str = "",
    template: str = "blue",
) -> dict:
    """
    向指定用户发送飞书应用消息（交互卡片）。

    Parameters
    ----------
    receiver_ids     : 收件人 ID 列表
    receiver_id_type : ID 类型，可选 "open_id" | "user_id" | "email" | "chat_id"
    title            : 消息标题（卡片 header）
    content          : 消息正文，支持飞书 Markdown（lark_md）语法
    template         : 卡片标题颜色，默认 "blue"，可选值见 CARD_TEMPLATES

    Returns
    -------
    {
      "ok": bool,
      "sent":   [id, ...],               # 发送成功
      "failed": [{"id": id, "error": str}, ...],  # 发送失败
    }
    """
    if receiver_id_type not in RECEIVER_ID_TYPES:
        raise ValueError(f"receiver_id_type 必须为 {RECEIVER_ID_TYPES} 之一，得到: {receiver_id_type!r}")
    if not receiver_ids:
        raise ValueError("receiver_ids 不能为空")

    card_content = _build_card(title, content, template)
    client = _lark_client.get_instance()
    sent, failed = [], []

    for rid in receiver_ids:
        request = (
            CreateMessageRequest.builder()
            .receive_id_type(receiver_id_type)
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(rid)
                .msg_type("interactive")
                .content(card_content)
                .build()
            )
            .build()
        )
        response = client.im.v1.message.create(request)
        if response.success():
            logger.info("notify: 消息已发送 %s=%s title=%s", receiver_id_type, rid, title)
            sent.append(rid)
        else:
            err = f"[{response.code}] {response.msg}"
            logger.error("notify: 发送失败 %s=%s: %s", receiver_id_type, rid, err)
            failed.append({"id": rid, "error": err})

    return {"ok": len(failed) == 0, "sent": sent, "failed": failed}

