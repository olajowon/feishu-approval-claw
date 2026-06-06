"""
option_callback.py — 飞书审批「外部选项」控件回调脚本的业务逻辑层。

职责：
  - 沙箱执行 option_callback 脚本（ENV 注入、stdout/stderr 捕获、超时告警）
  - 用户信息富化（按 employee_id 查 applicant）
  - 脚本返回值 → 飞书标准响应格式转换
  - AES CBC 加密（兼容飞书官方 Golang/Java 实现）
  - 调试入口（不影响 last_request 记录）

脚本接口：
    def query(applicant: dict, form: dict, page: int, query: str, locale: str
              ) -> tuple[list[dict], bool]:
        # 返回 (options_list, has_next_page)
        # 每个 option 必须含 "value"，可选 "is_default"

执行上下文额外注入：
    ENV: dict[str, str]  — 来自 script_envvars 表
"""
import base64
import contextlib
import hashlib
import io
import json
import logging
import os
import time
import traceback
import types as _types
from typing import Optional

import requests

from config import ALERT_WEBHOOK
from services.db import (
    get_option_callback_script,
    get_script_envvars_dict,
    update_option_callback_script_last_request,
)

logger = logging.getLogger(__name__)

# 飞书外部选项控件硬性超时（毫秒），超过即认为本次回调对终端用户不可见。
_FEISHU_TIMEOUT_MS = 3000


def _send_timeout_alert(script_name: str, total_ms: float) -> None:
    """选项回调超时告警，通过飞书机器人 webhook 推送。"""
    if not ALERT_WEBHOOK:
        return
    try:
        card = {
            "msg_type": "interactive",
            "card": {
                "schema": "2.0",
                "body": {
                    "elements": [{
                        "tag": "markdown",
                        "content": (f"**选项回调超时**\n\n脚本：{script_name}\n"
                                    f"耗时：{round(total_ms)}ms（超过 "
                                    f"{_FEISHU_TIMEOUT_MS}ms 限制）"),
                        "text_align": "left",
                    }],
                },
                "header": {
                    "title": {"tag": "plain_text",
                              "content": f"⏱ 选项回调超时: {script_name}"},
                    "template": "orange",
                },
            },
        }
        requests.post(ALERT_WEBHOOK, json=card, timeout=10)
    except Exception as exc:
        logger.warning("发送选项回调超时告警失败: %s", exc)


def execute_script(code: str, script_name: str,
                   applicant: dict, form: dict, page: int,
                   query: str, locale: str) -> dict:
    """
    沙箱执行脚本的 query() 函数。

    Returns dict:
        ok            : 是否成功（无异常且返回值格式正确）
        result        : 脚本原始返回值（用于调试展示）
        options       : list[dict] | None — 成功时的选项列表
        has_next_page : bool
        stdout, stderr: 捕获的输出
        error         : 异常 traceback 字符串或 None
        format_warning: 返回值格式不符合要求的提示或 None
    """
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    result = None
    error = None

    try:
        mod = _types.ModuleType(f"_opt_cb_{script_name}")
        mod.__dict__["ENV"] = get_script_envvars_dict()
        exec(compile(code, f"option_callback_scripts/{script_name}.py", "exec"),
             mod.__dict__)
        with contextlib.redirect_stdout(stdout_buf), \
             contextlib.redirect_stderr(stderr_buf):
            if hasattr(mod, "query"):
                result = mod.query(applicant, form, page, query, locale)
            else:
                error = "脚本缺少 query 函数"
    except Exception:
        error = traceback.format_exc()

    format_warning: Optional[str] = None
    options_list: Optional[list] = None
    has_next_page = False

    if error is None:
        if not (isinstance(result, tuple) and len(result) == 2):
            format_warning = (f"返回值必须是 (list, bool) 元组，"
                              f"实际得到 {type(result).__name__}")
        else:
            options_list, has_next_page = result
            if not isinstance(options_list, list):
                format_warning = (f"第一个返回值必须是 list，"
                                  f"实际得到 {type(options_list).__name__}")
                options_list = None
            else:
                for i, opt in enumerate(options_list):
                    if not isinstance(opt, dict) or "value" not in opt:
                        format_warning = (f'options[{i}] 格式错误，'
                                          f'每项必须为 dict 且包含 "value"')
                        options_list = None
                        break

    display_result = result
    if isinstance(result, tuple):
        display_result = {"options": result[0], "has_next_page": result[1]}

    return {
        "ok": error is None and format_warning is None,
        "result": (display_result if isinstance(
            display_result, (list, tuple, dict, str, int, float, bool, type(None)),
        ) else str(display_result)),
        "options": options_list,
        "has_next_page": bool(has_next_page),
        "stdout": stdout_buf.getvalue(),
        "stderr": stderr_buf.getvalue(),
        "error": error,
        "format_warning": format_warning,
    }


