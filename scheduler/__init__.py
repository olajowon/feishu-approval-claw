"""
scheduler — 后台定时任务。

任务：每天 12:00 清理创建时间超过 GROUP_TTL_DAYS 天的未解散群组。
实现：daemon 线程 + 每 30 秒检查一次时间，避免引入额外依赖。
"""
import logging
import time
logger = logging.getLogger(__name__)

def token_refresh_loop() -> None:
    """每 10 分钟检查 access_token，剩余不足 30 分钟则主动刷新。"""
    logger.info("Token 定时巡检已启动（每 10 分钟检查，剩余 < 30 分钟时自动刷新）")
    from services.user_token import get_instance
    while True:
        try:
            mgr = get_instance()
            if mgr is None:
                time.sleep(600)
                continue
            remaining = mgr._expires_at - time.time()
            if remaining < 1800:  # 不足 30 分钟
                logger.info("[token-checker] access_token 剩余 %.0f 秒，主动刷新…", remaining)
                ok = mgr._do_refresh()
                if ok:
                    logger.info("[token-checker] token 主动刷新成功")
                else:
                    logger.warning("[token-checker] token 主动刷新失败，refresh_token 可能已失效，请访问 /auth")
        except Exception as exc:
            logger.error("[token-checker] 异常: %s", exc)
        time.sleep(600)


def cleanup_old_groups() -> None:
    """清理超期未解散的群。"""
    from config import GROUP_TTL_DAYS
    from services.db import get_old_active_proc_tasks, dissolve_proc_task_by_chat
    from services.chat import dissolve_group

    logger.info("[scheduler] 开始清理超过 %d 天的群组", GROUP_TTL_DAYS)
    groups = get_old_active_proc_tasks(GROUP_TTL_DAYS)
    logger.info("[scheduler] 找到 %d 个需清理的群", len(groups))

    for g in groups:
        chat_id    = g["chat_id"]
        group_name = g.get("group_name", "")
        try:
            from services.user_token import get_instance as _get_utm
            mgr = _get_utm()
            user_token = (mgr._access_token if mgr else "") or ""
            dissolve_group(chat_id, user_token=user_token)
            dissolve_proc_task_by_chat(chat_id)
            logger.info("[scheduler] 已解散群：%s (chat_id=%s)", group_name, chat_id)
        except Exception as exc:
            logger.error("[scheduler] 解散群失败 chat_id=%s: %s", chat_id, exc)


def group_cleanup_loop() -> None:
    """每 1 小时检查一次。"""
    logger.info("群清理定时任务已启动（每 1 小时执行一次, 每天 12:00 清理超过 GROUP_TTL_DAYS 天的群）")
    while True:
        try:
            cleanup_old_groups()
        except Exception as exc:
            logger.error("[scheduler] 定时任务异常: %s", exc)
        time.sleep(3600)
