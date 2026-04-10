"""
user_profile.py — 用户资料查询服务（优先 user_token，降级 app_token）。
"""
import logging
from typing import Optional

import requests
from lark_oapi.api.contact.v3 import GetUserRequest

from config import FEISHU_HOST
import services.lark_client as _lark_client
import services.user_token as _user_token

logger = logging.getLogger(__name__)


def _fetch_user_with_token(open_id: str, token: str) -> tuple[Optional[dict], int]:
    resp = requests.get(
        f"{FEISHU_HOST}/open-apis/contact/v3/users/{open_id}",
        params={
            "user_id_type": "open_id",
            "department_id_type": "open_department_id",
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    body = resp.json()
    return body.get("data", {}).get("user"), body.get("code", -1)


def get_user(open_id: str) -> Optional[dict]:
    """
    通过 open_id 获取用户信息，优先 user_access_token，失败降级 app 身份。
    返回过滤后的 dict；失败返回 None。
    """
    token_mgr = _user_token.get_instance()
    if token_mgr:
        try:
            raw, code = _fetch_user_with_token(open_id, token_mgr.get_access_token())
            if raw is None and code in _user_token.TOKEN_EXPIRED_CODES:
                raw, code = _fetch_user_with_token(open_id, token_mgr.handle_expired())
            if raw:
                logger.debug("get_user via user_token open_id=%s", open_id)
                return {
                    "open_id":          raw.get("open_id") or "",
                    "union_id":         raw.get("union_id") or "",
                    "user_id":          raw.get("user_id") or "",
                    "name":             raw.get("name") or "",
                    "email":            raw.get("email") or "",
                    "enterprise_email": raw.get("enterprise_email") or "",
                    "mobile":           raw.get("mobile") or "",
                    "department_ids":   raw.get("department_ids") or [],
                    "department_path":  raw.get("department_path") or [],
                }
        except Exception as exc:
            logger.warning("user_token 获取用户失败，降级到 app_token: %s", exc)

    client = _lark_client.get_instance()
    try:
        request = (
            GetUserRequest.builder()
            .user_id(open_id)
            .user_id_type("open_id")
            .build()
        )
        response = client.contact.v3.user.get(request)
        if response.success() and response.data and response.data.user:
            u = response.data.user
            logger.debug("get_user via app_token open_id=%s", open_id)
            return {
                "open_id":          getattr(u, "open_id", ""),
                "union_id":         getattr(u, "union_id", ""),
                "user_id":          getattr(u, "user_id", ""),
                "name":             getattr(u, "name", ""),
                "email":            getattr(u, "email", ""),
                "enterprise_email": getattr(u, "enterprise_email", ""),
                "mobile":           getattr(u, "mobile", ""),
                "department_ids":   getattr(u, "department_ids", []) or [],
                "department_path":  [],
            }
        logger.warning("获取用户失败 [%s]: %s", response.code, response.msg)
    except Exception as exc:
        logger.exception("get_user 异常: %s", exc)
    return None


def resolve_to_open_ids(identifiers: list[str], client=None) -> list[str]:
    """
    将混合标识符列表（open_id / email / 手机号）统一解析为 open_id 列表。

    判断规则：
      - 已是 open_id：以 ``ou_`` 开头，直接保留
      - email：含 ``@``，通过 contact/v3 batch_get_id 解析
      - 手机号：其余情况（纯数字 / + 开头），通过 batch_get_id 解析

    无法解析（API 返回无对应用户）的标识符会在日志中警告，不加入结果。
    需要权限：``contact:user.base:readonly``（tenant_access_token 即可）。

    :param client: 可选的 lark.Client 实例，不传则使用默认主应用客户端。
    """
    if not identifiers:
        return []

    open_ids: list[str] = []
    emails:   list[str] = []
    mobiles:  list[str] = []

    for ident in identifiers:
        ident = ident.strip()
        if not ident:
            continue
        if ident.startswith("ou_"):
            open_ids.append(ident)
        elif "@" in ident:
            emails.append(ident)
        else:
            mobiles.append(ident)

    if not emails and not mobiles:
        return open_ids

    if client is None:
        client = _lark_client.get_instance()
    if client is None:
        logger.warning("resolve_to_open_ids: lark client 未初始化，无法解析 email/手机号")
        return open_ids

    try:
        from lark_oapi.api.contact.v3 import BatchGetIdUserRequest
        from lark_oapi.api.contact.v3.model import BatchGetIdUserRequestBody

        body = BatchGetIdUserRequestBody.builder()
        if emails:
            body = body.emails(emails)
        if mobiles:
            body = body.mobiles(mobiles)

        req = (
            BatchGetIdUserRequest.builder()
            .user_id_type("open_id")
            .request_body(body.build())
            .build()
        )
        resp = client.contact.v3.user.batch_get_id(req)
        if not resp.success():
            logger.warning(
                "resolve_to_open_ids: batch_get_id 失败 [%s] %s", resp.code, resp.msg
            )
            return open_ids

        user_list = (resp.data.user_list or []) if resp.data else []
        resolved_ids = [u.user_id for u in user_list if u.user_id]
        open_ids.extend(resolved_ids)

        # 记录哪些未能解析
        resolved_emails  = {u.email  for u in user_list if u.email}
        resolved_mobiles = {u.mobile for u in user_list if u.mobile}
        for e in emails:
            if e not in resolved_emails:
                logger.warning("resolve_to_open_ids: email 未找到对应用户: %s", e)
        for m in mobiles:
            if m not in resolved_mobiles:
                logger.warning("resolve_to_open_ids: 手机号未找到对应用户: %s", m)

        logger.info(
            "resolve_to_open_ids: 解析完成 emails=%s mobiles=%s → open_ids=%s",
            emails, mobiles, resolved_ids,
        )
    except Exception as exc:
        logger.exception("resolve_to_open_ids: 解析异常: %s", exc)

    return open_ids


