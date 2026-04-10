"""
web/server.py — 内嵌 HTTP 服务器。

路由：
  GET  /health                          — 健康检查
  GET  /auth                            — 跳转飞书 OAuth 授权
  GET  /callback?code=XXX               — OAuth 回调，自动写入 token
  GET  /admin                           — 管理页面（审批 + 群列表）
  POST /api/groups/<chat_id>/dissolve   — 手动解散群
  POST /api/notify/send                 — 发送飞书应用消息
"""
import base64
import html as _html_mod
import json
import logging
import os
import re
import threading
from urllib.parse import parse_qs, urlparse

import requests
from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, PlainTextResponse

from config import (
    APP_ID, APP_SECRET,
    FEISHU_HOST, REDIRECT_URI, HTTP_PORT,
    ADMIN_USER, ADMIN_PASS, ACCOUNTS,
    get_missing_configs,
)

import services.user_token as _user_token

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# OAuth 工具
# ---------------------------------------------------------------------------

def exchange_code_for_token(code: str) -> dict:
    """
    OAuth2 授权码换 token。
    POST /open-apis/authen/v2/oauth/token  — Basic Auth。
    """
    credentials = base64.b64encode(f"{APP_ID}:{APP_SECRET}".encode()).decode()
    r = requests.post(
        f"{FEISHU_HOST}/open-apis/authen/v2/oauth/token",
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json; charset=utf-8",
        },
        json={"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI},
        timeout=10,
    )
    body = r.json()
    if body.get("code", 0) != 0 or "access_token" not in body:
        raise RuntimeError(f"换取用户 token 失败: {body}")
    return body


def apply_new_token(access_token: str, refresh_token: str, expires_in: int,
                    refresh_expires_in: int = None) -> None:
    """
    OAuth 回调后热更新 token。
    直接 in-place 修改全局单例字段，所有持有单例引用的模块自动可见新值。
    """
    import time as _time
    mgr = _user_token.get_instance()
    if mgr is None:
        logger.error("apply_new_token: UserTokenManager 单例未初始化，请检查启动流程")
        return
    mgr._access_token  = access_token
    mgr._refresh_token = refresh_token
    mgr._expires_at    = _time.time() + expires_in
    if refresh_expires_in:
        mgr._refresh_expires_at = _time.time() + refresh_expires_in
    mgr._persist()
    logger.info("用户 token 已热更新，access_token 有效期 %d 秒，refresh_expires_in=%s 秒",
                expires_in, refresh_expires_in or "未知")


# ---------------------------------------------------------------------------
# 管理页 HTML 助手
# ---------------------------------------------------------------------------

# ── 共用 CSS ─────────────────────────────────────────────────────────────
_ADMIN_CSS = (
    '  <style>\n'
    '    * { box-sizing: border-box; margin:0; padding:0; }\n'
    '    body      { font-family: "PingFang SC", "Microsoft YaHei", sans-serif; margin: 0; padding: 0; background: #f0f2f5; display:flex; min-height:100vh; }\n'
    '    /* == 左侧竖向导航栏 == */\n'
    '    .sidebar  { width:200px; background:#1d2129; color:#fff; display:flex; flex-direction:column; flex-shrink:0; position:fixed; top:0; left:0; bottom:0; z-index:100; overflow-y:auto; }\n'
    '    .sidebar .logo { padding:20px 16px 12px; font-size:15px; font-weight:700; color:#fff; border-bottom:1px solid rgba(255,255,255,.1); white-space:nowrap; display:flex; align-items:center; gap:8px; }\n'
    '    .sidebar .logo svg { flex-shrink:0; }\n'
    '    .sidebar .nav-items { flex:1; padding:8px 0; }\n'
    '    .sidebar a { display:flex; align-items:center; padding:10px 18px; color:rgba(255,255,255,.7); text-decoration:none; font-size:13px; transition:background .15s,color .15s; border-left:3px solid transparent; }\n'
    '    .sidebar a:hover { background:rgba(255,255,255,.08); color:#fff; }\n'
    '    .sidebar a.active { background:rgba(26,115,232,.25); color:#4a9eff; border-left-color:#4a9eff; font-weight:600; }\n'
    '    .sidebar a svg { margin-right:8px; flex-shrink:0; }\n'
    '    .sidebar .nav-bottom { padding:12px 16px; border-top:1px solid rgba(255,255,255,.1); font-size:12px; }\n'
    '    .sidebar .nav-bottom a { padding:6px 0; border-left:none; color:rgba(255,255,255,.5); font-size:12px; }\n'
    '    .sidebar .nav-bottom a:hover { color:#fff; background:none; }\n'
    '    /* == 右侧主内容区 == */\n'
    '    .main-wrap { margin-left:200px; flex:1; min-width:0; display:flex; flex-direction:column; }\n'
    '    .top-bar   { background:#fff; padding:0; display:flex; flex-direction:column; box-shadow:0 1px 3px rgba(0,0,0,.06); position:sticky; top:0; z-index:50; }\n'
    '    .top-row   { display:flex; align-items:center; justify-content:space-between; padding:12px 24px; }\n'
    '    .top-bar h1 { color:#1d2129; font-size:18px; }\n'
    '    .actions a { margin-left:12px; color:#4a90d9; text-decoration:none; font-size:13px; }\n'
    '    .token-row { display:flex; align-items:center; justify-content:space-between; padding:10px 24px; font-size:12px; border-top:1px solid #f0f0f0; }\n'
    '    .token-row .token-info { flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }\n'
    '    .token-row .token-actions { flex-shrink:0; display:flex; align-items:center; gap:10px; margin-left:16px; }\n'
    '    .token-row .token-actions a { color:#4a90d9; text-decoration:none; font-size:12px; white-space:nowrap; }\n'
    '    .token-row .token-actions a:hover { text-decoration:underline; }\n'
    '    .main-content { padding:16px 24px 24px; flex:1; }\n'
    '    .pager    { display:flex; align-items:center; margin:12px 0; font-size:13px; }\n'
    '    table     { border-collapse:collapse; width:100%; background:#fff; border-radius:8px; overflow:hidden; box-shadow:0 1px 4px rgba(0,0,0,.1); }\n'
    '    th        { background:#1d2129; color:#fff; padding:10px 12px; text-align:left; font-size:13px; white-space:nowrap; }\n'
    '    td        { padding:8px 10px; border-bottom:1px solid #f0f0f0; font-size:13px; vertical-align:middle; }\n'
    '    tr:last-child td { border-bottom:none; }\n'
    '    tr:hover td { background:#f7faff; }\n'
    '    .btn-red    { background:#d93025; color:#fff; border:none; padding:3px 10px; border-radius:4px; cursor:pointer; font-size:12px; }\n'
    '    .btn-red:hover    { background:#b71c1c; }\n'
    '    .btn-orange { background:#e37400; color:#fff; border:none; padding:3px 10px; border-radius:4px; cursor:pointer; font-size:12px; margin-left:4px; }\n'
    '    .btn-orange:hover { background:#bf6000; }\n'
    '    .btn-info   { background:none; border:none; color:#e37400; cursor:pointer; font-size:12px; padding:0; text-decoration:underline; }\n'
    '    .modal-ov   { }\n'
    '    .notice-warn { background:#fff7e6; border:1px solid #ffd591; color:#8d5b00; border-radius:8px; padding:12px 14px; margin-bottom:16px; font-size:13px; line-height:1.8; }\n'
    '    .CodeMirror { height:100%; width:100%; max-width:100%; font-size:13px; font-family:"Menlo","Consolas",monospace; background:#fafafa; }\n'
    '    .CodeMirror-gutters { background:#f7f7f7; border-right:1px solid #e5e5e5; }\n'
    '    /* 响应式：移动端侧边栏折叠 */\n'
    '    @media (max-width: 768px) {\n'
    '      .sidebar { width:56px; }\n'
    '      .sidebar .logo { font-size:0; padding:16px 12px; justify-content:center; }\n'
    '      .sidebar .logo svg { width:28px; height:28px; }\n'
    '      .sidebar a span { display:none; }\n'
    '      .sidebar a { padding:12px 16px; justify-content:center; }\n'
    '      .sidebar a svg { margin-right:0; }\n'
    '      .main-wrap { margin-left:56px; }\n'
    '      .sidebar .nav-bottom { display:none; }\n'
    '    }\n'
    '  </style>\n'
)

_EDITOR_ASSETS = (
    '  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.css">\n'
    '  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/theme/eclipse.min.css">\n'
    '  <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.js"></script>\n'
    '  <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/python/python.min.js"></script>\n'
    '  <script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/addon/edit/matchbrackets.min.js"></script>\n'
)

# ── 共用 JS ───────────────────────────────────────────────────────────────
_ADMIN_JS = (
    "<script>\n"
    "function showInfo(text) {\n"
    "  if (!text) return;\n"
    "  var ov = document.createElement(\'div\');\n"
    "  ov.style.cssText = \'position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:9999;"
    "display:flex;align-items:center;justify-content:center\';\n"
    "  var box = document.createElement(\'div\');\n"
    "  box.style.cssText = \'background:#fff;border-radius:8px;padding:24px 28px;max-width:640px;"
    "width:90%;max-height:70vh;overflow:auto;position:relative\';\n"
    "  box.innerHTML = \'<button onclick=\\\"this.closest(\\\'.modal-ov\\\').remove()\\\" style=\\\""
    "position:absolute;top:8px;right:12px;background:none;border:none;font-size:18px;cursor:pointer\\\">✕</button>"
    "<pre style=\\\"white-space:pre-wrap;word-break:break-all;font-size:13px;margin:20px 0 0\\\">' "
    "+ text + \'</pre>\';\n"
    "  ov.className = \'modal-ov\';\n"
    "  ov.onclick = function(e){ if(e.target===ov) ov.remove(); };\n"
    "  ov.appendChild(box);\n"
    "  document.body.appendChild(ov);\n"
    "}\n"
    "async function retryTask(ic, subj) {\n"
    "  if (!confirm(\'重试处理：\' + (subj||ic) + \'\\n\\n将从上次失败节点继续，确认重试？\')) return;\n"
    "  const r = await fetch(\'/api/tasks/\' + ic + \'/retry\', {method:\'POST\'});\n"
    "  const j = await r.json();\n"
    "  if (j.ok) { alert(\'✓ 重试成功\'); location.reload(); }\n"
    "  else { alert(\'✗ 重试失败：\' + j.error); }\n"
    "}\n"
    "async function retryCheckTask(ic, subj) {\n"
    "  if (!confirm(\'重试预检查：\' + (subj||ic) + \'\\n\\n将重新执行检查脚本并自动审批节点，确认？\')) return;\n"
    "  const r = await fetch(\'/api/check-tasks/\' + ic + \'/retry\', {method:\'POST\'});\n"
    "  const j = await r.json();\n"
    "  if (j.ok) { alert(\'✓ 预检查重试成功\'); location.reload(); }\n"
    "  else { alert(\'✗ 重试失败：\' + j.error); }\n"
    "}\n"
    "async function dissolve(chatId, gname) {\n"
    "  if (!confirm(\'【第一步确认】\\n即将解散群组：\\n\' + gname + \'\\n\\n此操作不可撤销，是否继续？\')) return;\n"
    "  if (!confirm(\'【第二步确认】\\n再次确认：\\n解散后群组将永久消失，成员会被移出。\\n\\n确认解散？\')) return;\n"
    "  const r = await fetch(\'/api/groups/\' + chatId + \'/dissolve\', {method:\'POST\'});\n"
    "  const j = await r.json();\n"
    "  if (j.ok) { alert(\'✓ 已成功解散群组\'); location.reload(); }\n"
    "  else if (j.need_reauth) {\n"
    "    if (confirm(\'✗ Token 缺少 im:chat 权限，无法通过接口解散。\\n\\n\'\n"
    "      + \'请点击【确定】重新授权（会在新标签页打开），授权后刷新本页再试。\\n\'\n"
    "      + \'也可让群主在飞书客户端直接解散群。\')) {\n"
    "      window.open(\'/auth\', \'_blank\');\n"
    "    }\n"
    "  } else { alert(\'✗ 解散失败：\' + j.error); }\n"
    "}\n"
    "</script>"
)

# ── 标签常量 ──────────────────────────────────────────────────────────────
_STAGE_LABELS = {
    "init":           "初始化",
    "fetch_instance": "获取审批详情",
    "fetch_user":     "获取申请人",
    "create_group":   "创建群组",
    "run_script":     "执行脚本",
    "send_message":   "发送通知",
    "done":           "已完成",
}
_PROC_TYPE_LABELS = {
    "group":  "🏠 建群",
    "script": "⚡ 脚本",
}
_CHECK_STATUS_LABELS = {
    "pending":  ("⏳ 待执行", "#888"),
    "passed":   ("✓ 通过",    "#1a7f3c"),
    "rejected": ("✗ 不通过", "#d93025"),
    "skipped":  ("⊘ 跳过",   "#888"),
    "error":    ("⚠ 错误",   "#e37400"),
}
_CHECK_STAGE_LABELS = {
    "init":         "初始化",
    "run_check":    "执行检查",
    "approve_node": "提交审批",
    "done":         "已完成",
}


def _status_badge(proc_status: str) -> str:
    colors = {"success": "#1a7f3c", "error": "#d93025", "pending": "#888"}
    labels = {"success": "✓ 成功", "error": "✗ 失败", "pending": "⏳ 处理中"}
    return (f'<span style="color:{colors.get(proc_status, "#888")};font-weight:600">'
            f'{labels.get(proc_status, proc_status or "-")}</span>')


