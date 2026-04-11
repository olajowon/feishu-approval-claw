"""
user_token.py — 管理飞书用户 access_token 的自动刷新与持久化。

飞书用户 access_token 有效期约 2 小时，需用 refresh_token 续期。
- 在 token 过期前 5 分钟自动调用 /authen/v1/refresh_access_token 刷新；
- 刷新后将新 token 持久化到 .user_token.json，程序重启后优先复用；
- API 返回 token 无效错误（99991663/99991668）时可调用 handle_expired() 强制刷新。

刷新接口：
  POST /open-apis/authen/v1/refresh_access_token
  Headers: Authorization: Bearer <app_access_token>
  Body:    {"grant_type": "refresh_token", "refresh_token": "<refresh_token>"}
"""
import logging
import threading
import time
from typing import Optional

import requests

from config import FEISHU_HOST as _FEISHU_HOST

logger = logging.getLogger(__name__)

# 飞书返回 token 失效的错误码
TOKEN_EXPIRED_CODES = {99991663, 99991668, 99991661, 99991677}


class UserTokenManager:
    """持有用户 access_token / refresh_token，支持自动刷新与持久化。"""

    def __init__(
        self,
        app_id: str,
        app_secret: str,
        access_token: str,
        refresh_token: str,
        expires_at: float = 0.0,
        refresh_expires_at: float = 0.0,
    ):
        self._app_id = app_id
        self._app_secret = app_secret
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._expires_at: float = expires_at
        self._refresh_expires_at: float = refresh_expires_at
        self._refresh_lock = threading.Lock()

    # ── 公开接口 ────────────────────────────────────────────────────────────

    def get_access_token(self) -> str:
        """返回有效的 access_token；若距过期不足 5 分钟则先刷新。"""
        if self._refresh_token and time.time() >= self._expires_at - 300:
            self._do_refresh()
        return self._access_token

    @property
    def expires_in(self) -> float:
        """返回 access_token 距过期的剩余秒数（可为负，表示已过期）。"""
        return self._expires_at - time.time()

    def try_refresh(self) -> bool:
        """主动尝试刷新 token。成功返回 True，失败返回 False。"""
        return self._do_refresh()

    def handle_expired(self) -> str:
        """
        API 返回 token 无效错误时调用，强制立即刷新并返回新 token。
        若 refresh_token 也已失效，抛出 RuntimeError 提示用户重新授权。
        """
        logger.warning("用户 token 已过期/无效，强制刷新…")
        self._expires_at = 0  # 令 get_access_token 触发 _do_refresh
        if not self._do_refresh():
            raise RuntimeError(
                "用户 token 及 refresh_token 均已失效，请访问 /auth 重新授权后服务自动恢复。"
            )
        return self._access_token

    # ── 内部实现 ────────────────────────────────────────────────────────────

    def _get_app_access_token(self) -> str:
        try:
            resp = requests.post(
                f"{_FEISHU_HOST}/open-apis/auth/v3/app_access_token/internal",
                json={"app_id": self._app_id, "app_secret": self._app_secret},
                timeout=10,
            )
            data = resp.json()
            token = data.get("app_access_token", "")
            if not token:
                logger.error("获取 app_access_token 失败: %s", data)
            return token
        except Exception as e:
            logger.error("获取 app_access_token 异常: %s", e)
            return ""

    def _do_refresh(self) -> bool:
        """
        尝试用 refresh_token 换新 access_token。
        成功返回 True；失败返回 False。
        加锁防止多线程并发消费一次性 refresh_token。
        """
        if not self._refresh_token:
            logger.warning("未配置 refresh_token，无法自动刷新用户 token")
            return False

        if not self._refresh_lock.acquire(blocking=False):
            # 另一个线程正在刷新，等待其完成后直接返回
            with self._refresh_lock:
                return bool(self._access_token)

        try:
            return self._do_refresh_locked()
        finally:
            self._refresh_lock.release()

    def _do_refresh_locked(self) -> bool:
        """持有 _refresh_lock 时执行实际刷新逻辑。"""
        import base64 as _b64
        credentials = _b64.b64encode(f"{self._app_id}:{self._app_secret}".encode()).decode()
        try:
            resp = requests.post(
                f"{_FEISHU_HOST}/open-apis/authen/v2/oauth/token",
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Content-Type": "application/json; charset=utf-8",
                },
                json={"grant_type": "refresh_token", "refresh_token": self._refresh_token},
                timeout=10,
            )
            body = resp.json()
        except Exception as e:
            logger.error("刷新用户 token 网络异常: %s", e)
            return False

        if "access_token" in body:
            expires_in = body.get("expires_in") or 7200
            refresh_expires_in = body.get("refresh_token_expires_in") or 2592000
            self._access_token  = body["access_token"]
            self._refresh_token = body.get("refresh_token", self._refresh_token)
            self._expires_at    = time.time() + expires_in
            self._refresh_expires_at = time.time() + refresh_expires_in
            logger.info(
                "用户 token 刷新成功，access_token 有效期 %d 秒，refresh_token 有效期 %s 秒",
                expires_in, refresh_expires_in,
            )
            self._persist()
            return True
        else:
            err_code = body.get("code", 0)
            logger.error(
                "用户 token 刷新失败 (code=%s): %s",
                err_code, body,
            )
            return False

    def _persist(self) -> None:
        """将最新 token 持久化到 DB，save_user_token 是唯一写 DB 的路径。"""
        try:
            from services.db import save_user_token
            save_user_token(
                self._access_token,
                self._refresh_token,
                self._expires_at,
                self._refresh_expires_at,  # 0.0 时不覆盖
            )
        except Exception as e:
            logger.warning("持久化用户 token 失败: %s", e)


# ---------------------------------------------------------------------------
# 全局单例管理 — 所有模块通过 get_instance() 取用，不再传引用
# ---------------------------------------------------------------------------

_instance: Optional[UserTokenManager] = None
_instance_lock = threading.Lock()


def get_instance() -> Optional[UserTokenManager]:
    """返回全局单例，未调用 init_instance 前返回 None。"""
    return _instance


def init_instance(app_id: str, app_secret: str) -> UserTokenManager:
    """
    创建（或复用）全局单例，自动从 DB 加载已有 token。
    程序启动时调用一次；OAuth 回调后直接 in-place 更新单例字段，无需再次调用。
    """
    global _instance
    if _instance is not None:
        return _instance
    with _instance_lock:
        if _instance is not None:
            return _instance
        from services.db import load_user_token
        data = load_user_token()  # 始终返回 dict（access_token 可能为空）
        _instance = UserTokenManager(
            app_id, app_secret,
            data["access_token"],
            data["refresh_token"],
            data["expires_at"],
            data["refresh_expires_at"],
        )
    return _instance