def build_feishu_response(options_list: list, has_next_page: bool,
                          page: int, locale: str) -> dict:
    """将 [{value, is_default}] 列表转为飞书标准响应中的 result 对象。"""
    feishu_options = []
    texts: dict[str, str] = {}
    for i, opt in enumerate(options_list):
        opt_key = str(i)
        opt_value = str(opt.get("value", ""))
        i18n_key = f"@i18n@{opt_key}"
        feishu_opt: dict = {"id": opt_key, "value": i18n_key}
        if opt.get("is_default"):
            feishu_opt["isDefault"] = True
        feishu_options.append(feishu_opt)
        texts[i18n_key] = opt_value

    return {
        "options": feishu_options,
        "i18nResources": [
            {"locale": locale or "zh_cn", "isDefault": True, "texts": texts},
        ],
        "hasMore": bool(has_next_page),
        "nextPageToken": str(page + 1) if has_next_page else "",
    }


def aes_cbc_encrypt(plaintext: bytes, key_str: str) -> bytes:
    """AES-CBC + PKCS#7 加密；密钥取 SHA-256(key_str)；IV 随机 16 字节并前置。
    与飞书官方 Golang/Java SDK 的「外部数据源 Encrypt Key」实现兼容。"""
    from Crypto.Cipher import AES  # pycryptodome
    key = hashlib.sha256(key_str.encode()).digest()
    iv = os.urandom(16)
    pad_len = 16 - (len(plaintext) % 16)
    padded = plaintext + bytes([pad_len] * pad_len)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return iv + cipher.encrypt(padded)


def encrypt_result(result_obj: dict, encrypt_key: str) -> Optional[str]:
    """加密 result 对象，返回 base64 字符串；失败返回 None。"""
    try:
        plain = json.dumps(result_obj, ensure_ascii=False).encode("utf-8")
        return base64.b64encode(aes_cbc_encrypt(plain, encrypt_key)).decode("ascii")
    except Exception:
        logger.error("AES 加密失败:\n%s", traceback.format_exc())
        return None


_ERR_RESP = {"code": 1, "msg": "error",
             "data": {"result": {"options": [], "i18nResources": []}}}


