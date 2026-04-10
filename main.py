"""
main.py — 飞书审批自动化服务入口（精简版）。

职责：初始化各组件并启动服务，业务逻辑分布于各子模块：
  web/server.py     — HTTP 服务（OAuth、Admin、健康检查）
  handlers/approval.py — 审批事件处理
  services/db.py    — SQLite 数据存储
  scheduler/        — 定时清理任务

HTTP 接口（端口见 .env HTTP_PORT，默认 9999）：
  GET  /health                        — 健康检查
  GET  /auth                          — 飞书 OAuth 授权跳转
  GET  /callback?code=XXX             — OAuth 回调（自动写入 token）
  GET  /admin                         — 管理页面（审批/群记录、手动解散）
  POST /api/groups/<chat_id>/dissolve — 手动解散群

首次使用或 token 过期后，访问 http://localhost:<HTTP_PORT>/auth 重新授权。
"""
import logging
import signal
import sys
import threading

import lark_oapi as lark
from lark_oapi.api.approval.v4 import SubscribeApprovalRequest

from config import (
    APP_ID, APP_SECRET,
    APPROVAL_CODES, HTTP_PORT,
    WORKER_BOT_APP_ID, WORKER_BOT_APP_SECRET,
)
import config as _config
from handlers.approval import handle_approval_v1
from services.db import init_db
import services.lark_client as lark_client
import services.user_token as _user_token
import services.worker_bot as worker_bot
from services.user_profile import resolve_to_open_ids
from web.server import run_http_server
from scheduler import group_cleanup_loop, token_refresh_loop

# == 日志 =====================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# == WebSocket 连接状态标记（供 /health 查询）================================
_ws_connected: bool = False

# == 优雅关闭 =================================================================
_shutdown_event = threading.Event()


def _graceful_shutdown(signum, frame):
    """收到 SIGTERM/SIGINT 后优雅关闭：通过 uvicorn should_exit 触发事件循环退出。"""
    sig_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else str(signum)
    logger.info("收到信号 %s，开始优雅关闭…", sig_name)
    _shutdown_event.set()
    try:
        import web.server as _web_srv
        if _web_srv._uvicorn_server is not None:
            _web_srv._uvicorn_server.should_exit = True
    except Exception:
        pass


signal.signal(signal.SIGTERM, _graceful_shutdown)
signal.signal(signal.SIGINT, _graceful_shutdown)


# == 调试补丁 ==================================================================

def _patch_dispatcher(handler: lark.EventDispatcherHandler) -> None:
    """包装 do_without_validation，打印所有收到的原始事件类型（调试用）。"""
    orig = handler.do_without_validation

    def patched(payload: bytes):
        try:
            import json as _json
            raw      = _json.loads(payload)
            schema   = raw.get("schema", "?")
            header   = raw.get("header", {})
            evt_type = header.get("event_type", raw.get("event", {}).get("type", "unknown"))
            logging.getLogger("raw_event").info(
                "[RAW EVENT] schema=%s type=%s header=%s", schema, evt_type, header
            )
        except Exception:
            logging.getLogger("raw_event").info("[RAW EVENT] payload=%s", payload[:200])
        return orig(payload)

    handler.do_without_validation = patched


# == 审批订阅 ==================================================================

def _subscribe_approval(approval_code: str) -> None:
    """订阅指定审批定义的事件（重复调用幂等）。"""
    client = lark_client.get_instance()
    resp = client.approval.v4.approval.subscribe(
        SubscribeApprovalRequest.builder().approval_code(approval_code).build()
    )
    if resp.success() or resp.code == 1390007:
        logger.info("审批事件订阅成功（或已订阅）：approval_code=%s", approval_code)
    else:
        logger.error(
            "审批事件订阅失败：code=%s msg=%s，请确认应用有权限访问该审批定义",
            resp.code, resp.msg,
        )


# == 配置校验 ==================================================================

def _validate_config() -> None:
    """启动时校验配置格式，不合法则警告（不阻断启动）。"""
    from config import APPROVAL_CODES, WORKER_USER_IDS, GROUP_TTL_DAYS

    # APPROVAL_CODES：非空时每项应为字母数字和连字符
    for code in APPROVAL_CODES:
        if not code or not all(c.isalnum() or c in '-_' for c in code):
            logger.warning("APPROVAL_CODES 中存在可疑值: '%s'，请确认是否为合法审批 code", code)

    # WORKER_USER_IDS：每项应为 open_id/email/手机号格式
    for uid in WORKER_USER_IDS:
        if not uid:
            logger.warning("WORKER_USER_IDS 中存在空值，请检查配置")
        elif not (uid.startswith("ou_") or "@" in uid or uid.isdigit()):
            logger.warning("WORKER_USER_IDS 中的 '%s' 格式不符合 open_id/邮箱/手机号，请检查", uid)

    # GROUP_TTL_DAYS：应为正整数
    if GROUP_TTL_DAYS <= 0:
        logger.warning("GROUP_TTL_DAYS=%d 不合法，应为正整数", GROUP_TTL_DAYS)


# == 主函数 ====================================================================

