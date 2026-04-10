"""
worker_bot.py — Openclaw Bot 的 lark.Client 单例与 bot open_id。

用法：
    # main.py 启动时初始化一次
    from services import worker_bot
    worker_bot.init_instance(APP_ID, APP_SECRET)

    # 任意模块内获取
    worker_bot.get_client()      # lark.Client 实例
    worker_bot.get_bot_open_id() # bot 自身的 open_id
"""
import logging
from typing import Optional

import lark_oapi as lark
import requests

from config import FEISHU_HOST

logger = logging.getLogger(__name__)

_client: Optional[lark.Client] = None
_bot_open_id: str = ""


def init_instance(app_id: str, app_secret: str) -> None:
    """创建 worker bot 的 lark.Client 单例并获取 bot open_id。"""
    global _client, _bot_open_id
    _client = (
        lark.Client.builder()
        .domain(FEISHU_HOST)
        .app_id(app_id)
        .app_secret(app_secret)
        .log_level(lark.LogLevel.INFO)
        .build()
    )
    logger.info("worker_bot lark.Client 已初始化 app_id=%s", app_id)

    # 获取 bot 自身的 open_id（/bot/v3/info 无对应 SDK 封装，走 REST）
    try:
        token_resp = requests.post(
            f"{FEISHU_HOST}/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": app_id, "app_secret": app_secret},
            timeout=10,
        )
        token = token_resp.json().get("tenant_access_token")
        if not token:
            logger.error("worker_bot: 获取 tenant_access_token 失败: %s", token_resp.json())
            return

        bot_data = requests.get(
            f"{FEISHU_HOST}/open-apis/bot/v3/info",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        ).json()
        if bot_data.get("code") != 0:
            logger.error("worker_bot: 获取机器人信息失败: %s", bot_data)
            return

        _bot_open_id = bot_data["bot"]["open_id"]
        logger.info("worker_bot open_id 获取成功: %s", _bot_open_id)
    except Exception as exc:
        logger.exception("worker_bot: 获取 bot open_id 异常: %s", exc)


def get_client() -> Optional[lark.Client]:
    """返回 worker bot 的 lark.Client，未初始化时返回 None。"""
    return _client


def get_bot_open_id() -> str:
    """返回 worker bot 的 open_id，未初始化时返回空字符串。"""
    return _bot_open_id