def _build_token_html() -> str:
    """生成 token 状态 HTML 片段。"""
    import time as _time
    from datetime import datetime as _dt
    from services.db import get_setting
    mgr = _user_token.get_instance()
    if mgr:
        remaining  = max(0, int(mgr._expires_at - _time.time()))
        access_exp = _dt.fromtimestamp(mgr._expires_at).strftime("%Y-%m-%d %H:%M:%S")
        ac  = "#1a7f3c" if remaining > 600 else "#d93025"
        html = (
            f'<span style="color:{ac}">'
            f'Access Token 到期: {access_exp}（剩余 {remaining//60} 分钟）</span>'
        )
        rt_exp_val = get_setting("user_refresh_token_expires_at")
        if rt_exp_val:
            rt_ts   = float(rt_exp_val)
            rt_str  = _dt.fromtimestamp(rt_ts).strftime("%Y-%m-%d %H:%M:%S")
            rt_days = max(0, int((rt_ts - _time.time()) // 86400))
            rc      = "#1a7f3c" if rt_days > 3 else "#d93025"
            html += (
                f' &nbsp;|&nbsp; <span style="color:{rc}">'
                f'Refresh Token 过期时间: {rt_str}（剩余 {rt_days} 天）</span>'
            )
        else:
            html += (' &nbsp;|&nbsp; <span style="color:#e37400">'
                     'Refresh Token 到期未知，请 <a href="/auth" target="_blank">重新授权</a> 一次</span>')
    else:
        missing_auth = get_missing_configs(["APP_ID", "APP_SECRET", "REDIRECT_URI"])
        if missing_auth:
            html = ('<span style="color:#d93025">主应用尚未完成配置：'
                    + ", ".join(missing_auth)
                    + '。请前往 <a href="/admin/settings">/admin/settings</a> 配置并重启。</span>')
        else:
            html = ('<span style="color:#d93025">未配置用户 Token，'
                    '请 <a href="/auth" target="_blank">立即授权</a></span>')
    return html


def _build_auth_warning() -> str:
    """当用户 token 缺失或完全过期（且无法自动刷新）时，返回醒目提示 HTML；否则返回空串。"""
    import time as _time
    mgr = _user_token.get_instance()
    if mgr is None:
        return (
            '<div style="background:#fff1f0;border:2px solid #ff4d4f;border-radius:8px;'
            'padding:14px 18px;margin-bottom:16px;font-size:13px;line-height:1.8">'
            '<b style="color:#d93025;font-size:14px">⚠ 尚未完成飞书授权</b><br>'
            '系统需要一个<b>飞书用户级 token</b> 才能代表真实用户：①发送群消息 ②创建/解散处理群。'
            '主应用（机器人）身份无法执行这些操作。<br>'
            '<b>请先在"系统配置"中完成 APP_ID / APP_SECRET / REDIRECT_URI 设置，'
            '然后访问 <a href="/auth" style="color:#1a73e8">/auth</a> 完成授权。</b>'
            '</div>'
        )
    if not mgr._access_token:
        return (
            '<div style="background:#fff1f0;border:2px solid #ff4d4f;border-radius:8px;'
            'padding:14px 18px;margin-bottom:16px;font-size:13px;line-height:1.8">'
            '<b style="color:#d93025;font-size:14px">⚠ 未找到用户 Token，功能受限</b><br>'
            '没有用户 token，系统将以主应用（机器人）身份发送消息，<b>无法创建/解散群组</b>。<br>'
            '请访问 <a href="/auth" style="color:#1a73e8;font-weight:600">/auth</a> 完成飞书授权，授权后无需重启即生效。'
            '</div>'
        )
    remaining = mgr._expires_at - _time.time()
    if remaining <= 0 and not mgr._refresh_token:
        return (
            '<div style="background:#fff1f0;border:2px solid #ff4d4f;border-radius:8px;'
            'padding:14px 18px;margin-bottom:16px;font-size:13px;line-height:1.8">'
            '<b style="color:#d93025;font-size:14px">⚠ 用户 Token 已过期且无法自动续期</b><br>'
            '用户 token 已失效，且没有 refresh_token，系统将无法自动刷新。'
            '发送消息和群操作可能失败。<br>'
            '请重新访问 <a href="/auth" style="color:#1a73e8;font-weight:600">/auth</a> 完成授权。'
            '</div>'
        )
    return ""


def _page_shell(active: str, token_h: str, body: str, is_admin: bool = True, current_user: str = "") -> str:
    """返回完整 HTML 页面（左侧竖向导航 + 右侧主内容区）。"""
    import html as _html
    _tab_icons = {
        "process-records":
            '<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">'
            '<path d="M2 3h12v1.5H2zm0 4h12v1.5H2zm0 4h8v1.5H2z"/></svg>',
        "precheck-records":
            '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" '
            'stroke-linecap="round" stroke-linejoin="round">'
            '<rect x="2" y="2" width="12" height="12" rx="1.5"/><polyline points="5.5,8 7.5,10 11,5.5"/></svg>',
        "process-scripts":
            '<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">'
            '<path d="M5.5 4.2L1.5 8l4 3.8.8-.9L3.2 8l3.1-2.9-.8-.9zm5 0l-.8.9L12.8 8l-3.1 2.9.8.9 4-3.8-4-3.8z'
            'M9.3 3.5l-2.6 9 1.4.4 2.6-9-1.4-.4z"/></svg>',
        "precheck-scripts":
            '<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">'
            '<path d="M4.7 4.2L.7 8l4 3.8.8-.9L2.4 8l3.1-2.9-.8-.9zM8 3.5L5.4 12.5l1.4.4 2.6-9-1.4-.4z"/>'
            '<circle cx="12.5" cy="10.5" r="3" fill="none" stroke="currentColor" stroke-width="1.3"/>'
            '<polyline points="11,10.5 12.2,11.7 14.5,9" fill="none" stroke="currentColor" stroke-width="1.3" '
            'stroke-linecap="round" stroke-linejoin="round"/></svg>',
        "settings":
            '<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">'
            '<path d="M7.5 1l-.4 2c-.4.1-.8.3-1.1.6l-1.9-.8-1.5 1.5.8 1.9c-.3.3-.5.7-.6 1.1l-2 .4v2.1l2 .4'
            'c.1.4.3.8.6 1.1l-.8 1.9 1.5 1.5 1.9-.8c.3.3.7.5 1.1.6l.4 2h2.1l.4-2c.4-.1.8-.3 1.1-.6l1.9.8'
            ' 1.5-1.5-.8-1.9c.3-.3.5-.7.6-1.1l2-.4V7.5l-2-.4c-.1-.4-.3-.8-.6-1.1l.8-1.9-1.5-1.5-1.9.8'
            'c-.3-.3-.7-.5-1.1-.6l-.4-2H7.5zM8.6 5.5a3 3 0 1 1 0 6 3 3 0 0 1 0-6z"/></svg>',
        "about":
            '<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">'
            '<circle cx="8" cy="8" r="7" fill="none" stroke="currentColor" stroke-width="1.5"/>'
            '<text x="8" y="12" text-anchor="middle" font-size="9" font-weight="bold">i</text></svg>',
        "logs":
            '<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">'
            '<path d="M3 2h10v1.2H3zm0 3.2h10v1.2H3zm0 3.2h7v1.2H3zm0 3.2h5v1.2H3z"/>'
            '<circle cx="12.5" cy="11.5" r="3" fill="none" stroke="currentColor" stroke-width="1.3"/>'
            '<line x1="12.5" y1="10" x2="12.5" y2="12" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>'
            '<line x1="11" y1="11.5" x2="14" y2="11.5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>',
        "envvars":
            '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round">'
            '<rect x="1.5" y="3" width="13" height="10" rx="1.5"/>'
            '<path d="M5 8h6M8 6v4" stroke-linejoin="round"/></svg>',
    }
    tabs = [
        ("process-records",  "处理记录",         "/admin/process-records"),
        ("precheck-records", "预检查记录",       "/admin/precheck-records"),
        ("process-scripts",  "处理脚本",         "/admin/process-scripts"),
        ("precheck-scripts", "预检查脚本",       "/admin/precheck-scripts"),
        ("envvars",          "环境变量",         "/admin/envvars"),
        ("settings",         "系统配置",         "/admin/settings"),
        ("logs",             "操作记录",         "/admin/logs"),
        ("about",            "系统介绍",         "/admin/about"),
    ]
    if not is_admin:
        tabs = [t for t in tabs if t[0] not in ("settings", "logs")]

    esc_user = _html.escape(current_user) if current_user else ""

    # 获取当前 tab 显示名称
    _active_label = "管理后台"
    for key, label, _href in tabs:
        if key == active:
            _active_label = label
            break

    nav_items = "\n".join(
        f'      <a href="{href}"' + (' class="active"' if key == active else '')
        + f'>{_tab_icons.get(key,"")}<span>{_html.escape(label)}</span></a>'
        for key, label, href in tabs
    )
    return (
        '<!DOCTYPE html>\n<html lang="zh">\n<head>\n'
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" content="width=device-width,initial-scale=1">\n'
        '  <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,'
        '%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 48 48%22%3E'
        '%3Cg stroke=%22%23000%22 stroke-width=%222.8%22 stroke-linecap=%22square%22 '
        'fill=%22none%22 transform=%22translate(48,0) scale(-1,1)%22%3E'
        '%3Cpath d=%22M3,3 L22,42%22/%3E%3Cpath d=%22M12,3 L31,42%22/%3E'
        '%3Cpath d=%22M21,3 L35,32 L46,10%22/%3E%3C/g%3E%3C/svg%3E">\n'
        '  <title>飞书审批Claw管理后台</title>\n'
        + _ADMIN_CSS
        + _ADMIN_JS
        + _EDITOR_ASSETS + '\n'
        '</head>\n<body>\n'
        # == 左侧导航栏 ==
        '  <nav class="sidebar">\n'
        '    <div class="logo">'
    '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 48 48" fill="none">'
    '<g stroke="#fff" stroke-width="2.8" stroke-linecap="square" stroke-linejoin="miter" fill="none" transform="translate(48,0) scale(-1,1)">'
    '<path d="M3,3 L22,42"/>'
    '<path d="M12,3 L31,42"/>'
    '<path d="M21,3 L35,32 L46,10"/>'
    '</g></svg>'
    '飞书审批CLAW</div>\n'
        '    <div class="nav-items">\n'
        + nav_items + '\n'
        '    </div>\n'
        '    <div class="nav-bottom">\n'
        + (f'      <div style="color:rgba(255,255,255,.6);margin-bottom:6px;font-size:11px">👤 {esc_user}</div>\n' if esc_user else '')
        + '    </div>\n'
        '  </nav>\n'
        # == 右侧主内容 ==
        '  <div class="main-wrap">\n'
        '    <div class="top-bar">\n'
        '      <div class="top-row">\n'
        f'        <h1>{_html.escape(_active_label)}</h1>\n'
        '        <div class="actions">\n'
        + (f'          <span style="font-size:12px;color:#888">当前用户：<b style="color:#333">{esc_user}</b></span>\n' if esc_user else '')
        + '        </div>\n'
        '      </div>\n'
        + (('      <div class="token-row">\n'
            '        <div class="token-info">' + token_h + '</div>\n'
            '        <div class="token-actions">\n'
            '          <a href="/health" target="_blank">🩺 健康检查</a>\n'
            '          <a href="/auth" target="_blank">🔑 重新授权</a>\n'
            '        </div>\n'
            '      </div>\n') if is_admin else '')
        + '    </div>\n'
        + '    <div class="main-content">\n'
        + _build_auth_warning()
        + body
        + '    </div>\n'
        '  </div>\n'
        + '<script>\n'
        + 'function doLogout(){'
        + "location.replace('/logout');}\n"
        + '</script>\n'
        + '\n</body>\n</html>'
    )


def _applicant_cell(r: dict) -> str:
    """申请人单元格：有 applicant_json 时渲染可点击的 JSON 弹窗按钮（与 _form_cell 风格一致）。"""
    import json as _json
    display = _html_mod.escape(r.get("applicant_name") or r.get("applicant_open_id") or "-")
    aj = r.get("applicant_json") or "{}"
    if not aj or aj in ("{}", "null"):
        return display
    try:
        pretty = _html_mod.escape(_json.dumps(_json.loads(aj), ensure_ascii=False, indent=2))
    except Exception:
        return display
    return ('<button class="btn-info" data-info="' + pretty
            + '" onclick="showInfo(this.dataset.info)">' + display + '</button>')


def _form_cell(fj: str) -> str:
    """将 form_json 字符串转成表单弹窗按钮 HTML，无内容时返回 '-'。"""
    import json as _json
    if not fj or fj in ("{}", "null"):
        return "-"
    try:
        pretty = _html_mod.escape(_json.dumps(_json.loads(fj), ensure_ascii=False, indent=2))
    except Exception:
        pretty = _html_mod.escape(fj)
    return ('<button class="btn-info" data-info="' + pretty
            + '" onclick="showInfo(this.dataset.info)">表单</button>')


def _render_proc_page(page: int = 1, page_size: int = 20,
                      name: str = "", subject: str = "",
                      is_admin: bool = True, current_user: str = "") -> str:
    """渲染处理任务记录页（/admin/process-records）。"""
    import urllib.parse as _up
    from services.db import list_proc_tasks_paged, count_proc_tasks

    total       = count_proc_tasks(name=name, subject=subject)
    total_pages = max(1, (total + page_size - 1) // page_size)
    page        = max(1, min(page, total_pages))
    records     = list_proc_tasks_paged(page, page_size, name=name, subject=subject)

    _qs_base = ""
    if name:    _qs_base += f"&name={_up.quote(name)}"
    if subject: _qs_base += f"&subject={_up.quote(subject)}"
    if page_size != 20: _qs_base += f"&page_size={page_size}"

    def _plink(p, lbl):
        if p < 1 or p > total_pages:
            return f'<span style="color:#ccc;padding:4px 8px">{lbl}</span>'
        return (f'<a href="/admin/process-records?page={p}{_qs_base}" style="color:#4a90d9;text-decoration:none;'
                f'padding:4px 8px;border:1px solid #c9d1e0;border-radius:4px">{lbl}</a>')

    pagination = (
        f'{_plink(page-1, "◄ 上一页")}'
        f'<span style="margin:0 12px;color:#555">第 {page} / {total_pages} 页（共 {total} 条）</span>'
        f'{_plink(page+1, "下一页 ►")}'
    )

    def _esc(s): return s.replace('"', '&quot;').replace('<', '&lt;')
    _inp      = 'style="border:1px solid #c9d1e0;border-radius:6px;padding:6px 10px;font-size:14px;height:36px"'
    _btn_blue = 'style="background:#1a73e8;color:#fff;border:none;padding:0 18px;height:36px;border-radius:6px;cursor:pointer;font-size:14px"'
    _btn_gray = 'style="background:#fff;color:#555;border:1px solid #c9d1e0;padding:0 14px;height:36px;border-radius:6px;cursor:pointer;font-size:14px;text-decoration:none;display:inline-flex;align-items:center"'
    _ps_opts  = ''.join(
        f'<option value="{n}"' + (' selected' if n == page_size else '') + f'>{n} 条/页</option>'
        for n in [10, 20, 50, 100]
    )
    search_form = (
        '<form method="get" action="/admin/process-records" '
        'style="display:flex;gap:10px;align-items:center;margin-bottom:14px;flex-wrap:wrap">'
        f'<input name="name" placeholder="申请人" value="{_esc(name)}" {_inp} style="width:140px;border:1px solid #c9d1e0;border-radius:6px;padding:6px 10px;font-size:14px;height:36px">'
        f'<input name="subject" placeholder="申请事项" value="{_esc(subject)}" {_inp} style="width:180px;border:1px solid #c9d1e0;border-radius:6px;padding:6px 10px;font-size:14px;height:36px">'
        f'<select name="page_size" onchange="this.form.submit()" style="border:1px solid #c9d1e0;border-radius:6px;padding:0 8px;font-size:14px;height:36px;cursor:pointer">{_ps_opts}</select>'
        f'<button type="submit" {_btn_blue}>搜索</button>'
        f'<a href="/admin/process-records" {_btn_gray}>重置</a>'
        f'<button type="button" onclick="location.reload()" {_btn_gray}>刷新</button>'
        '</form>'
    )

    if not records:
        rows_html = '<tr><td colspan="14" style="text-align:center;color:#888;padding:24px">暂无记录</td></tr>'
    else:
        rows = []
        for r in records:
            ps        = r.get("proc_status", "")
            stage     = r.get("stage", "")
            proc_type = r.get("proc_type", "")
            chat_id   = r.get("chat_id") or ""
            extra_info = _html_mod.escape(r.get("extra_info") or "")
            info_cell = (
                '<button class="btn-info" data-info="' + extra_info
                + '" onclick="showInfo(this.dataset.info)">⚠ 查看</button>'
                if extra_info else "-"
            )
            aname = r.get("approval_name") or "-"
            fc    = _form_cell(r.get("form_json") or "")
            _jsattr = lambda s: _html_mod.escape(json.dumps(s, ensure_ascii=False))
            icode = r["instance_code"]
            if ps == "error":
                subj   = r.get("subject") or ""
                action = f'<button onclick="retryTask({_jsattr(icode)},{_jsattr(subj)})" class="btn-orange">重试</button>'
            elif proc_type == "group" and ps == "success" and not r.get("is_dissolved"):
                gname  = r.get("group_name") or chat_id
                action = f'<button onclick="dissolve({_jsattr(chat_id)},{_jsattr(gname)})" class="btn-red">解散</button>'
            elif r.get("is_dissolved"):
                action = '<span style="color:#aaa">已解散</span>'
            else:
                action = '<span style="color:#aaa">-</span>'
            rows.append(
                f"<tr>"
                f"<td>{r['id']}</td>"
                f"<td style='font-size:11px;color:#666'>{(r['instance_code'] or '')[:14]}…</td>"
                f"<td style='font-size:12px;color:#555'>{aname}</td>"
                f"<td>{r.get('subject') or '-'}</td>"
                f"<td>{_applicant_cell(r)}</td>"
                f"<td>{fc}</td>"
                f"<td>{_PROC_TYPE_LABELS.get(proc_type, proc_type or '-')}</td>"
                f"<td>{r.get('group_name') or '-'}</td>"
                f"<td>{_STAGE_LABELS.get(stage, stage or '-')}</td>"
                f"<td>{_status_badge(ps)}</td>"
                f"<td>{info_cell}</td>"
                f"<td>{r.get('created_at') or '-'}</td>"
                f"<td>{action}</td>"
                f"</tr>"
            )
        rows_html = "\n".join(rows)

    body = (
        search_form
        + '\n<div class="pager">' + pagination + '</div>\n'
        '<table>\n<thead><tr>\n'
        '  <th>#</th><th>实例 Code</th><th>审批名称</th><th>申请事项</th><th>申请人</th>\n'
        '  <th>表单</th><th>处理方式</th><th>群名</th><th>当前阶段</th><th>处理状态</th>\n'
        '  <th>处理信息</th><th>创建时间</th><th>操作</th>\n'
        '</tr></thead>\n'
        '<tbody>' + rows_html + '</tbody>\n'
        '</table>\n'
        '<div class="pager" style="margin-top:12px">' + pagination + '</div>\n'
    )
    return _page_shell("process-records", _build_token_html(), body, is_admin=is_admin, current_user=current_user)


def _render_check_page(cpage: int = 1, cpage_size: int = 20,
                       csubject: str = "", cname: str = "",
                       is_admin: bool = True, current_user: str = "") -> str:
    """渲染预检查记录页（/admin/precheck-records）。"""
    import urllib.parse as _up
    from services.db import list_check_tasks_paged, count_check_tasks

    c_total       = count_check_tasks(subject=csubject, name=cname)
    c_total_pages = max(1, (c_total + cpage_size - 1) // cpage_size)
    cpage         = max(1, min(cpage, c_total_pages))
    c_records     = list_check_tasks_paged(cpage, cpage_size, subject=csubject, name=cname)

    _qs_base = f"&cpage_size={cpage_size}"
    if csubject: _qs_base += f"&csubject={_up.quote(csubject)}"
    if cname:    _qs_base += f"&cname={_up.quote(cname)}"

    def _cplink(p, lbl):
        if p < 1 or p > c_total_pages:
            return f'<span style="color:#ccc;padding:4px 8px">{lbl}</span>'
        return (f'<a href="/admin/precheck-records?cpage={p}{_qs_base}" style="color:#4a90d9;text-decoration:none;'
                f'padding:4px 8px;border:1px solid #c9d1e0;border-radius:4px">{lbl}</a>')

    c_pagination = (
        f'{_cplink(cpage-1, "◄ 上一页")}'
        f'<span style="margin:0 12px;color:#555">第 {cpage} / {c_total_pages} 页（共 {c_total} 条）</span>'
        f'{_cplink(cpage+1, "下一页 ►")}'
    )

    def _esc(s): return s.replace('"', '&quot;').replace('<', '&lt;')
    _cinp     = 'style="border:1px solid #c9d1e0;border-radius:6px;padding:6px 10px;font-size:14px;height:36px"'
    _btn_blue = 'style="background:#1a73e8;color:#fff;border:none;padding:0 18px;height:36px;border-radius:6px;cursor:pointer;font-size:14px"'
    _btn_gray = 'style="background:#fff;color:#555;border:1px solid #c9d1e0;padding:0 14px;height:36px;border-radius:6px;cursor:pointer;font-size:14px;text-decoration:none;display:inline-flex;align-items:center"'
    _cps_opts = ''.join(
        f'<option value="{n}"' + (' selected' if n == cpage_size else '') + f'>{n} 条/页</option>'
        for n in [10, 20, 50, 100]
    )
    c_search_form = (
        '<form method="get" action="/admin/precheck-records" '
        'style="display:flex;gap:10px;align-items:center;margin-bottom:14px;flex-wrap:wrap">'
        f'<input name="cname" placeholder="申请人" value="{_esc(cname)}" {_cinp} style="width:140px;border:1px solid #c9d1e0;border-radius:6px;padding:6px 10px;font-size:14px;height:36px">'
        f'<input name="csubject" placeholder="申请事项" value="{_esc(csubject)}" {_cinp} style="width:180px;border:1px solid #c9d1e0;border-radius:6px;padding:6px 10px;font-size:14px;height:36px">'
        f'<select name="cpage_size" onchange="this.form.submit()" style="border:1px solid #c9d1e0;border-radius:6px;padding:0 8px;font-size:14px;height:36px;cursor:pointer">{_cps_opts}</select>'
        f'<button type="submit" {_btn_blue}>搜索</button>'
        f'<a href="/admin/precheck-records" {_btn_gray}>重置</a>'
        f'<button type="button" onclick="location.reload()" {_btn_gray}>刷新</button>'
        '</form>'
    )

    if not c_records:
        rows_html = '<tr><td colspan="13" style="text-align:center;color:#888;padding:24px">暂无记录</td></tr>'
    else:
        rows = []
        for r in c_records:
            cs = r.get("check_status", "")
            lbl, clr = _CHECK_STATUS_LABELS.get(cs, (cs or "-", "#888"))
            status_cell = f'<span style="color:{clr};font-weight:600">{lbl}</span>'
            reason = _html_mod.escape(r.get("check_reason") or "")
            reason_cell = (
                '<button class="btn-info" data-info="' + reason
                + '" onclick="showInfo(this.dataset.info)">查看</button>'
                if reason else "-"
            )
            extra = _html_mod.escape(r.get("extra_info") or "")
            extra_cell = (
                '<button class="btn-info" data-info="' + extra
                + '" onclick="showInfo(this.dataset.info)">⚠ 查看</button>'
                if extra else "-"
            )
            aname = r.get("approval_name") or "-"
            fc    = _form_cell(r.get("form_json") or "")
            _jsattr = lambda s: _html_mod.escape(json.dumps(s, ensure_ascii=False))
            icode = r["instance_code"]
            subj  = r.get("subject") or ""
            action = (
                f'<button onclick="retryCheckTask({_jsattr(icode)},{_jsattr(subj)})" class="btn-orange">重试</button>'
                if cs == "error" else '<span style="color:#aaa">-</span>'
            )
            rows.append(
                f"<tr>"
                f"<td>{r['id']}</td>"
                f"<td style='font-size:11px;color:#666'>{(r['instance_code'] or '')[:14]}…</td>"
                f"<td style='font-size:12px;color:#555'>{aname}</td>"
                f"<td>{r.get('subject') or '-'}</td>"
                f"<td>{fc}</td>"
                f"<td>{_applicant_cell(r)}</td>"
                f"<td style='font-size:11px;color:#666'>{r.get('task_id') or '-'}</td>"
                f"<td>{_CHECK_STAGE_LABELS.get(r.get('stage',''), r.get('stage','-'))}</td>"
                f"<td>{status_cell}</td>"
                f"<td>{reason_cell}</td>"
                f"<td>{extra_cell}</td>"
                f"<td>{r.get('created_at') or '-'}</td>"
                f"<td>{action}</td>"
                f"</tr>"
            )
        rows_html = "\n".join(rows)

    body = (
        c_search_form
        + '\n<div class="pager">' + c_pagination + '</div>\n'
        '<table>\n<thead><tr>\n'
        '  <th>#</th><th>实例 Code</th><th>审批名称</th><th>申请事项</th><th>表单</th><th>申请人</th>\n'
        '  <th>节点 Task ID</th><th>当前阶段</th><th>检查状态</th>\n'
        '  <th>检查原因</th><th>错误信息</th><th>创建时间</th><th>操作</th>\n'
        '</tr></thead>\n'
        '<tbody>' + rows_html + '</tbody>\n'
        '</table>\n'
        '<div class="pager" style="margin-top:12px">' + c_pagination + '</div>\n'
    )
    return _page_shell("precheck-records", _build_token_html(), body, is_admin=is_admin, current_user=current_user)


# ---------------------------------------------------------------------------
# 系统配置页
# ---------------------------------------------------------------------------

def _render_settings_page(current_user: str = "") -> str:
    """渲染系统配置页（/admin/settings）。"""
    from config import CONFIG_META
    from services.db import get_setting
    import os as _os

    # 这两项是逗号分隔的多值字段，用 textarea 展示更易编辑
    _TEXTAREA_KEYS = {"WORKER_USER_IDS", "APPROVAL_CODES"}

    # 分组标题映射: key -> 所属分组
    _SECTION_OF = {
        'APP_ID': '飞书应用配置', 'APP_SECRET': '飞书应用配置',
        'REDIRECT_URI': '飞书应用配置', 'FEISHU_HOST': '飞书应用配置',
        'APPROVAL_CODES': '飞书审批配置', 'PRE_CHECK_NODE_NAME': '飞书审批配置',
        'WORKER_BOT_APP_ID': '飞书群配置', 'WORKER_BOT_APP_SECRET': '飞书群配置',
        'WORKER_USER_IDS': '飞书群配置', 'WORKER_ADMIN_ID': '飞书群配置',
        'WORKER_BOT_ADMIN_ID': '飞书群配置',
        'GROUP_TTL_DAYS': '飞书群配置',
        'ALERT_WEBHOOK': '运维配置',
    }
    rows = []
    _last_section = None
    for key, desc, is_secret in CONFIG_META:
        section = _SECTION_OF.get(key, '')
        if section and section != _last_section:
            rows.append(
                f'<tr><td colspan="4" style="background:#f0f4ff;font-weight:700;'
                f'font-size:12px;color:#1a73e8;padding:8px 12px;border-top:2px solid #dce8ff">'
                f'{section}</td></tr>'
            )
            _last_section = section
        db_val = get_setting(f"config:{key}")
        env_val = _os.environ.get(key, "")
        current = db_val if db_val is not None else env_val
        source = "数据库" if db_val is not None else (".env" if env_val else "默认")
        esc_val = current.replace('"', "&quot;").replace("<", "&lt;")
        if key in _TEXTAREA_KEYS:
            field_html = (
                f'<textarea name="{key}" rows="3" '
                f'style="width:100%;border:1px solid #c9d1e0;border-radius:4px;'
                f'padding:4px 8px;font-size:13px;font-family:monospace;resize:vertical">'
                f'{esc_val}</textarea>'
                f'<div style="font-size:11px;color:#aaa;margin-top:2px">多个值用英文逗号分隔</div>'
            )
        elif is_secret:
            # 显示脱敏掩码；value 仍存真实值，type=password 让浏览器掩码显示
            # 用户若不修改，JS 提交时跳过此字段（值与 data-orig 相同则不提交）
            field_html = (
                f'<input type="password" name="{key}" value="{esc_val}" '
                f'data-orig="{esc_val}" data-secret="1" '
                f'style="width:100%;border:1px solid #c9d1e0;border-radius:4px;padding:4px 8px;font-size:13px;height:36px" '
                f'autocomplete="new-password">'
            )
        else:
            field_html = (
                f'<input type="text" name="{key}" value="{esc_val}" '
                f'style="width:100%;border:1px solid #c9d1e0;border-radius:4px;padding:4px 8px;font-size:13px;height:36px">'
            )
        rows.append(
            f'<tr>'
            f'<td style="font-weight:600;white-space:nowrap;font-size:13px">{key}</td>'
            f'<td style="color:#555;font-size:12px;line-height:1.6">{desc}</td>'
            f'<td>{field_html}</td>'
            f'<td style="color:#888;font-size:12px;white-space:nowrap">{source}</td>'
            f'</tr>'
        )

    missing_bootstrap = get_missing_configs(["APP_ID", "APP_SECRET", "REDIRECT_URI"])
    notice_html = ""
    if missing_bootstrap:
        notice_html = (
            '<div class="notice-warn">'
            '当前缺少主应用启动配置：<b>' + ", ".join(missing_bootstrap) + '</b>。'
            '服务现在仍可启动并打开管理后台，但不会连接飞书、不会接收审批事件，/auth 也暂不可用。'
            '请先在本页补齐配置，再点击“保存并重启”。'
            '</div>'
        )

    body = (
        notice_html +
        '<form id="settingsForm" style="margin-bottom:20px">'
        '<table><thead><tr>'
        '<th style="width:160px">配置键</th><th>说明</th><th style="width:420px">配置值</th><th style="width:60px">来源</th>'
        '</tr></thead><tbody>'
        + "\n".join(rows)
        + '</tbody></table>'
        '<div style="margin-top:16px;display:flex;gap:12px">'
        '<button type="button" onclick="saveSettings()" '
        'style="background:#1a73e8;color:#fff;border:none;padding:8px 24px;border-radius:6px;cursor:pointer;font-size:14px">'
        '保存配置</button>'
        '<button type="button" onclick="saveAndRestart()" '
        'style="background:#e37400;color:#fff;border:none;padding:8px 24px;border-radius:6px;cursor:pointer;font-size:14px">'
        '保存并重启</button>'
        '</div>'
        '</form>'
        '<script>\n'
        'function _collectSettings(){\n'
        '  const form = document.getElementById("settingsForm");\n'
        '  const data = {};\n'
        '  form.querySelectorAll("input[name],textarea[name]").forEach(el => {\n'
        '    if(el.dataset.secret==="1" && el.value===el.dataset.orig) return;\n'
        '    data[el.name] = el.value;\n'
        '  });\n'
        '  return data;\n'
        '}\n'
        'async function saveSettings() {\n'
        '  const data = _collectSettings();\n'
        '  const r = await fetch("/api/settings/save", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(data)});\n'
        '  const j = await r.json();\n'
        '  if(j.ok) alert("配置已保存"); else alert("保存失败: " + j.error);\n'
        '}\n'
        'async function saveAndRestart() {\n'
        '  const data = _collectSettings();\n'
        '  const r = await fetch("/api/settings/save", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(data)});\n'
        '  const j = await r.json();\n'
        '  if(!j.ok){ alert("保存失败: " + j.error); return; }\n'
        '  if(!confirm("配置已保存。确认重启服务？")) return;\n'
        '  fetch("/api/restart", {method:"POST"}).catch(()=>{});\n'
        '  alert("服务正在重启，请等待几秒后刷新页面……");\n'
        '  setTimeout(()=>location.reload(), 3000);\n'
        '}\n'
        '</script>'
    )
    return _page_shell("settings", _build_token_html(), body, current_user=current_user)


# ---------------------------------------------------------------------------
# 环境变量管理页
# ---------------------------------------------------------------------------

def _render_envvars_page(is_admin: bool = True, current_user: str = "") -> str:
    """渲染脚本环境变量管理页（/admin/envvars）。"""
    from services.db import list_script_envvars

    records = list_script_envvars()

    def _esc(s: str) -> str:
        return s.replace('&', '&amp;').replace('<', '&lt;').replace('"', '&quot;')

    def _mask(v: str) -> str:
        if not v:
            return '<span style="color:#ccc">（空）</span>'
        visible = v[:2] if len(v) > 4 else v[:1]
        return _esc(visible) + '•' * min(len(v) - len(visible), 12)

    if records:
        def _ev_row(r: dict) -> str:
            k = _esc(r["key"]); d = _esc(r["desc"])
            rk = repr(r["key"]); rd = repr(r["desc"]); rv = repr(r["value"])
            return (
                f'<tr>'
                f'<td style="font-weight:600;font-family:monospace">{k}</td>'
                f'<td style="color:#555;font-size:13px">{d}</td>'
                f'<td style="font-family:monospace;color:#555">{_mask(r["value"])}</td>'
                f'<td style="font-size:12px;color:#888">{r.get("updated_at","")}</td>'
                f'<td style="white-space:nowrap">'
                f'<button class="btn-orange" onclick="editEnvvar({rk},{rd})">编辑</button> '
                f'<button class="btn-red" onclick="delEnvvar({rk})">删除</button>'
                f'</td></tr>'
            )
        rows_html = "\n".join(_ev_row(r) for r in records)
    else:
        rows_html = '<tr><td colspan="5" style="text-align:center;color:#888;padding:24px">暂无环境变量，点击「新增」添加</td></tr>'

    body = (
        '<div style="background:#fffbe6;border:1px solid #ffe58f;border-radius:8px;'
        'padding:12px 16px;font-size:13px;color:#7d5a00;margin-bottom:16px;line-height:1.8">'
        '在此配置的变量会注入到脚本的 <code>ENV</code> 字典中，脚本通过 <code>ENV.get("KEY")</code> 读取。'
        ''
        '</div>'

        '<div style="margin-bottom:12px">'
        '<button onclick="editEnvvar(\'\',\'\')" '
        'style="background:#1a73e8;color:#fff;border:none;padding:7px 20px;border-radius:6px;cursor:pointer;font-size:14px">'
        '+ 新增环境变量</button>'
        '</div>'

        '<table style="table-layout:fixed">\n<thead><tr>'
        '<th style="width:200px">变量名</th>'
        '<th style="width:220px">说明</th>'
        '<th style="width:200px">值</th>'
        '<th style="width:160px">更新时间</th>'
        '<th style="width:110px">操作</th>'
        '</tr></thead>\n'
        '<tbody>' + rows_html + '</tbody>\n</table>\n'

        # ── 弹窗 ──────────────────────────────────────────────────────────────
        '<div id="evModal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:999;align-items:center;justify-content:center">'
        '  <div style="background:#fff;border-radius:10px;padding:28px 32px;min-width:420px;max-width:560px;box-shadow:0 8px 32px rgba(0,0,0,.18)">'
        '    <h3 id="evTitle" style="margin:0 0 18px;font-size:16px;color:#1d2129">新增环境变量</h3>'
        '    <div id="evKeySection" style="margin-bottom:12px">'
        '      <label style="font-size:13px;font-weight:600;display:block;margin-bottom:4px">变量名 <span style="color:#d93025">*</span></label>'
        '      <input id="evKey" type="text" placeholder="如 VOLCENGINE_AK" '
        '        style="width:100%;box-sizing:border-box;border:1px solid #c9d1e0;border-radius:6px;padding:7px 10px;font-size:14px;font-family:monospace">'
        '    </div>'
        '    <div id="evDescSection" style="margin-bottom:12px">'
        '      <label style="font-size:13px;font-weight:600;display:block;margin-bottom:4px">说明</label>'
        '      <input id="evDesc" type="text" placeholder="简要说明此变量用途" '
        '        style="width:100%;box-sizing:border-box;border:1px solid #c9d1e0;border-radius:6px;padding:7px 10px;font-size:14px">'
        '    </div>'
        '    <div id="evEditLabel" style="display:none;margin-bottom:12px;padding:8px 12px;background:#f5f7ff;border-radius:6px;font-size:13px;color:#1d2129">'
        '      <span style="color:#888">变量：</span><span id="evEditLabelKey" style="font-family:monospace;font-weight:600"></span>'
        '    </div>'
        '    <div style="margin-bottom:20px">'
        '      <label style="font-size:13px;font-weight:600;display:block;margin-bottom:4px">值 <span style="color:#d93025">*</span></label>'
        '      <input id="evVal" type="text" placeholder="新建时输入实际值；编辑时留空则不修改" autocomplete="off" '
        '        style="width:100%;box-sizing:border-box;border:1px solid #c9d1e0;border-radius:6px;padding:7px 10px;font-size:14px;font-family:monospace">'
        '    </div>'
        '    <div style="display:flex;gap:10px;justify-content:flex-end">'
        '      <button onclick="closeEvModal()" style="padding:7px 20px;border:1px solid #c9d1e0;border-radius:6px;cursor:pointer;background:#fff">取消</button>'
        '      <button onclick="saveEnvvar()" style="padding:7px 20px;background:#1a73e8;color:#fff;border:none;border-radius:6px;cursor:pointer">保存</button>'
        '    </div>'
        '  </div>'
        '</div>'

        '<script>\n'
        'var _evOrigKey="";\n'
        'function editEnvvar(k,d){\n'
        '  _evOrigKey=k;\n'
        '  document.getElementById("evTitle").textContent=k?"编辑环境变量":"新增环境变量";\n'
        '  var editing=!!k;\n'
        '  document.getElementById("evKeySection").style.display=editing?"none":"block";\n'
        '  document.getElementById("evDescSection").style.display=editing?"none":"block";\n'
        '  document.getElementById("evEditLabel").style.display=editing?"block":"none";\n'
        '  document.getElementById("evEditLabelKey").textContent=k;\n'
        '  document.getElementById("evKey").value=k;\n'
        '  document.getElementById("evDesc").value=d;\n'
        '  document.getElementById("evVal").value="";\n'
        '  document.getElementById("evVal").placeholder=k?"输入新值（留空则不修改）":"输入实际值";\n'
        '  document.getElementById("evVal").focus();\n'
        '  var m=document.getElementById("evModal");\n'
        '  m.style.display="flex";\n'
        '}\n'
        'function closeEvModal(){\n'
        '  document.getElementById("evModal").style.display="none";\n'
        '}\n'
        'async function saveEnvvar(){\n'
        '  var k=document.getElementById("evKey").value.trim();\n'
        '  var d=document.getElementById("evDesc").value.trim();\n'
        '  var v=document.getElementById("evVal").value;\n'
        '  if(!k){alert("变量名不能为空");return;}\n'
        '  if(!_evOrigKey && !v){alert("新增时值不能为空");return;}\n'
        '  var payload={key:k,desc:d};\n'
        '  if(v) payload.value=v;\n'
        '  var endpoint=_evOrigKey?"/api/envvars/edit":"/api/envvars/create";\n'
        '  var r=await fetch(endpoint,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});\n'
        '  var j=await r.json();\n'
        '  if(j.ok){closeEvModal();location.reload();}else{alert("保存失败: "+j.error);}\n'
        '}\n'
        'async function delEnvvar(k){\n'
        '  if(!confirm("确认删除环境变量 "+k+" ？")) return;\n'
        '  var r=await fetch("/api/envvars/delete",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({key:k})});\n'
        '  var j=await r.json();\n'
        '  if(j.ok){location.reload();}else{alert("删除失败: "+j.error);}\n'
        '}\n'
        'document.getElementById("evModal").addEventListener("click",function(e){if(e.target===this)closeEvModal();});\n'
        '</script>\n'
    )
    return _page_shell("envvars", _build_token_html(), body, is_admin=is_admin, current_user=current_user)


# ---------------------------------------------------------------------------
# 操作日志页
# ---------------------------------------------------------------------------

def _render_logs_page(lpage: int = 1, lpage_size: int = 50,
                      lusername: str = "", laction: str = "",
                      current_user: str = "") -> str:
    """渲染管理员操作日志页（/admin/logs）。"""
    import urllib.parse as _up
    from services.db import list_admin_logs_paged, count_admin_logs

    total       = count_admin_logs(username=lusername, action=laction)
    total_pages = max(1, (total + lpage_size - 1) // lpage_size)
    lpage       = max(1, min(lpage, total_pages))
    records     = list_admin_logs_paged(lpage, lpage_size, username=lusername, action=laction)

    _qs_base = ""
    if lusername: _qs_base += f"&lusername={_up.quote(lusername)}"
    if laction:   _qs_base += f"&laction={_up.quote(laction)}"
    if lpage_size != 50: _qs_base += f"&lpage_size={lpage_size}"

    def _plink(p, lbl):
        if p < 1 or p > total_pages:
            return f'<span style="color:#ccc;padding:4px 8px">{lbl}</span>'
        return (f'<a href="/admin/logs?lpage={p}{_qs_base}" '
                f'style="color:#4a90d9;text-decoration:none;'
                f'padding:4px 8px;border:1px solid #c9d1e0;border-radius:4px">{lbl}</a>')

    pagination = (
        f'{_plink(lpage - 1, "◄ 上一页")}'
        f'<span style="margin:0 12px;color:#555">第 {lpage} / {total_pages} 页（共 {total} 条）</span>'
        f'{_plink(lpage + 1, "下一页 ►")}'
    )

    def _esc(s: str) -> str:
        return s.replace('&', '&amp;').replace('<', '&lt;').replace('"', '&quot;')

    _inp      = 'style="border:1px solid #c9d1e0;border-radius:6px;padding:6px 10px;font-size:14px;height:36px"'
    _btn_blue = 'style="background:#1a73e8;color:#fff;border:none;padding:0 18px;height:36px;border-radius:6px;cursor:pointer;font-size:14px"'
    _btn_gray = ('style="background:#fff;color:#555;border:1px solid #c9d1e0;padding:0 14px;height:36px;'
                 'border-radius:6px;cursor:pointer;font-size:14px;text-decoration:none;'
                 'display:inline-flex;align-items:center"')
    _ps_opts  = ''.join(
        f'<option value="{n}"' + (' selected' if n == lpage_size else '') + f'>{n} 条/页</option>'
        for n in [20, 50, 100, 200]
    )
    search_form = (
        '<form method="get" action="/admin/logs" '
        'style="display:flex;gap:10px;align-items:center;margin-bottom:14px;flex-wrap:wrap">'
        f'<input name="lusername" placeholder="用户名" value="{_esc(lusername)}" {_inp} '
        f'style="width:140px;border:1px solid #c9d1e0;border-radius:6px;padding:6px 10px;font-size:14px;height:36px">'
        f'<input name="laction" placeholder="操作类型" value="{_esc(laction)}" {_inp} '
        f'style="width:160px;border:1px solid #c9d1e0;border-radius:6px;padding:6px 10px;font-size:14px;height:36px">'
        f'<select name="lpage_size" onchange="this.form.submit()" '
        f'style="border:1px solid #c9d1e0;border-radius:6px;padding:0 8px;font-size:14px;height:36px;cursor:pointer">'
        f'{_ps_opts}</select>'
        f'<button type="submit" {_btn_blue}>搜索</button>'
        f'<a href="/admin/logs" {_btn_gray}>重置</a>'
        f'<button type="button" onclick="location.reload()" {_btn_gray}>刷新</button>'
        '</form>'
    )

    if not records:
        rows_html = '<tr><td colspan="6" style="text-align:center;color:#888;padding:24px">暂无记录</td></tr>'
    else:
        rows_html = "\n".join(
            "<tr>"
            f"<td>{r['id']}</td>"
            f"<td style='font-weight:600'>{_esc(r.get('username') or '-')}</td>"
            f"<td style='color:#666;font-size:12px'>{_esc(r.get('ip') or '-')}</td>"
            f"<td style='font-size:12px'>{_esc(r.get('action') or '-')}</td>"
            f"<td style='font-size:12px;color:#444;max-width:420px;word-break:break-all'>"
            f"{_esc(r.get('detail') or '-')}</td>"
            f"<td style='font-size:12px;white-space:nowrap'>{r.get('created_at') or '-'}</td>"
            "</tr>"
            for r in records
        )

    body = (
        search_form
        + f'\n<div class="pager">{pagination}</div>\n'
        '<table>\n<thead><tr>\n'
        '  <th>#</th><th>用户名</th><th>来源 IP</th><th>操作类型</th><th>详情</th><th>时间</th>\n'
        '</tr></thead>\n'
        '<tbody>' + rows_html + '</tbody>\n'
        '</table>\n'
        f'<div class="pager" style="margin-top:12px">{pagination}</div>\n'
    )
    return _page_shell("logs", _build_token_html(), body, is_admin=True, current_user=current_user)


# ---------------------------------------------------------------------------
# 脚本管理页（预检查 / 处理 共用模板）
# ---------------------------------------------------------------------------

def _render_about_page(is_admin: bool = True, current_user: str = "") -> str:
    """渲染系统介绍页（/admin/about）。"""
    body = (
        '<div style="max-width:940px">'

        # ── 系统标题 ──────────────────────────────────────────────────────────
        '<h2 style="font-size:18px;color:#1d2129;margin:0 0 4px">飞书审批Claw</h2>'
        '<p style="color:#666;font-size:13px;line-height:1.8;margin:0 0 24px">'
        '通过 WebSocket 长连接实时监听飞书审批事件，自动完成'
        '<b>预检查 → 审批通过 → 建处理群 → @Openclaw Bot 自动办理 或 低代码脚本处理</b>的全链路审批自动化。'
        '</p>'

        # ── 核心设计：Openclaw 对接 ───────────────────────────────────────────
        '<h3 style="font-size:15px;color:#1a73e8;border-left:3px solid #1a73e8;'
        'padding-left:10px;margin:0 0 12px">核心设计：审批 → 处理群 → Openclaw Bot 自动处理</h3>'
        '<div style="background:#f7f9ff;border:1px solid #dce8ff;border-radius:8px;'
        'padding:16px 20px;font-size:13px;line-height:2.2;margin-bottom:16px;font-family:monospace">'
        '用户在飞书提交审批<br>'
        '&nbsp;&nbsp;&nbsp;&nbsp;↓ 到达「预检查」节点<br>'
        '&nbsp;&nbsp;&nbsp;&nbsp;↓ <b>自动执行预检查脚本</b> → 通过则继续，不通过则自动退回<br>'
        '&nbsp;&nbsp;&nbsp;&nbsp;↓ 审批最终通过<br>'
        '&nbsp;&nbsp;&nbsp;&nbsp;↓ 匹配「申请事项」对应的处理脚本<br>'
        '&nbsp;&nbsp;&nbsp;&nbsp;├─ 有处理脚本 → <b>低代码脚本处理</b>（可对接 n8n / Dify 等工作流）<br>'
        '&nbsp;&nbsp;&nbsp;&nbsp;└─ 无处理脚本 → <b>自动建群 + 拉人 + @Openclaw Bot</b><br>'
        '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'
        '↓ Openclaw Bot 识别 @ 消息 → 匹配 Skill → 自动执行处理任务'
        '</div>'

        # ── Openclaw Bot 对接说明 ─────────────────────────────────────────────
        '<h3 style="font-size:15px;color:#1a73e8;border-left:3px solid #1a73e8;'
        'padding-left:10px;margin:0 0 12px">Openclaw Bot 对接说明</h3>'
        '<div style="background:#fffbe6;border:1px solid #ffe58f;border-radius:8px;'
        'padding:14px 18px;font-size:13px;line-height:1.9;margin-bottom:16px">'
        '<b>⚠️ 前提：Openclaw Bot 需要提前训练好对应的 Skills</b><br>'
        '审批通过后，系统会自动创建飞书群并将 <b>Openclaw Bot</b>（WORKER_BOT_APP_ID 对应的机器人）'
        '拉入群组，然后发送结构化的 @提及消息（包含申请人、申请事项、表单字段），'
        'Openclaw Bot 收到 @消息后，依据预训练的 Skill 自动解析并处理申请。'
        '<br><br>'
        '要使对接正常工作，Openclaw 侧需要提前完成以下配置：'
        '</div>'
        '<table style="border-collapse:collapse;width:100%;margin-bottom:20px">'
        '<tr>'
        '<th style="background:#f0f4ff;color:#1d2129;padding:8px 12px;text-align:left;font-size:13px;'
        'border:1px solid #dce8ff;width:200px">配置项</th>'
        '<th style="background:#f0f4ff;color:#1d2129;padding:8px 12px;text-align:left;font-size:13px;'
        'border:1px solid #dce8ff">说明</th>'
        '</tr>'
        '<tr><td style="padding:8px 12px;border:1px solid #eee;font-weight:600">训练 Skill</td>'
        '<td style="padding:8px 12px;border:1px solid #eee;font-size:13px;color:#444">'
        '针对每种「申请事项」（如：开通 VPN、申请数据库权限等），在 Openclaw 中预先训练'
        '对应的 Skill，并使其能够识别本系统发送的消息格式（包含申请人姓名、申请事项关键词、所需参数）。'
        '</td></tr>'
        '<tr><td style="padding:8px 12px;border:1px solid #eee;font-weight:600">消息格式约定</td>'
        '<td style="padding:8px 12px;border:1px solid #eee;font-size:13px;color:#444">'
        '系统向群发送的 @ 消息格式固定，包含：<code>申请人</code>（姓名+open_id）、'
        '<code>申请事项</code>（审批表单中的事项字段值）、<code>表单字段</code>（所有 k/v 对）。'
        'Openclaw 的 Skill 应按此格式设计触发条件和参数提取规则。'
        '</td></tr>'
        '<tr><td style="padding:8px 12px;border:1px solid #eee;font-weight:600">Bot 需在群内</td>'
        '<td style="padding:8px 12px;border:1px solid #eee;font-size:13px;color:#444">'
        'WORKER_BOT_APP_ID 填写的应用必须已添加"机器人"能力，且机器人已被授权加入企业内部群。'
        '系统通过其 open_id 将其拉入处理群后发送 @消息，Openclaw 才能收到并触发 Skill。'
        '</td></tr>'
        '<tr><td style="padding:8px 12px;border:1px solid #eee;font-weight:600">人工兜底</td>'
        '<td style="padding:8px 12px;border:1px solid #eee;font-size:13px;color:#444">'
        'WORKER_USER_IDS 中的处理人也会被拉入群，作为人工监督和兜底处理。'
        '若 Openclaw Skill 无法匹配或执行失败，处理人可直接在群内手动处理并关闭申请。'
        '</td></tr>'
        '</table>'

        # ── 核心功能 ──────────────────────────────────────────────────────────
        '<h3 style="font-size:15px;color:#1a73e8;border-left:3px solid #1a73e8;'
        'padding-left:10px;margin:0 0 12px">功能模块</h3>'
        '<table style="border-collapse:collapse;width:100%;margin-bottom:20px">'
        '<tr><th style="background:#f0f4ff;color:#1d2129;padding:8px 12px;text-align:left;font-size:13px;'
        'border:1px solid #dce8ff;width:160px">模块</th>'
        '<th style="background:#f0f4ff;color:#1d2129;padding:8px 12px;text-align:left;font-size:13px;'
        'border:1px solid #dce8ff">说明</th></tr>'
        '<tr><td style="padding:8px 12px;border:1px solid #eee;font-weight:600">预检查自动化</td>'
        '<td style="padding:8px 12px;border:1px solid #eee;font-size:13px;color:#444">'
        '审批流到达「预检查」节点时，自动执行对应脚本，返回 <code>(True, 原因)</code> 自动通过，'
        '<code>(False, 原因)</code> 自动退回，无需人工介入。</td></tr>'
        '<tr><td style="padding:8px 12px;border:1px solid #eee;font-weight:600">处理群创建</td>'
        '<td style="padding:8px 12px;border:1px solid #eee;font-size:13px;color:#444">'
        '审批通过且无对应处理脚本时，自动创建飞书处理群、拉入处理人和 Openclaw Bot、'
        '发送申请通知并 @机器人，触发自动处理流程。</td></tr>'
        '<tr><td style="padding:8px 12px;border:1px solid #eee;font-weight:600">低代码处理脚本</td>'
        '<td style="padding:8px 12px;border:1px solid #eee;font-size:13px;color:#444">'
        '按「申请事项」匹配处理脚本，有脚本则执行 <code>run(applicant, form)</code>，'
        '优先于默认建群逻辑。几行 Python 即可对接 n8n、Dify 等外部工作流平台或调用任意 API。</td></tr>'
        '<tr><td style="padding:8px 12px;border:1px solid #eee;font-weight:600">脚本在线编辑</td>'
        '<td style="padding:8px 12px;border:1px solid #eee;font-size:13px;color:#444">'
        '后台直接新增/编辑 Python 脚本，支持语法高亮、实时传参调试，结果即时展示。'
        '脚本内可直接 <code>import requests</code> 调用外部 API，零门槛对接第三方系统。</td></tr>'
        '<tr><td style="padding:8px 12px;border:1px solid #eee;font-weight:600">环境变量管理</td>'
        '<td style="padding:8px 12px;border:1px solid #eee;font-size:13px;color:#444">'
        '在后台「<a href="/admin/envvars" style="color:#1a73e8">环境变量</a>」Tab 中配置 KV，'
        '脚本执行时自动注入为 <code>ENV</code> 字典，适合集中管理 API 密钥、账号等敏感参数。</td></tr>'
        '<tr><td style="padding:8px 12px;border:1px solid #eee;font-weight:600">操作记录</td>'
        '<td style="padding:8px 12px;border:1px solid #eee;font-size:13px;color:#444">'
        '所有管理操作（新增/编辑/删除脚本、保存配置、重启等）自动写入审计日志，记录操作人、来源 IP 和时间。</td></tr>'
        '<tr><td style="padding:8px 12px;border:1px solid #eee;font-weight:600">配置热更新</td>'
        '<td style="padding:8px 12px;border:1px solid #eee;font-size:13px;color:#444">'
        '所有配置均可在后台修改，「保存并重启」一键生效；配置优先级：数据库 > .env > 默认值。</td></tr>'
        '</table>'

        # ── 系统架构 ──────────────────────────────────────────────────────────
        '<h3 style="font-size:15px;color:#1a73e8;border-left:3px solid #1a73e8;'
        'padding-left:10px;margin:0 0 12px">系统架构</h3>'
        '<div style="background:#f7f9ff;border:1px solid #dce8ff;border-radius:8px;'
        'padding:14px 18px;font-size:13px;line-height:2;margin-bottom:20px;font-family:monospace">'
        '飞书审批平台<br>'
        '&nbsp;&nbsp;&nbsp;&nbsp;↓ WebSocket 长连接（approval_instance P1 事件，无需公网回调）<br>'
        'main.py — 入口：初始化各组件、订阅审批事件、启动 WebSocket + HTTP 服务<br>'
        '│<br>'
        '├─ handlers/ — 审批事件处理<br>'
        '│&nbsp;&nbsp;&nbsp;&nbsp;├─ approval.py — 事件路由（分发预检查 / 处理流程）<br>'
        '│&nbsp;&nbsp;&nbsp;&nbsp;├─ precheck.py — 预检查节点：执行脚本 → 自动通过/退回<br>'
        '│&nbsp;&nbsp;&nbsp;&nbsp;└─ process.py — 审批通过：执行脚本 或 建群 + @Openclaw Bot<br>'
        '│<br>'
        '├─ services/ — 基础服务层<br>'
        '│&nbsp;&nbsp;&nbsp;&nbsp;├─ db.py — SQLite 数据层（WAL 模式，7 张表）<br>'
        '│&nbsp;&nbsp;&nbsp;&nbsp;├─ chat.py — 飞书 IM（建群 / 拉人 / @Bot / 解散群）<br>'
        '│&nbsp;&nbsp;&nbsp;&nbsp;├─ approval.py — 审批实例详情拉取 + 表单解析<br>'
        '│&nbsp;&nbsp;&nbsp;&nbsp;├─ user_token.py — 用户 OAuth token（持久化 + 自动刷新 + 线程安全）<br>'
        '│&nbsp;&nbsp;&nbsp;&nbsp;├─ user_profile.py — 用户资料查询（email/手机号 → open_id 解析）<br>'
        '│&nbsp;&nbsp;&nbsp;&nbsp;├─ lark_client.py — 主应用 lark.Client 单例<br>'
        '│&nbsp;&nbsp;&nbsp;&nbsp;├─ worker_bot.py — Openclaw Bot lark.Client 单例 + bot open_id<br>'
        '│&nbsp;&nbsp;&nbsp;&nbsp;└─ notify.py — 飞书消息发送（脚本内可调用）<br>'
        '│<br>'
        '├─ web/server.py — 管理后台 HTTP 服务（FastAPI + uvicorn）<br>'
        '│&nbsp;&nbsp;&nbsp;&nbsp;├─ /admin 路由（8 个 Tab）<br>'
        '│&nbsp;&nbsp;&nbsp;&nbsp;└─ /auth + /callback — 飞书 OAuth 2.0 授权<br>'
        '│<br>'
        '├─ scheduler/ — 后台定时任务<br>'
        '│&nbsp;&nbsp;&nbsp;&nbsp;├─ 群 TTL 清理（每小时） — 解散超期处理群<br>'
        '│&nbsp;&nbsp;&nbsp;&nbsp;└─ Token 巡检（每 10 分钟） — access_token 剩余 &lt; 30 分钟自动 refresh<br>'
        '│<br>'
        '└─ data/ — 数据持久化（SQLite，Docker 挂载）'
        '</div>'

        # ── 脚本编写规范 ──────────────────────────────────────────────────────
        '<h3 style="font-size:15px;color:#1a73e8;border-left:3px solid #1a73e8;'
        'padding-left:10px;margin:0 0 12px">脚本编写规范</h3>'
        '<table style="border-collapse:collapse;width:100%;margin-bottom:20px">'
        '<tr><th style="background:#f0f4ff;color:#1d2129;padding:8px 12px;text-align:left;font-size:13px;'
        'border:1px solid #dce8ff;width:160px">脚本类型</th>'
        '<th style="background:#f0f4ff;color:#1d2129;padding:8px 12px;text-align:left;font-size:13px;'
        'border:1px solid #dce8ff">触发时机 / 接口规范</th></tr>'
        '<tr><td style="padding:8px 12px;border:1px solid #eee;font-weight:600">预检查脚本</td>'
        '<td style="padding:8px 12px;border:1px solid #eee;font-size:13px;color:#444">'
        '<b>触发</b>：审批流到达 PRE_CHECK_NODE_NAME 同名节点时执行。<br>'
        '<b>接口</b>：<code>def check(applicant: dict, form: dict) -> tuple[bool, str]</code>'
        '</td></tr>'
        '<tr><td style="padding:8px 12px;border:1px solid #eee;font-weight:600">处理脚本</td>'
        '<td style="padding:8px 12px;border:1px solid #eee;font-size:13px;color:#444">'
        '<b>触发</b>：审批通过后，「申请事项」与脚本名称完全匹配时执行，优先于默认建群逻辑。<br>'
        '<b>接口</b>：<code>def run(applicant: dict, form: dict) -> None</code>'
        '</td></tr>'
        '</table>'

        # ── 首次使用 ──────────────────────────────────────────────────────────
        + (
        '<h3 style="font-size:15px;color:#1a73e8;border-left:3px solid #1a73e8;'
        'padding-left:10px;margin:0 0 12px">首次使用向导（管理员）</h3>'
        '<ol style="font-size:13px;line-height:2.2;color:#444;margin:0 0 20px;padding-left:20px">'
        '<li>在飞书开发者后台创建主应用，开通所需权限，订阅 approval_instance 事件。</li>'
        '<li>在 Openclaw 中为各类申请事项训练好对应 Skill，约定好本系统的消息格式。</li>'
        '<li>在「系统配置」填写 APP_ID / APP_SECRET / WORKER_BOT_APP_ID 等，点击「保存并重启」。</li>'
        '<li>访问 <a href="/auth" style="color:#1a73e8">/auth</a> 完成飞书 OAuth 授权，获取用户级 token。</li>'
        '<li>在飞书审批后台配置审批流（含预检查节点），将 code 填入 APPROVAL_CODES。</li>'
        '<li>（可选）在「<a href="/admin/envvars" style="color:#1a73e8">环境变量</a>」Tab 中添加脚本所需的密钥/参数，'
        '脚本执行时通过 <code>ENV.get("KEY", "")</code> 读取，无需硬编码。</li>'
        '<li>（可选）在「自定义处理脚本」或「自定义预检查脚本」中编写 Python 脚本，实现自动化处理逻辑。</li>'
        '<li>发起测试审批，在「预检查记录」和「处理记录」中观察执行结果；若出错可点击「重试」。</li>'
        '</ol>'
        if is_admin else
        '<h3 style="font-size:15px;color:#1a73e8;border-left:3px solid #1a73e8;'
        'padding-left:10px;margin:0 0 12px">新增申请事项向导（配置用户）</h3>'
        '<ol style="font-size:13px;line-height:2.2;color:#444;margin:0 0 20px;padding-left:20px">'
        '<li>在飞书审批后台确认目标审批表单中「申请事项」字段的<b>精确取值</b>，如果没有「申请事项」字段，则将审批名称作为「申请事项」的取值（可在「处理记录」或「预检查记录」的申请事项列查看已有样本）。</li>'
        '<li>进入「<a href="/admin/precheck-scripts" style="color:#1a73e8">自定义预检查脚本</a>」，点击「新建」，脚本名称填写上一步确认的取值（必须完全一致）。</li>'
        '<li>在编辑器中实现 <code>def check(applicant, form) -> tuple[bool, str]</code>，'
        '通过返回 <code>(True, "")</code>，拒绝返回 <code>(False, "退回原因")</code>，保存。</li>'
        '<li>（可选）在「调用参数」区填入测试用的 applicant/form JSON，点击「运行」验证返回值正确后再保存。</li>'
        '<li>进入「<a href="/admin/process-scripts" style="color:#1a73e8">自定义处理脚本</a>」，同名新建脚本，'
        '实现 <code>def run(applicant, form)</code>，编写审批通过后的自动化处理逻辑，保存。</li>'
        '<li>同样在「调用参数」区填入测试数据，点击「运行」确认脚本无报错后保存。</li>'
        '<li>发起一条真实测试审批，在「<a href="/admin/precheck-records" style="color:#1a73e8">预检查记录</a>」'
        '和「<a href="/admin/process-records" style="color:#1a73e8">处理记录</a>」中确认状态为 success；'
        '若为 error 可点击「重试」，并根据 extra_info 中的错误信息修正脚本。</li>'
        '</ol>'
        '<p style="font-size:12px;color:#888;margin:-8px 0 20px">'
        '如需在「<a href="/admin/envvars" style="color:#1a73e8">环境变量</a>」Tab 中添加密钥，'
        '或修改系统配置、新增审批 Code，请联系 admin。'
        '</p>'
        )
        + '</div>'
    )
    return _page_shell("about", _build_token_html(), body, is_admin=is_admin, current_user=current_user)


def _render_scripts_page(script_type: str, is_admin: bool = True, current_user: str = "") -> str:
    """渲染脚本管理页。script_type: 'precheck' 或 'process'。"""
    from services.db import (
        list_precheck_scripts, list_process_scripts,
        list_check_tasks_paged, list_proc_tasks_paged,
    )

    if script_type == "precheck":
        scripts = list_precheck_scripts()
        tab_key = "precheck-scripts"
        title = "自定义预检查脚本"
        api_prefix = "/api/precheck-scripts"
        debug_fn = "check"
        history = list_check_tasks_paged(1, 100)
    else:
        scripts = list_process_scripts()
        tab_key = "process-scripts"
        title = "自定义处理任务脚本"
        api_prefix = "/api/process-scripts"
        debug_fn = "run"
        history = list_proc_tasks_paged(1, 100)

    # -- 模版代码 --
    if script_type == "precheck":
        _tpl = (
            'def check(applicant: dict, form: dict) -> tuple[bool, str]:\n'
            '    """\n'
            '    预检查逻辑。\n'
            '\n'
            '    Parameters\n'
            '    ----------\n'
            '    applicant : dict\n'
            '        申请人信息 (name, email, open_id, mobile, employee_no, ...)\n'
            '    form : dict\n'
            '        表单字段 {字段名: 值}\n'
            '\n'
            '    Returns\n'
            '    -------\n'
            '    (True, "")           — 通过，节点自动审批\n'
            '    (False, "退回原因")   — 不通过，节点自动退回\n'
            '    """\n'
            '    # 环境变量示例：api_key = ENV.get("MY_API_KEY", "")\n'
            '    # 在此编写预检查逻辑\n'
            '\n'
            '    return True, ""\n'
        )
    else:
        _tpl = (
            'import logging\n'
            '\n'
            'logger = logging.getLogger(__name__)\n'
            '\n'
            '\n'
            'def run(applicant: dict, form: dict):\n'
            '    """\n'
            '    处理逻辑。\n'
            '\n'
            '    Parameters\n'
            '    ----------\n'
            '    applicant : dict\n'
            '        申请人信息 (name, email, open_id, mobile, employee_no, ...)\n'
            '    form : dict\n'
            '        表单字段 {字段名: 值}\n'
            '\n'
            '    Returns\n'
            '    -------\n'
            '    str | None  处理结果说明（写入 extra_info）\n'
            '    抛出异常     状态标记为 error，可从管理页重试\n'
            '    """\n'
            '    name = applicant.get("name", "")\n'
            '    open_id = applicant.get("open_id", "")\n'
            '\n'
            '    # 环境变量示例：api_key = ENV.get("MY_API_KEY", "")\n'
            '    # 在此编写处理逻辑\n'
            '\n'
            '    return f"处理完成"\n'
        )
    tpl_js = json.dumps(_tpl)  # JS-safe string

    # -- 编写指南文档 --
    _rec_hint_pre  = '可在「预检查记录」页面的「申请事项」列查看任意一条记录确认。'
    _rec_hint_proc = '可在「处理任务」页面的「申请事项」列查看任意一条记录确认。'
    if script_type == "precheck":
        guide_html = (
            '<details style="margin-bottom:16px;background:#fff;border-radius:8px;padding:16px;'
            'box-shadow:0 1px 4px rgba(0,0,0,.08)">'
            '<summary style="cursor:pointer;font-weight:600;font-size:15px;color:#1a73e8">'
            '自定义预检查脚本说明与编写指南</summary>'
            '<div style="margin-top:12px;font-size:13px;line-height:1.9;color:#333">'

            '<div style="background:#e8f0fe;border-left:4px solid #1a73e8;padding:10px 14px;'
            'border-radius:0 6px 6px 0;margin-bottom:14px">'
            '<b>什么是自定义预检查脚本？</b><br>'
            '当飞书审批流程中包含名为「<b>预检查</b>」（节点名可在系统配置中修改）的审批节点，'
            '系统会在该节点进入「待审批」时自动执行对应脚本。'
            '通过则节点自动审批；不通过则整个审批自动退回并附上原因。没有匹配到脚本时节点留给人工审批。'
            '</div>'

            '<h4 style="margin:8px 0 4px">① 触发时机</h4>'
            '<p>同时满足以下两个条件时自动触发：</p>'
            '<ul style="margin:4px 0 8px 20px;padding:0">'
            '<li>收到飞书推送：审批实例状态变为 <code>PENDING</code></li>'
            '<li>审批任务列表中存在节点名称 = 「<code>预检查</code>」（可配置）且节点状态 = <code>PENDING</code></li>'
            '</ul>'

            '<h4 style="margin:12px 0 4px">② 脚本如何被匹配</h4>'
            '<p>系统以「<b>申请事项</b>」为键名查找并执行对应脚本。申请事项的取值规则：</p>'
            '<ul style="margin:4px 0 8px 20px;padding:0">'
            '<li>若表单中存在名为「<code>申请事项</code>」的字段且有填写内容，使用该字段的值</li>'
            '<li>否则取飞书审批定义的<b>名称</b></li>'
            '</ul>'
            f'<p style="font-size:12px;color:#666;margin:4px 0 10px">{_rec_hint_pre}</p>'

            '<h4 style="margin:12px 0 4px">③ 函数签名与返回值</h4>'
            '<p>必须实现：<code>check(applicant: dict, form: dict) -> tuple[bool, str]</code></p>'
            '<table style="font-size:12px;border-collapse:collapse;width:100%;margin-top:6px">'
            '<tr style="background:#f5f5f5">'
            '<th style="text-align:left;padding:4px 8px">返回值</th>'
            '<th style="text-align:left;padding:4px 8px">效果</th></tr>'
            '<tr><td style="padding:4px 8px"><code>(True, "")</code></td>'
            '<td style="padding:4px 8px">预检查通过，节点自动审批</td></tr>'
            '<tr><td style="padding:4px 8px"><code>(False, "原因")</code></td>'
            '<td style="padding:4px 8px">预检查不通过，整个审批自动退回，原因作为退回备注</td></tr>'
            '<tr><td style="padding:4px 8px">抛出异常</td>'
            '<td style="padding:4px 8px">节点不会自动处理，任务状态标记为 <code>error</code>，需人工介入</td></tr>'
            '</table>'

            '<h4 style="margin:12px 0 4px">④ 参数说明</h4>'
            '<table style="font-size:12px;border-collapse:collapse;width:100%">'
            '<tr style="background:#f5f5f5">'
            '<th style="text-align:left;padding:4px 8px">参数</th>'
            '<th style="text-align:left;padding:4px 8px">类型</th>'
            '<th style="text-align:left;padding:4px 8px">说明</th></tr>'
            '<tr><td style="padding:4px 8px"><code>applicant</code></td>'
            '<td style="padding:4px 8px">dict</td>'
            '<td style="padding:4px 8px">申请人信息：<code>name</code>、<code>email</code>、<code>enterprise_email</code>、<code>open_id</code>、<code>mobile</code>、<code>employee_no</code></td></tr>'
            '<tr><td style="padding:4px 8px"><code>form</code></td>'
            '<td style="padding:4px 8px">dict</td>'
            '<td style="padding:4px 8px">审批表单所有字段的 <code>{字段名: 字段内容}</code> 字典</td></tr>'
            '</table>'

            '<h4 style="margin:12px 0 4px">⑤ 环境变量（ENV）</h4>'
            '<p>在「<a href="/admin/envvars" style="color:#1a73e8">环境变量</a>」Tab 中配置的 KV 在脚本执行时自动注入为 <code>ENV</code> 字典：</p>'
            '<pre style="background:#f5f5f5;padding:8px 12px;border-radius:6px;font-size:12px;margin:4px 0 10px">api_key = ENV.get("MY_API_KEY", "")</pre>'

            '<h4 style="margin:12px 0 4px">⑥ 注意事项</h4>'
            '<ul style="margin:4px 0 4px 20px;padding:0">'
            '<li>可自由 import 标准库及已安装的第三方库，也可通过 <code>from services.db import ...</code> 使用项目内部服务</li>'
            '<li>建议用 <code>logging</code> 记录关键判断，便于异常时排查</li>'
            '</ul>'
            '</div></details>'
        )
    else:
        guide_html = (
            '<details style="margin-bottom:16px;background:#fff;border-radius:8px;padding:16px;'
            'box-shadow:0 1px 4px rgba(0,0,0,.08)">'
            '<summary style="cursor:pointer;font-weight:600;font-size:15px;color:#1a73e8">'
            '自定义处理任务脚本说明与编写指南</summary>'
            '<div style="margin-top:12px;font-size:13px;line-height:1.9;color:#333">'

            '<div style="background:#e6f4ea;border-left:4px solid #1a7f3c;padding:10px 14px;'
            'border-radius:0 6px 6px 0;margin-bottom:14px">'
            '<b>什么是自定义处理任务脚本？</b><br>'
            '当飞书审批<b>最终通过</b>后，系统自动执行对应脚本的 <code>run()</code>，'
            '完成具体的自动化业务（如开通权限、创建云资源、变更 DNS、通知申请人等）。'
            '异常时可在「处理任务」页面重试。没有匹配到脚本时审批通过后自动创建处理群跟进。'
            '</div>'

            '<h4 style="margin:8px 0 4px">① 触发时机</h4>'
            '<p>审批实例状态变为 <code>APPROVED</code>（最终通过）时自动触发。</p>'
            '<p style="color:#888;font-size:12px;margin:2px 0 8px">提示：若审批流程配置了预检查节点，预检查通过后仍需经过后续审批节点，全部通过后才会触发处理脚本。</p>'

            '<h4 style="margin:12px 0 4px">② 脚本如何被匹配</h4>'
            '<p>系统以「<b>申请事项</b>」为键名查找并执行对应脚本。申请事项的取值规则：</p>'
            '<ul style="margin:4px 0 8px 20px;padding:0">'
            '<li>若表单中存在名为「<code>申请事项</code>」的字段且有填写内容，使用该字段的值</li>'
            '<li>否则取飞书审批定义的<b>名称</b></li>'
            '</ul>'
            f'<p style="font-size:12px;color:#666;margin:4px 0 10px">{_rec_hint_proc}</p>'

            '<h4 style="margin:12px 0 4px">③ 函数签名与返回值</h4>'
            '<p>必须实现：<code>run(applicant: dict, form: dict)</code></p>'
            '<table style="font-size:12px;border-collapse:collapse;width:100%;margin-top:6px">'
            '<tr style="background:#f5f5f5">'
            '<th style="text-align:left;padding:4px 8px">返回值</th>'
            '<th style="text-align:left;padding:4px 8px">效果</th></tr>'
            '<tr><td style="padding:4px 8px"><code>str</code></td>'
            '<td style="padding:4px 8px">写入任务记录的 <code>extra_info</code> 字段，便于追溯</td></tr>'
            '<tr><td style="padding:4px 8px"><code>None</code> / 不写 return</td>'
            '<td style="padding:4px 8px">正常完成</td></tr>'
            '<tr><td style="padding:4px 8px">抛出异常</td>'
            '<td style="padding:4px 8px">任务标记为 <code>error</code>，可在「处理任务」页面重试</td></tr>'
            '</table>'

            '<h4 style="margin:12px 0 4px">④ 参数说明</h4>'
            '<table style="font-size:12px;border-collapse:collapse;width:100%">'
            '<tr style="background:#f5f5f5">'
            '<th style="text-align:left;padding:4px 8px">参数</th>'
            '<th style="text-align:left;padding:4px 8px">类型</th>'
            '<th style="text-align:left;padding:4px 8px">说明</th></tr>'
            '<tr><td style="padding:4px 8px"><code>applicant</code></td>'
            '<td style="padding:4px 8px">dict</td>'
            '<td style="padding:4px 8px">申请人信息：<code>name</code>、<code>email</code>、<code>enterprise_email</code>、<code>open_id</code>、<code>mobile</code>、<code>employee_no</code></td></tr>'
            '<tr><td style="padding:4px 8px"><code>form</code></td>'
            '<td style="padding:4px 8px">dict</td>'
            '<td style="padding:4px 8px">审批表单所有字段的 <code>{字段名: 字段内容}</code> 字典</td></tr>'
            '</table>'

            '<h4 style="margin:12px 0 4px">⑤ 常用服务</h4>'
            '<ul style="margin:4px 0 4px 20px;padding:0">'
            '<li><code>from services.notify import send_feishu_message</code> — 发送飞书应用消息/卡片</li>'
            '<li><code>from services.chat import create_group, dissolve_group</code> — 飞书群管理</li>'
            '<li><code>import requests</code> — 调用外部 HTTP API</li>'
            '<li><code>from config import ...</code> — 读取系统配置（如 CMDB 地址、Token 等）</li>'
            '</ul>'

            '<h4 style="margin:12px 0 4px">⑥ 环境变量（ENV）</h4>'
            '<p>在「<a href="/admin/envvars" style="color:#1a73e8">环境变量</a>」Tab 中配置的 KV 在脚本执行时自动注入为 <code>ENV</code> 字典：</p>'
            '<pre style="background:#f5f5f5;padding:8px 12px;border-radius:6px;font-size:12px;margin:4px 0 10px">api_key = ENV.get("MY_API_KEY", "")</pre>'

            '<h4 style="margin:12px 0 4px">⑦ 注意事项</h4>'
            '<ul style="margin:4px 0 4px 20px;padding:0">'
            '<li>处理脚本在独立线程中执行，请注意线程安全</li>'
            '<li>建议用 <code>logging</code> 记录关键步骤，日志会输出到服务控制台</li>'
            '<li>长时间操作建议加超时控制，避免线程长期挂起</li>'
            '<li>不要调用 <code>sys.exit()</code>，会终止整个服务进程</li>'
            '</ul>'
            '</div></details>'
        )

    # -- 脚本列表表格 --
    if not scripts:
        table_rows = '<tr><td colspan="4" style="text-align:center;color:#888;padding:24px">暂无脚本</td></tr>'
    else:
        trs = []
        for s in scripts:
            esc_name = s["name"].replace('"', "&quot;").replace("'", "\\'")
            enabled_badge = ('<span style="color:#1a7f3c">✓ 启用</span>' if s["enabled"]
                             else '<span style="color:#d93025">✗ 禁用</span>')
            trs.append(
                f'<tr>'
                f'<td style="font-weight:600">{s["name"]}</td>'
                f'<td>{enabled_badge}</td>'
                f'<td style="font-size:12px;color:#888">{s.get("updated_at") or "-"}</td>'
                f'<td>'
                f'<button class="btn-orange" onclick="editScript(\'{esc_name}\')">编辑</button> '
                f'<button class="btn-red" onclick="deleteScript(\'{esc_name}\')">删除</button>'
                f'</td>'
                f'</tr>'
            )
        table_rows = "\n".join(trs)

    # -- 历史记录 options --
    hist_options = '<option value="">-- 选择历史记录自动填入 --</option>'
    for h in history:
        hname = h.get("applicant_name") or h.get("applicant_open_id") or "?"
        hsubj = h.get("subject") or "?"
        htime = (h.get("created_at") or "")[:16]
        aj = (h.get("applicant_json") or "{}").replace('"', "&quot;")
        fj = (h.get("form_json") or "{}").replace('"', "&quot;")
        hist_options += (
            f'<option data-applicant="{aj}" data-form="{fj}">'
            f'{hname} / {hsubj} / {htime}</option>'
        )

    body = (
        # -- 编写指南 --
        guide_html +
        # -- 脚本列表 --
        '<div style="margin-bottom:16px">'
        '<button onclick="newScript()" style="background:#1a73e8;color:#fff;border:none;'
        'padding:6px 18px;border-radius:6px;cursor:pointer;font-size:13px;margin-bottom:10px">'
        '新增脚本</button>'
        '</div>'
        '<table><thead><tr>'
        '<th>申请事项</th><th>状态</th><th>更新时间</th><th>操作</th>'
        '</tr></thead><tbody>'
        + table_rows +
        '</tbody></table>'

        # ── 编辑 + 调试 模态框（左右两栏） ──
        '<div id="editModal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.45);'
        'z-index:9999;align-items:center;justify-content:center">'
        '<div style="background:#fff;border-radius:10px;width:96%;max-width:1400px;height:90vh;'
        'display:flex;flex-direction:column;position:relative;overflow:hidden">'
        # 顶栏
        '<div style="display:flex;align-items:center;justify-content:space-between;padding:16px 24px;'
        'border-bottom:1px solid #eee;flex-shrink:0">'
        '<h3 id="modalTitle" style="margin:0;font-size:16px">编辑脚本</h3>'
        '<div style="display:flex;align-items:center;gap:16px">'
        '<label style="font-size:13px;display:flex;align-items:center;gap:4px">'
        '<input id="scriptEnabled" type="checkbox" checked> 启用</label>'
        '<button onclick="saveScript()" style="background:#1a73e8;color:#fff;border:none;'
        'padding:6px 20px;border-radius:6px;cursor:pointer;font-size:13px">保存</button>'
        '<button onclick="loadHistory()" style="background:#6c757d;color:#fff;border:none;'
        'padding:6px 16px;border-radius:6px;cursor:pointer;font-size:13px">历史版本</button>'
        '<button onclick="closeEditModal()" style="background:#888;color:#fff;border:none;'
        'padding:6px 16px;border-radius:6px;cursor:pointer;font-size:13px">关闭</button>'
        '</div></div>'
        # 脚本名称行
        '<div style="padding:10px 24px;border-bottom:1px solid #f0f0f0;flex-shrink:0;display:flex;'
        'align-items:center;gap:12px">'
        '<label style="font-size:13px;white-space:nowrap;font-weight:600">申请事项</label>'
        '<input id="scriptName" style="flex:1;max-width:400px;border:1px solid #ccc;border-radius:4px;'
        'padding:5px 10px;font-size:14px">'
        '</div>'
        # 左右两栏主体
        '<div style="display:flex;flex:1;overflow:hidden">'
        # 左栏：代码编辑器
        '<div style="flex:1;display:flex;flex-direction:column;border-right:1px solid #eee;min-width:0;overflow:hidden">'
        '<div style="padding:8px 16px;border-bottom:1px solid #f5f5f5;font-size:13px;font-weight:600;'
        'color:#555;flex-shrink:0">代码编辑器</div>'
        '<textarea id="scriptCode" style="flex:1;width:100%;border:none;font-family:\'Menlo\',\'Consolas\',monospace;'
        'font-size:13px;line-height:1.5;padding:12px 16px;tab-size:4;white-space:pre;overflow:auto;resize:none;'
        'outline:none;background:#fafafa;box-sizing:border-box"></textarea>'
        '</div>'
        # 右栏：调试面板
        '<div style="width:440px;flex-shrink:0;display:flex;flex-direction:column;overflow:hidden">'
        '<div style="padding:8px 16px;border-bottom:1px solid #f5f5f5;font-size:13px;font-weight:600;'
        'color:#555;flex-shrink:0">调试面板</div>'
        '<div style="flex:1;overflow-y:auto;padding:12px 16px">'
        # 历史记录下拉
        '<div style="margin-bottom:10px">'
        '<label style="font-size:12px;color:#666">填入历史记录</label><br>'
        f'<select id="debugHistory" onchange="fillHistory()" style="width:100%;border:1px solid #ccc;'
        f'border-radius:4px;padding:5px;font-size:12px;margin-top:3px">{hist_options}</select>'
        '</div>'
        # applicant JSON
        '<div style="margin-bottom:10px">'
        '<label style="font-size:12px;color:#666">applicant (JSON)</label>'
        '<textarea id="debugApplicant" style="width:100%;height:100px;font-family:monospace;font-size:11px;'
        'border:1px solid #ccc;border-radius:4px;padding:6px;margin-top:3px;box-sizing:border-box">{}</textarea>'
        '</div>'
        # form JSON
        '<div style="margin-bottom:10px">'
        '<label style="font-size:12px;color:#666">form (JSON)</label>'
        '<textarea id="debugForm" style="width:100%;height:100px;font-family:monospace;font-size:11px;'
        'border:1px solid #ccc;border-radius:4px;padding:6px;margin-top:3px;box-sizing:border-box">{}</textarea>'
        '</div>'
        # 执行按钮
        '<button onclick="runDebug()" style="background:#1a73e8;color:#fff;border:none;padding:7px 20px;'
        'border-radius:6px;cursor:pointer;font-size:13px;margin-bottom:10px;width:100%">'
        '执行调试（使用编辑器中的代码）</button>'
        # 输出
        '<pre id="debugOutput" style="background:#1d2129;color:#e6e6e6;border-radius:6px;padding:12px;'
        'font-size:12px;white-space:pre-wrap;word-break:break-all;min-height:120px;max-height:100%;overflow:auto">'
        '等待执行……</pre>'
        '</div></div>'  # 右栏结束
        '</div>'  # flex 两栏结束
        '</div></div>'  # modal 结束

        # ── JavaScript ──
        '<script>\n'
        f'const API = "{api_prefix}";\n'
        f'const TEMPLATE = {tpl_js};\n'
        f'const DEBUG_FN = "{debug_fn}";\n'
        'let _editingOld = "";\n'
        'let _scriptEditor = null;\n'
        'function ensureScriptEditor() {\n'
        '  if (_scriptEditor) return _scriptEditor;\n'
        '  const ta = document.getElementById("scriptCode");\n'
        '  if (!ta || !window.CodeMirror) return null;\n'
        '  _scriptEditor = CodeMirror.fromTextArea(ta, {\n'
        '    mode: "python",\n'
        '    theme: "eclipse",\n'
        '    lineNumbers: true,\n'
        '    indentUnit: 4,\n'
        '    tabSize: 4,\n'
        '    matchBrackets: true,\n'
        '    lineWrapping: false\n'
        '  });\n'
        '  _scriptEditor.setSize("100%", "100%");\n'
        '  return _scriptEditor;\n'
        '}\n'
        'function setScriptCode(v) {\n'
        '  const ed = ensureScriptEditor();\n'
        '  if (ed) { ed.setValue(v || ""); ed.clearHistory(); setTimeout(() => ed.refresh(), 0); }\n'
        '  else { document.getElementById("scriptCode").value = v || ""; }\n'
        '}\n'
        'function getScriptCode() {\n'
        '  const ed = ensureScriptEditor();\n'
        '  return ed ? ed.getValue() : document.getElementById("scriptCode").value;\n'
        '}\n'
        '\n'
        'function newScript() {\n'
        '  _editingOld = "";\n'
        '  document.getElementById("modalTitle").textContent = "新增脚本";\n'
        '  document.getElementById("scriptName").value = "";\n'
        '  document.getElementById("scriptName").disabled = false;\n'
        '  document.getElementById("scriptEnabled").checked = true;\n'
        '  ensureScriptEditor();\n'
        '  setScriptCode(TEMPLATE);\n'
        '  document.getElementById("debugOutput").textContent = "等待执行……";\n'
        '  document.getElementById("debugApplicant").value = "{}";\n'
        '  document.getElementById("debugForm").value = "{}";\n'
        '  document.getElementById("editModal").style.display = "flex";\n'
        '}\n'
        '\n'
        'async function editScript(name) {\n'
        '  const r = await fetch(API + "/get?name=" + encodeURIComponent(name));\n'
        '  const j = await r.json();\n'
        '  if(!j.ok){ alert("加载失败: " + j.error); return; }\n'
        '  _editingOld = name;\n'
        '  document.getElementById("modalTitle").textContent = "编辑脚本: " + name;\n'
        '  document.getElementById("scriptName").value = j.data.name;\n'
        '  document.getElementById("scriptName").disabled = true;\n'
        '  document.getElementById("scriptEnabled").checked = !!j.data.enabled;\n'
        '  ensureScriptEditor();\n'
        '  setScriptCode(j.data.code);\n'
        '  document.getElementById("debugOutput").textContent = "等待执行……";\n'
        '  document.getElementById("debugApplicant").value = "{}";\n'
        '  document.getElementById("debugForm").value = "{}";\n'
        '  document.getElementById("editModal").style.display = "flex";\n'
        '}\n'
        '\n'
        'function closeEditModal() {\n'
        '  document.getElementById("editModal").style.display = "none";\n'
        '}\n'
        '\n'
        'async function saveScript() {\n'
        '  const name = document.getElementById("scriptName").value.trim();\n'
        '  const code = getScriptCode();\n'
        '  const enabled = document.getElementById("scriptEnabled").checked ? 1 : 0;\n'
        '  if(!name){ alert("名称不能为空"); return; }\n'
        '  const endpoint = _editingOld ? "/edit" : "/create";\n'
        '  const r = await fetch(API + endpoint, {method:"POST",\n'
        '    headers:{"Content-Type":"application/json"},\n'
        '    body:JSON.stringify({name, code, enabled})});\n'
        '  const j = await r.json();\n'
        '  if(j.ok){ alert("✓ 已保存"); location.reload(); }\n'
        '  else { alert("✗ " + j.error); }\n'
        '}\n'
        '\n'
        'async function deleteScript(name) {\n'
        '  if(!confirm("确认删除脚本: " + name + "？")) return;\n'
        '  const r = await fetch(API + "/delete", {method:"POST",\n'
        '    headers:{"Content-Type":"application/json"},\n'
        '    body:JSON.stringify({name})});\n'
        '  const j = await r.json();\n'
        '  if(j.ok){ alert("✓ 已删除"); location.reload(); }\n'
        '  else { alert("✗ " + j.error); }\n'
        '}\n'
        '\n'
        'function fillHistory() {\n'
        '  const sel = document.getElementById("debugHistory");\n'
        '  const opt = sel.options[sel.selectedIndex];\n'
        '  if(!opt || !opt.dataset.applicant) return;\n'
        '  try { document.getElementById("debugApplicant").value = JSON.stringify(JSON.parse(opt.dataset.applicant), null, 2); } catch(e){}\n'
        '  try { document.getElementById("debugForm").value = JSON.stringify(JSON.parse(opt.dataset.form), null, 2); } catch(e){}\n'
        '}\n'
        '\n'
        'async function runDebug() {\n'
        '  const code = getScriptCode();\n'
        '  if(!code.trim()){ alert("代码不能为空"); return; }\n'
        '  const scriptName = document.getElementById("scriptName").value.trim() || "untitled";\n'
        '  let applicant, form;\n'
        '  try { applicant = JSON.parse(document.getElementById("debugApplicant").value); }\n'
        '  catch(e){ alert("applicant JSON 格式错误"); return; }\n'
        '  try { form = JSON.parse(document.getElementById("debugForm").value); }\n'
        '  catch(e){ alert("form JSON 格式错误"); return; }\n'
        '  document.getElementById("debugOutput").textContent = "执行中……";\n'
        '  try {\n'
        '    const r = await fetch(API + "/debug", {method:"POST",\n'
        '      headers:{"Content-Type":"application/json"},\n'
        '      body:JSON.stringify({script_name:scriptName, code, applicant, form})});\n'
        '    const j = await r.json();\n'
        '    let out = "";\n'
        '    if(j.error) out += "❌ 异常:\\n" + j.error + "\\n\\n";\n'
        '    if(j.format_warning) out += j.format_warning + "\\n\\n";\n'
        '    if(j.result !== undefined && j.result !== null) out += "📋 返回值:\\n" + JSON.stringify(j.result, null, 2) + "\\n\\n";\n'
        '    if(j.stdout) out += "📤 stdout:\\n" + j.stdout + "\\n";\n'
        '    if(j.stderr) out += "⚠️ stderr:\\n" + j.stderr + "\\n";\n'
        '    if(!out) out = "✓ 执行完成（无输出）";\n'
        '    document.getElementById("debugOutput").textContent = out;\n'
        '  } catch(e) {\n'
        '    document.getElementById("debugOutput").textContent = "❌ 请求失败: " + e;\n'
        '  }\n'
        '}\n'
        '\n'
        'async function loadHistory() {\n'
        '  const name = document.getElementById("scriptName").value.trim();\n'
        '  if(!name){ alert("请先打开一个脚本"); return; }\n'
        '  const r = await fetch(API+"/history",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name})});\n'
        '  const j = await r.json();\n'
        '  if(!j.ok){ alert("加载失败: "+j.error); return; }\n'
        '  if(!j.data.length){ alert("暂无历史版本"); return; }\n'
        '  let msg = "版本历史（最近 " + j.data.length + " 条）：\\n\\n";\n'
        '  j.data.forEach((h,i)=>{ msg += (i+1) + ". [" + h.created_at + "] " + (h.username||"system") + "\\n"; });\n'
        '  msg += "\\n输入序号回滚到该版本（取消则不操作）：";\n'
        '  const idx = prompt(msg);\n'
        '  if(!idx) return;\n'
        '  const n = parseInt(idx)-1;\n'
        '  if(isNaN(n)||n<0||n>=j.data.length){ alert("无效序号"); return; }\n'
        '  if(!confirm("确认回滚到 " + j.data[n].created_at + " 的版本？当前编辑器中的代码将被覆盖。")) return;\n'
        '  const rr = await fetch(API+"/rollback",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({history_id:j.data[n].id})});\n'
        '  const jj = await rr.json();\n'
        '  if(jj.ok){ alert("✓ 已回滚"); location.reload(); } else { alert("✗ "+jj.error); }\n'
        '}\n'
        '\n'
        '// textarea: Tab → 4 空格, Shift+Tab → 反缩进\n'
        'document.addEventListener("keydown", function(e) {\n'
        '  if(e.target.tagName !== "TEXTAREA") return;\n'
        '  if(e.key === "Tab") {\n'
        '    e.preventDefault();\n'
        '    var ta = e.target, s = ta.selectionStart, en = ta.selectionEnd;\n'
        '    if(!e.shiftKey) {\n'
        '      ta.value = ta.value.substring(0, s) + "    " + ta.value.substring(en);\n'
        '      ta.selectionStart = ta.selectionEnd = s + 4;\n'
        '    } else {\n'
        '      var lineStart = ta.value.lastIndexOf("\\n", s - 1) + 1;\n'
        '      var line = ta.value.substring(lineStart, s);\n'
        '      var rem = 0;\n'
        '      while(rem < 4 && line[rem] === " ") rem++;\n'
        '      if(rem > 0) { ta.value = ta.value.substring(0, lineStart) + ta.value.substring(lineStart + rem); ta.selectionStart = ta.selectionEnd = s - rem; }\n'
        '    }\n'
        '  }\n'
        '});\n'
        '</script>\n'
    )
    return _page_shell(tab_key, _build_token_html(), body, is_admin=is_admin, current_user=current_user)


# ---------------------------------------------------------------------------
# FastAPI 应用
# ---------------------------------------------------------------------------

app = FastAPI(title="飞书审批Claw管理后台", docs_url=None, redoc_url=None)
from fastapi import HTTPException


# -- Auth 依赖 ----------------------------------------------------------------

def _get_auth_user(request: Request):
    if not ADMIN_USER or not ADMIN_PASS:
        return None
    import base64 as _b64
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Basic "):
        try:
            creds = _b64.b64decode(auth[6:]).decode("utf-8")
            user, _, pwd = creds.partition(":")
            if (user == ADMIN_USER and pwd == ADMIN_PASS) or \
                    (user in ACCOUNTS and ACCOUNTS[user] == pwd):
                return user
        except Exception:
            pass
    return None


def _is_admin_user(request: Request) -> bool:
    if not ADMIN_USER or not ADMIN_PASS:
        return False
    import base64 as _b64
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Basic "):
        try:
            creds = _b64.b64decode(auth[6:]).decode("utf-8")
            user, _, pwd = creds.partition(":")
            return user == ADMIN_USER and pwd == ADMIN_PASS
        except Exception:
            pass
    return False


class _UnauthorizedException(HTTPException):
    def __init__(self):
        super().__init__(status_code=401)


class _ForbiddenException(HTTPException):
    def __init__(self):
        super().__init__(status_code=403, detail="此操作仅主管理员可执行。")


def _require_any(request: Request) -> str:
    user = _get_auth_user(request)
    if user is None:
        raise _UnauthorizedException()
    return user


def _require_admin_dep(request: Request) -> str:
    user = _get_auth_user(request)
    if user is None:
        raise _UnauthorizedException()
    if not _is_admin_user(request):
        raise _ForbiddenException()
    return user


@app.exception_handler(_UnauthorizedException)
async def _unauth_handler(request: Request, exc: _UnauthorizedException):
    return Response(
        status_code=401,
        headers={"WWW-Authenticate": 'Basic realm="AIOps Admin"'},
        content="",
    )


@app.exception_handler(_ForbiddenException)
async def _forbidden_handler(request: Request, exc: _ForbiddenException):
    return HTMLResponse("<h2>403 Forbidden</h2><p>此操作仅主管理员可执行。</p>", status_code=403)


# -- 日志 & 辅助 ---------------------------------------------------------------

def _log_admin_action(username: str, request: Request, action: str, detail: str = "") -> None:
    _action_labels = {
        "save_settings": "保存配置", "restart": "重启服务",
        "retry_task": "重试处理", "retry_check": "重试预检",
        "dissolve_group": "解散群", "precheck_create": "新增预检脚本",
        "precheck_edit": "编辑预检脚本", "precheck_delete": "删除预检脚本",
        "process_create": "新增处理脚本", "process_edit": "编辑处理脚本",
        "process_delete": "删除处理脚本", "envvar_create": "新增环境变量",
        "envvar_edit": "修改环境变量", "envvar_delete": "删除环境变量",
    }
    try:
        from services.db import log_admin_action
        ip = (request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
              or (request.client.host if request.client else ""))
        log_admin_action(username, ip, _action_labels.get(action, action), detail)
    except Exception:
        pass


# -- GET /health --------------------------------------------------------------

@app.get("/health")
async def health():
    import time as _time
    mgr = _user_token.get_instance()
    status = {
        "status": "ok",
        "user_token": "已配置" if mgr else "未配置（发送消息将使用主应用身份）",
    }
    if mgr:
        remaining = max(0, int(mgr._expires_at - _time.time()))
        status["token_expires_in_seconds"] = remaining
        status["can_auto_refresh"] = bool(mgr._refresh_token)
        status["tip"] = "正常" if remaining > 300 else "token 即将过期，建议访问 /auth 重新授权"
    else:
        status["tip"] = f"访问 http://localhost:{HTTP_PORT}/auth 完成授权"
    try:
        from services.db import get_setting
        status["db"] = "ok"
    except Exception as e:
        status["db"] = f"error: {e}"
    try:
        import main as _main_mod
        status["websocket"] = "connected" if _main_mod._ws_connected else "disconnected"
    except Exception:
        status["websocket"] = "unknown"
    try:
        from services.db import _read_conn as _db_conn
        with _db_conn() as con:
            row = con.execute(
                "SELECT updated_at FROM proc_tasks ORDER BY updated_at DESC LIMIT 1"
            ).fetchone()
        status["last_proc_event"] = row["updated_at"] if row else "无记录"
        with _db_conn() as con:
            row2 = con.execute(
                "SELECT updated_at FROM check_tasks ORDER BY updated_at DESC LIMIT 1"
            ).fetchone()
        status["last_check_event"] = row2["updated_at"] if row2 else "无记录"
    except Exception:
        pass
    return JSONResponse(status)


# -- GET /auth ----------------------------------------------------------------

@app.get("/auth")
async def start_auth(user: str = Depends(_require_admin_dep)):
    missing_auth = get_missing_configs(["APP_ID", "APP_SECRET", "REDIRECT_URI"])
    if missing_auth:
        return HTMLResponse(
            f"<h2>主应用配置不完整，暂时无法授权</h2>"
            f"<p>缺少配置：{', '.join(missing_auth)}</p>"
            f"<p>请前往 <a href='/admin/settings'>/admin/settings</a> 配置后保存并重启。</p>",
            status_code=503,
        )
    auth_url = (
        f"{FEISHU_HOST}/open-apis/authen/v1/authorize"
        f"?app_id={APP_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=offline_access%20im:message%20im:chat"
    )
    return RedirectResponse(auth_url, status_code=302)


# -- GET /callback ------------------------------------------------------------

@app.get("/callback")
async def callback(request: Request):
    missing_auth = get_missing_configs(["APP_ID", "APP_SECRET", "REDIRECT_URI"])
    if missing_auth:
        return HTMLResponse(
            f"<h2>主应用配置不完整，暂时无法处理授权回调</h2>"
            f"<p>缺少配置：{', '.join(missing_auth)}</p>"
            f"<p>请前往 <a href='/admin/settings'>/admin/settings</a> 配置后保存并重启。</p>",
            status_code=503,
        )
    code = request.query_params.get("code", "")
    if not code:
        return HTMLResponse("<h2>未收到授权码，请重新访问 /auth</h2>", status_code=400)
    try:
        data = exchange_code_for_token(code)
        access_token  = data["access_token"]
        refresh_token = data.get("refresh_token", "")
        expires_in    = data.get("expires_in", 7200)
        refresh_expires_in = data.get("refresh_token_expires_in")
        apply_new_token(access_token, refresh_token, expires_in, refresh_expires_in)
        tip = "支持自动续期" if refresh_token else "警告：未获取到 refresh_token，过期后需重新授权"
        return HTMLResponse(f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>授权成功</title></head><body>
<h2>授权成功，token 已写入并立即生效</h2>
<p>有效期：{expires_in} 秒（约 {expires_in // 3600} 小时）</p>
<p>{tip}</p>
<p>可关闭此页面，服务无需重启。</p>
<p><a href="/admin/process-records">查看管理页面</a></p>
</body></html>""")
    except Exception as e:
        logger.error("OAuth 回调处理失败: %s", e)
        return HTMLResponse(f"<h2>授权失败: {e}</h2><p>请重试 /auth</p>", status_code=500)


# -- GET /admin ---------------------------------------------------------------

@app.get("/admin")
async def admin_redirect(user: str = Depends(_require_any)):
    return RedirectResponse("/admin/process-records", status_code=302)


@app.get("/admin/process-records")
async def admin_proc(request: Request, page: int = 1, name: str = "",
                     subject: str = "", page_size: int = 20,
                     user: str = Depends(_require_any)):
    page_size = page_size if page_size in (10, 20, 50, 100) else 20
    is_adm = _is_admin_user(request)
    try:
        html = _render_proc_page(page=page, page_size=page_size, name=name,
                                 subject=subject, is_admin=is_adm, current_user=user)
        return HTMLResponse(html)
    except Exception as e:
        logger.error("渲染处理任务页失败: %s", e)
        return PlainTextResponse(f"Internal error: {e}", status_code=500)


@app.get("/admin/precheck-records")
async def admin_check(request: Request, cpage: int = 1, cname: str = "",
                      csubject: str = "", cpage_size: int = 20,
                      user: str = Depends(_require_any)):
    cpage_size = cpage_size if cpage_size in (10, 20, 50, 100) else 20
    is_adm = _is_admin_user(request)
    try:
        html = _render_check_page(cpage=cpage, cpage_size=cpage_size,
                                  csubject=csubject, cname=cname,
                                  is_admin=is_adm, current_user=user)
        return HTMLResponse(html)
    except Exception as e:
        logger.error("渲染预检查页失败: %s", e)
        return PlainTextResponse(f"Internal error: {e}", status_code=500)


@app.get("/admin/settings")
async def admin_settings(user: str = Depends(_require_admin_dep)):
    try:
        html = _render_settings_page(current_user=user)
        return HTMLResponse(html)
    except Exception as e:
        logger.error("渲染系统配置页失败: %s", e)
        return PlainTextResponse(f"Internal error: {e}", status_code=500)


@app.get("/admin/envvars")
async def admin_envvars(request: Request, user: str = Depends(_require_any)):
    is_adm = _is_admin_user(request)
    try:
        html = _render_envvars_page(is_admin=is_adm, current_user=user)
        return HTMLResponse(html)
    except Exception as e:
        logger.error("渲染环境变量页失败: %s", e)
        return PlainTextResponse(f"Internal error: {e}", status_code=500)


@app.get("/admin/about")
async def admin_about(request: Request, user: str = Depends(_require_any)):
    is_adm = _is_admin_user(request)
    try:
        html = _render_about_page(is_admin=is_adm, current_user=user)
        return HTMLResponse(html)
    except Exception as e:
        logger.error("渲染系统介绍页失败: %s", e)
        return PlainTextResponse(f"Internal error: {e}", status_code=500)


@app.get("/admin/logs")
async def admin_logs(request: Request, lpage: int = 1, lusername: str = "",
                     laction: str = "", lpage_size: int = 50,
                     user: str = Depends(_require_admin_dep)):
    lpage_size = lpage_size if lpage_size in (20, 50, 100, 200) else 50
    try:
        html = _render_logs_page(lpage=lpage, lpage_size=lpage_size,
                                 lusername=lusername, laction=laction, current_user=user)
        return HTMLResponse(html)
    except Exception as e:
        logger.error("渲染操作日志页失败: %s", e)
        return PlainTextResponse(f"Internal error: {e}", status_code=500)


@app.get("/admin/precheck-scripts")
async def admin_precheck_scripts(request: Request, user: str = Depends(_require_any)):
    is_adm = _is_admin_user(request)
    try:
        html = _render_scripts_page("precheck", is_admin=is_adm, current_user=user)
        return HTMLResponse(html)
    except Exception as e:
        logger.error("渲染预检查脚本页失败: %s", e)
        return PlainTextResponse(f"Internal error: {e}", status_code=500)


@app.get("/admin/process-scripts")
async def admin_process_scripts(request: Request, user: str = Depends(_require_any)):
    is_adm = _is_admin_user(request)
    try:
        html = _render_scripts_page("process", is_admin=is_adm, current_user=user)
        return HTMLResponse(html)
    except Exception as e:
        logger.error("渲染处理脚本页失败: %s", e)
        return PlainTextResponse(f"Internal error: {e}", status_code=500)


@app.get("/logout")
async def logout():
    return Response(
        content="<!DOCTYPE html><html lang=\"zh\"><head><meta charset=\"utf-8\"></head>"
                "<body style=\"font-family:sans-serif;text-align:center;padding-top:120px\">"
                "<h2>已退出</h2><p><a href=\"/admin\" style=\"color:#1a73e8\">点击重新登录</a></p>"
                "</body></html>",
        status_code=401,
        headers={"WWW-Authenticate": 'Basic realm="AiOps"',
                 "Content-Type": "text/html; charset=utf-8"},
    )


# -- GET /api/{precheck,process}-scripts/get ----------------------------------

@app.get("/api/precheck-scripts/get")
@app.get("/api/process-scripts/get")
async def get_script_api(request: Request, name: str = "",
                         user: str = Depends(_require_any)):
    script_type = "precheck" if "precheck" in str(request.url) else "process"
    name = name.strip()
    if not name:
        return JSONResponse({"ok": False, "error": "缺少 name 参数"}, status_code=400)
    from services.db import get_precheck_script, get_process_script
    fn = get_precheck_script if script_type == "precheck" else get_process_script
    row = fn(name)
    if not row:
        return JSONResponse({"ok": False, "error": "脚本不存在"}, status_code=404)
    return JSONResponse({"ok": True, "data": row})


# -- POST /api/restart --------------------------------------------------------

@app.post("/api/restart")
async def api_restart(request: Request, user: str = Depends(_require_admin_dep)):
    _log_admin_action(user, request, "restart", "直接重启服务")
    import sys as _sys, asyncio as _asyncio
    async def _do_restart():
        await _asyncio.sleep(0.1)
        os.execv(_sys.executable, [_sys.executable] + _sys.argv)
    _asyncio.ensure_future(_do_restart())
    return JSONResponse({"ok": True, "message": "restarting"})


# -- POST /api/settings/save --------------------------------------------------

@app.post("/api/settings/save")
async def api_settings_save(request: Request, user: str = Depends(_require_admin_dep)):
    try:
        body = await request.json()
    except Exception as e:
        return JSONResponse({"ok": False, "error": f"JSON 解析失败: {e}"}, status_code=400)
    try:
        from services.db import set_setting
        keys_saved = list(body.keys())
        for key, value in body.items():
            set_setting(f"config:{key}", value)
        _log_admin_action(user, request, "save_settings", f"keys={','.join(keys_saved)}")
        return JSONResponse({"ok": True})
    except Exception as e:
        logger.error("保存配置失败: %s", e)
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


# -- POST /api/groups/{chat_id}/dissolve --------------------------------------

@app.post("/api/groups/{chat_id}/dissolve")
async def api_dissolve_group(chat_id: str, request: Request, user: str = Depends(_require_any)):
    from services.chat import dissolve_group
    from services.db import dissolve_proc_task_by_chat, get_proc_task_by_chat
    from services.worker_bot import get_bot_open_id as _get_bot_open_id
    record = get_proc_task_by_chat(chat_id)
    if not record:
        return JSONResponse({"ok": False, "error": "群不存在"}, status_code=404)
    if record.get("is_dissolved"):
        return JSONResponse({"ok": False, "error": "群已经解散"}, status_code=400)
    try:
        mgr = _user_token.get_instance()
        user_token = (mgr._access_token if mgr else "") or ""
        dissolve_group(chat_id, user_token=user_token, bot_open_id=_get_bot_open_id())
        dissolve_proc_task_by_chat(chat_id)
        _log_admin_action(user, request, "dissolve_group",
                          f"chat_id={chat_id} group={record.get('group_name', '')}")
        return JSONResponse({"ok": True})
    except Exception as e:
        err = str(e)
        logger.error("手动解散群失败 chat_id=%s: %s", chat_id, e)
        need_reauth = "99991679" in err or "im:chat" in err
        return JSONResponse({"ok": False, "error": err, "need_reauth": need_reauth}, status_code=500)


# -- POST /api/tasks/{instance_code}/retry ------------------------------------

@app.post("/api/tasks/{instance_code}/retry")
async def api_retry_task(instance_code: str, request: Request, user: str = Depends(_require_any)):
    try:
        from handlers.process import retry_proc_task
        retry_proc_task(instance_code)
        _log_admin_action(user, request, "retry_task", f"instance_code={instance_code}")
        return JSONResponse({"ok": True})
    except Exception as e:
        logger.error("任务重试失败 instance_code=%s: %s", instance_code, e)
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/check-tasks/{instance_code}/retry")
async def api_retry_check_task(instance_code: str, request: Request,
                                user: str = Depends(_require_any)):
    try:
        from handlers.precheck import retry_precheck
        retry_precheck(instance_code)
        _log_admin_action(user, request, "retry_check", f"instance_code={instance_code}")
        return JSONResponse({"ok": True})
    except Exception as e:
        logger.error("预检查重试失败 instance_code=%s: %s", instance_code, e)
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/notify/send")
async def api_notify_send(request: Request, user: str = Depends(_require_any)):
    try:
        body = await request.json()
    except Exception as e:
        return JSONResponse({"ok": False, "error": f"请求体解析失败: {e}"}, status_code=400)
    try:
        from services.notify import send_feishu_message
        result = send_feishu_message(
            receiver_ids=body.get("receiver_ids") or [],
            receiver_id_type=body.get("receiver_id_type", "open_id"),
            title=body.get("title", ""),
            content=body.get("content", ""),
            template=body.get("template", "blue"),
        )
        s = 200 if result["ok"] else 207
        return JSONResponse(result, status_code=s)
    except Exception as e:
        logger.error("发送飞书消息失败: %s", e)
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


# -- POST /api/{precheck,process}-scripts/{action} ----------------------------

async def _debug_script_handler(script_type: str, body: dict) -> JSONResponse:
    import contextlib, io, traceback, types as _types
    script_name = (body.get("script_name") or "debug").strip()
    code = body.get("code")
    applicant = body.get("applicant", {})
    form = body.get("form", {})
    if not code:
        from services.db import get_precheck_script, get_process_script
        fn = get_precheck_script if script_type == "precheck" else get_process_script
        row = fn(script_name)
        if not row:
            return JSONResponse({"ok": False, "error": "脚本不存在且未提供代码"}, status_code=404)
        code = row["code"]
    if not code.strip():
        return JSONResponse({"ok": False, "error": "代码不能为空"}, status_code=400)
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    result = None
    error = None
    try:
        from services.db import get_script_envvars_dict
        mod = _types.ModuleType(f"_debug_{script_name}")
        mod.__dict__["ENV"] = get_script_envvars_dict()
        exec(compile(code, f"{script_name}.py", "exec"), mod.__dict__)
        with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
            if script_type == "precheck":
                if hasattr(mod, "check"):
                    result = mod.check(applicant, form)
                else:
                    error = "脚本无 check 函数"
            else:
                if hasattr(mod, "run"):
                    result = mod.run(applicant, form)
                else:
                    error = "脚本无 run 函数"
    except Exception:
        error = traceback.format_exc()
    format_warning = None
    if script_type == "precheck" and error is None:
        if not (isinstance(result, tuple) and len(result) == 2
                and isinstance(result[0], bool) and isinstance(result[1], str)):
            format_warning = (f"返回格式不符合要求！期望 tuple[bool, str]，"
                              f"实际得到 {type(result).__name__}: {result!r}")
    resp = {
        "ok": error is None and format_warning is None,
        "result": (result if isinstance(result, (list, tuple, dict, str, int, float, bool, type(None)))
                   else str(result)),
        "stdout": stdout_buf.getvalue(),
        "stderr": stderr_buf.getvalue(),
        "error": error,
        "format_warning": format_warning,
    }
    return JSONResponse(resp)


async def _handle_script_api(script_type: str, action: str, body: dict,
                              request: Request, user: str):
    from services.db import (
        upsert_precheck_script, upsert_process_script,
        delete_precheck_script, delete_process_script,
        get_precheck_script, get_process_script,
    )
    if action == "create":
        name = (body.get("name") or "").strip()
        code = body.get("code", "")
        enabled = int(body.get("enabled", 1))
        if not name:
            return JSONResponse({"ok": False, "error": "名称不能为空"}, status_code=400)
        get_fn = get_precheck_script if script_type == "precheck" else get_process_script
        if get_fn(name) is not None:
            return JSONResponse(
                {"ok": False, "error": f"脚本「{name}」已存在，请使用编辑功能修改"},
                status_code=409)
        fn = upsert_precheck_script if script_type == "precheck" else upsert_process_script
        fn(name, code, enabled)
        _log_admin_action(user, request, f"{script_type}_create", f"name={name}")
        return JSONResponse({"ok": True})
    elif action == "edit":
        name = (body.get("name") or "").strip()
        code = body.get("code", "")
        enabled = int(body.get("enabled", 1))
        if not name:
            return JSONResponse({"ok": False, "error": "名称不能为空"}, status_code=400)
        fn = upsert_precheck_script if script_type == "precheck" else upsert_process_script
        fn(name, code, enabled, username=user)
        _log_admin_action(user, request, f"{script_type}_edit", f"name={name}")
        return JSONResponse({"ok": True})
    elif action == "delete":
        name = (body.get("name") or "").strip()
        if not name:
            return JSONResponse({"ok": False, "error": "名称不能为空"}, status_code=400)
        fn = delete_precheck_script if script_type == "precheck" else delete_process_script
        fn(name)
        _log_admin_action(user, request, f"{script_type}_delete", f"name={name}")
        return JSONResponse({"ok": True})
    elif action == "debug":
        return await _debug_script_handler(script_type, body)
    elif action == "history":
        name = (body.get("name") or "").strip()
        if not name:
            return JSONResponse({"ok": False, "error": "缺少 name"}, status_code=400)
        from services.db import list_script_history
        rows = list_script_history(script_type, name)
        return JSONResponse({"ok": True, "data": rows})
    elif action == "rollback":
        history_id = body.get("history_id")
        if not history_id:
            return JSONResponse({"ok": False, "error": "缺少 history_id"}, status_code=400)
        from services.db import get_script_history_item
        item = get_script_history_item(int(history_id))
        if not item:
            return JSONResponse({"ok": False, "error": "历史记录不存在"}, status_code=404)
        fn = upsert_precheck_script if script_type == "precheck" else upsert_process_script
        fn(item["name"], item["code"], item["enabled"], username=user)
        _log_admin_action(user, request, f"{script_type}_edit",
                          f"rollback name={item['name']} from history_id={history_id}")
        return JSONResponse({"ok": True})
    else:
        return PlainTextResponse("Not Found", status_code=404)


@app.post("/api/precheck-scripts/{action}")
async def api_precheck_scripts(action: str, request: Request, user: str = Depends(_require_any)):
    try:
        body = await request.json()
    except Exception as e:
        return JSONResponse({"ok": False, "error": f"JSON 解析失败: {e}"}, status_code=400)
    try:
        return await _handle_script_api("precheck", action, body, request, user)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.post("/api/process-scripts/{action}")
async def api_process_scripts(action: str, request: Request, user: str = Depends(_require_any)):
    try:
        body = await request.json()
    except Exception as e:
        return JSONResponse({"ok": False, "error": f"JSON 解析失败: {e}"}, status_code=400)
    try:
        return await _handle_script_api("process", action, body, request, user)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


# -- POST /api/envvars/{action} -----------------------------------------------

@app.post("/api/envvars/{action}")
async def api_envvars(action: str, request: Request, user: str = Depends(_require_admin_dep)):
    try:
        body = await request.json()
    except Exception as e:
        return JSONResponse({"ok": False, "error": f"JSON 解析失败: {e}"}, status_code=400)
    from services.db import (upsert_script_envvar, delete_script_envvar,
                              update_script_envvar_desc, list_script_envvars)
    try:
        if action == "create":
            key = (body.get("key") or "").strip()
            desc = (body.get("desc") or "").strip()
            value = body.get("value") or ""
            if not key:
                return JSONResponse({"ok": False, "error": "key 不能为空"}, status_code=400)
            existing_keys = {r["key"] for r in list_script_envvars()}
            if key in existing_keys:
                return JSONResponse(
                    {"ok": False, "error": f"变量「{key}」已存在，请在列表中点击编辑修改"},
                    status_code=409)
            upsert_script_envvar(key, desc, value)
            _log_admin_action(user, request, "envvar_create", f"key={key}")
            return JSONResponse({"ok": True})
        elif action == "edit":
            key = (body.get("key") or "").strip()
            desc = (body.get("desc") or "").strip()
            value = body.get("value")
            if not key:
                return JSONResponse({"ok": False, "error": "key 不能为空"}, status_code=400)
            if value:
                upsert_script_envvar(key, desc, value)
            else:
                update_script_envvar_desc(key, desc)
            _log_admin_action(user, request, "envvar_edit", f"key={key}")
            return JSONResponse({"ok": True})
        elif action == "delete":
            key = (body.get("key") or "").strip()
            if not key:
                return JSONResponse({"ok": False, "error": "key 不能为空"}, status_code=400)
            delete_script_envvar(key)
            _log_admin_action(user, request, "envvar_delete", f"key={key}")
            return JSONResponse({"ok": True})
        else:
            return PlainTextResponse("Not Found", status_code=404)
    except Exception as e:
        logger.error("环境变量操作失败: %s", e)
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


# ---------------------------------------------------------------------------
# 启动入口
# ---------------------------------------------------------------------------

_uvicorn_server = None  # 供外部 signal handler 调用 should_exit


def run_http_server() -> None:
    """启动 HTTP 服务（uvicorn）。"""
    import asyncio
    import uvicorn
    global _uvicorn_server

    config = uvicorn.Config(app, host="0.0.0.0", port=HTTP_PORT, log_level="warning")
    server = uvicorn.Server(config)
    # 禁用 uvicorn 自带的信号处理——由 main.py 的 _graceful_shutdown 统一管理
    server.install_signal_handlers = lambda: None  # type: ignore[method-assign]
    _uvicorn_server = server

    logger.info("HTTP 服务已启动 (uvicorn FastAPI) -> http://localhost:%d", HTTP_PORT)
    logger.info("  授权登录  : http://localhost:%d/auth",   HTTP_PORT)
    logger.info("  健康检查  : http://localhost:%d/health", HTTP_PORT)
    logger.info("  管理页面  : http://localhost:%d/admin",  HTTP_PORT)
    asyncio.run(server.serve())