def main() -> None:
    global _ws_connected

    # 0. 配置格式校验
    _validate_config()

    # 1. 初始化数据库
    init_db()

    # 2. 初始化主应用 lark Client 单例（需要 APP_ID、APP_SECRET）
    if not APP_ID or not APP_SECRET:
        logger.warning("缺少配置 APP_ID / APP_SECRET，无法初始化飞书客户端")
    else:
        lark_client.init_instance(APP_ID, APP_SECRET)

    # 3. 将 WORKER_USER_IDS / WORKER_ADMIN_ID 中的 email/手机号解析为 open_id
    #    支持 open_id（ou_ 开头）、邮箱（含 @）、手机号（其余）混合配置
    if APP_ID and APP_SECRET:
        _config.WORKER_USER_IDS = resolve_to_open_ids(_config.WORKER_USER_IDS)
        admin_list = resolve_to_open_ids(
            [_config.WORKER_ADMIN_ID] if _config.WORKER_ADMIN_ID else []
        )
        _config.WORKER_ADMIN_ID = admin_list[0] if admin_list else ""
        logger.info("WORKER_USER_IDS 解析结果: %s", _config.WORKER_USER_IDS)
        logger.info("WORKER_ADMIN_ID 解析结果: %s", _config.WORKER_ADMIN_ID)
    else:
        logger.warning("缺少 APP_ID / APP_SECRET，跳过 WORKER_USER_IDS / WORKER_ADMIN_ID 解析")

    # 4. 初始化用户 token 单例（需要 APP_ID、APP_SECRET）
    if not APP_ID or not APP_SECRET:
        logger.warning("缺少配置 APP_ID / APP_SECRET，无法初始化飞书用户token")
    else:
        mgr = _user_token.init_instance(APP_ID, APP_SECRET)
        if mgr._access_token:
            if mgr._refresh_token:
                logger.info("用户 token 已从 DB 加载，支持自动刷新")
            else:
                logger.warning(
                    "用户 token 已加载但无 refresh_token，过期后请访问 "
                    "http://localhost:%d/auth 重新授权", HTTP_PORT
                )
        else:
            logger.warning(
                "未找到用户 token，消息将以主应用身份发送。"
                "访问 http://localhost:%d/auth 授权后无需重启即生效。", HTTP_PORT
            )

    # 5. 初始化 Openclaw Bot 单例（需要 WORKER_BOT_APP_ID、WORKER_BOT_APP_SECRET）
    if not WORKER_BOT_APP_ID or not WORKER_BOT_APP_SECRET:
        logger.warning("缺少配置 WORKER_BOT_APP_ID / WORKER_BOT_APP_SECRET，无法初始化 Openclaw Bot")
    else:
        worker_bot.init_instance(WORKER_BOT_APP_ID, WORKER_BOT_APP_SECRET)
        logger.info("WORKER_BOT_APP open_id: %s", worker_bot.get_bot_open_id())

        # 解析 WORKER_BOT_ADMIN_ID（复用 worker_bot 的 lark.Client）
        if _config.WORKER_BOT_ADMIN_ID:
            _raw_admin_id = _config.WORKER_BOT_ADMIN_ID.strip()
            if _raw_admin_id.startswith("ou_"):
                logger.info("WORKER_BOT_ADMIN_ID 已是 open_id: %s", _raw_admin_id)
            else:
                resolved_list = resolve_to_open_ids(
                    [_raw_admin_id], client=worker_bot.get_client(),
                )
                if resolved_list:
                    _config.WORKER_BOT_ADMIN_ID = resolved_list[0]
                    logger.info("WORKER_BOT_ADMIN_ID 解析结果: %s → %s", _raw_admin_id, resolved_list[0])
                else:
                    logger.warning("WORKER_BOT_ADMIN_ID '%s' 未能解析为 open_id，保留原值", _raw_admin_id)

    # 6. 订阅审批事件（需要 APPROVAL_CODES 且 lark 客户端已初始化）
    if not APPROVAL_CODES:
        logger.warning("未配置 APPROVAL_CODES，当前不会自动订阅或处理任何审批")
    elif not APP_ID or not APP_SECRET:
        logger.warning("缺少配置 APP_ID / APP_SECRET，跳过审批事件订阅")
    else:
        for _code in APPROVAL_CODES:
            _subscribe_approval(_code)

    # 7. 启动 WebSocket 长连接（需要 APP_ID、APP_SECRET，在后台 daemon 线程运行）
    if not APP_ID or not APP_SECRET:
        logger.warning("缺少配置 APP_ID / APP_SECRET，无法启动 飞书长连接客户端，审批事件将无法实时处理")
    else:
        event_handler = (
            lark.EventDispatcherHandler.builder("", "")
            .register_p1_customized_event("approval_instance", handle_approval_v1)
            .build()
        )
        _patch_dispatcher(event_handler)
        ws_client = lark.ws.Client(
            APP_ID, APP_SECRET,
            event_handler=event_handler,
            log_level=lark.LogLevel.INFO,
            domain=_config.FEISHU_HOST,
        )
        logger.info("飞书长连接客户端启动，等待审批通过事件……")

        def _ws_thread():
            global _ws_connected
            try:
                _ws_connected = True
                ws_client.start()
            except Exception as exc:
                logger.error("飞书 WebSocket 连接异常退出: %s", exc)
            finally:
                _ws_connected = False
                logger.warning("飞书 WebSocket 连接已断开")

        threading.Thread(target=_ws_thread, daemon=True, name="lark-ws").start()

    # 8. 启动定时任务（后台 daemon 线程）
    # 群清理：依赖 DB + chat 服务，配置不足时仍启动，内部任务执行失败会打印日志
    threading.Thread(target=group_cleanup_loop, daemon=True, name="scheduler").start()

    # Token 巡检：仅在用户 token 已初始化时有意义
    if APP_ID and APP_SECRET:
        threading.Thread(target=token_refresh_loop, daemon=True, name="token-checker").start()
    else:
        logger.warning("缺少配置 APP_ID / APP_SECRET，跳过 Token 定时巡检")

    # 9. 主线程阻塞于 HTTP server（进程唯一出口）
    run_http_server()


if __name__ == "__main__":
    main()