def handle_callback(script_name: str, body: dict) -> dict:
    """处理飞书外部选项回调的完整流程。返回可直接作为 JSONResponse 的 dict。"""
    t_start = time.time()
    logger.info("[opt_cb:%s] 收到回调请求 body=%s",
                script_name, json.dumps(body, ensure_ascii=False))

    row = get_option_callback_script(script_name)
    if not row:
        logger.info("[opt_cb:%s] 脚本不存在", script_name)
        return _ERR_RESP
    if not row["enabled"]:
        logger.info("[opt_cb:%s] 脚本已禁用", script_name)
        return _ERR_RESP

    # token 校验（脚本未设置 token 则跳过）
    req_token = body.get("token", "") or ""
    if row["token"] and req_token != row["token"]:
        logger.warning("[opt_cb:%s] token 校验失败", script_name)
        return {"code": 1, "msg": "token mismatch", "data": {}}

    # applicant：默认仅含 user_id；enrich_applicant 开启时按 employee_id 拉完整字段
    uid = body.get("employee_id", "") or body.get("employeeId", "") or ""
    if row.get("enrich_applicant") and uid:
        try:
            from services.user_profile import get_user
            applicant = get_user(uid) or {"user_id": uid}
        except Exception as exc:
            logger.warning("[opt_cb:%s] 富化 applicant 失败 uid=%s: %s",
                           script_name, uid, exc)
            applicant = {"user_id": uid}
    else:
        applicant = {"user_id": uid}

    form = body.get("linkage_params", {}) or {}
    page_token = body.get("page_token", "") or ""
    page = int(page_token) if str(page_token).isdigit() else 1
    query_kw = body.get("query", "") or ""
    locale = body.get("locale", "zh_cn") or "zh_cn"

    # 执行脚本
    t_exec = time.time()
    exec_result = execute_script(row["code"], script_name,
                                 applicant, form, page, query_kw, locale)
    exec_ms = (time.time() - t_exec) * 1000

    # 记录本次调用数据（供调试面板回放）
    try:
        last_req = {"applicant": applicant, "form": form, "page": page,
                    "query": query_kw, "locale": locale}
        update_option_callback_script_last_request(
            script_name, json.dumps(last_req, ensure_ascii=False),
        )
    except Exception:
        pass

    if not exec_result["ok"] or exec_result["options"] is None:
        logger.error("[opt_cb:%s] 脚本执行失败 耗时 %.0fms error=%s warn=%s",
                     script_name, exec_ms,
                     (exec_result.get("error") or "")[:200],
                     exec_result.get("format_warning"))
        if exec_result.get("stdout"):
            logger.info("[opt_cb:%s] stdout: %s",
                        script_name, exec_result["stdout"][:500])
        if exec_result.get("stderr"):
            logger.info("[opt_cb:%s] stderr: %s",
                        script_name, exec_result["stderr"][:500])
        return _ERR_RESP

    logger.info("[opt_cb:%s] 脚本执行成功 耗时 %.0fms 返回 %d 项 has_next_page=%s",
                script_name, exec_ms, len(exec_result["options"]),
                exec_result["has_next_page"])

    result_obj = build_feishu_response(
        exec_result["options"], exec_result["has_next_page"], page, locale,
    )

    encrypt_key = row.get("encrypt_key") or ""
    if encrypt_key:
        encrypted = encrypt_result(result_obj, encrypt_key)
        if encrypted is None:
            return _ERR_RESP
        total_ms = (time.time() - t_start) * 1000
        logger.info("[opt_cb:%s] 响应完成(已加密) 总耗时 %.0fms",
                    script_name, total_ms)
        if total_ms > _FEISHU_TIMEOUT_MS:
            _send_timeout_alert(script_name, total_ms)
        return {"code": 0, "msg": "success", "data": {"result": encrypted}}

    total_ms = (time.time() - t_start) * 1000
    logger.info("[opt_cb:%s] 响应完成(明文) 总耗时 %.0fms", script_name, total_ms)
    if total_ms > _FEISHU_TIMEOUT_MS:
        _send_timeout_alert(script_name, total_ms)
    return {"code": 0, "msg": "success", "data": {"result": result_obj}}


def debug_script(script_name: str, code: str, params: dict,
                 enrich: bool = False) -> dict:
    """调试选项回调脚本，不修改 last_request。返回可直接作为 JSONResponse 的 dict。"""
    if not code:
        row = get_option_callback_script(script_name)
        if not row:
            return {"ok": False, "error": "脚本不存在且未提供代码"}
        code = row["code"]
    if not code.strip():
        return {"ok": False, "error": "代码不能为空"}

    applicant = params.get("applicant", {}) or {}
    if enrich and applicant.get("user_id"):
        try:
            from services.user_profile import get_user
            applicant = get_user(applicant["user_id"]) or applicant
        except Exception:
            pass
    form = params.get("form", {}) or {}
    page_token = params.get("page_token", "")
    page = int(page_token) if str(page_token).isdigit() else 1
    query_kw = params.get("query", "") or ""
    locale = params.get("locale", "zh_cn") or "zh_cn"

    t0 = time.time()
    result = execute_script(code, script_name, applicant, form, page, query_kw, locale)
    elapsed_ms = (time.time() - t0) * 1000
    result["elapsed_ms"] = round(elapsed_ms)
    if elapsed_ms > _FEISHU_TIMEOUT_MS:
        result["timeout_warning"] = (
            f"耗时 {round(elapsed_ms)}ms，超过飞书 {_FEISHU_TIMEOUT_MS}ms 超时限制"
        )
    elif elapsed_ms > _FEISHU_TIMEOUT_MS * 2 / 3:
        result["timeout_warning"] = (
            f"耗时 {round(elapsed_ms)}ms，接近飞书 {_FEISHU_TIMEOUT_MS}ms 超时限制"
        )
    return result
