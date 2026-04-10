"""
lark_client.py — 主应用 lark.Client 全局单例。

用法：
    # main.py 启动时初始化一次
    from services import lark_client
    lark_client.init_instance(APP_ID, APP_SECRET)

    # 任意模块内获取
    from services.lark_client import get_instance
    client = get_instance()
"""
import logging
from typing import Optional

import lark_oapi as lark

from config import FEISHU_HOST

logger = logging.getLogger(__name__)

_instance: Optional[lark.Client] = None


def init_instance(app_id: str, app_secret: str) -> lark.Client:
    """
    创建并缓存 lark.Client 单例。
    进程生命周期内只需调用一次（通常在 main.py 启动时）。
    lark.Client 内部自动管理 tenant_access_token 的获取与刷新，无需手动维护。
    """
    global _instance
    _instance = (
        lark.Client.builder()
        .domain(FEISHU_HOST)
        .app_id(app_id)
        .app_secret(app_secret)
        .log_level(lark.LogLevel.INFO)
        .build()
    )
    logger.info("lark.Client 单例已初始化 app_id=%s", app_id)
    return _instance


def get_instance() -> lark.Client:
    """
    获取 lark.Client 单例。
    若未初始化则抛出 RuntimeError（确保 main.py 在启动时调用过 init_instance）。
    """
    if _instance is None:
        raise RuntimeError(
            "lark.Client 未初始化，请在 main.py 启动时调用 lark_client.init_instance()"
        )
    return _instance
