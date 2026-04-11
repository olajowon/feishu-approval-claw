import os
import sqlite3
from dotenv import load_dotenv

load_dotenv()

# == 文件路径（最先定义，其他模块依赖） ==========================================
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
ENV_FILE     = os.path.join(PROJECT_ROOT, ".env")
DATA_DIR     = os.path.join(PROJECT_ROOT, "data")
DB_FILE      = os.path.join(DATA_DIR, "data.db")


# ── settings 表读取（轻量级，不依赖 services/db.py 避免循环引用） ───────────────

def _load_all_settings() -> dict[str, str]:
    """一次性从 SQLite settings 表读取所有 config: 前缀的配置，DB 不存在时返回空字典。"""
    if not os.path.exists(DB_FILE):
        return {}
    try:
        con = sqlite3.connect(DB_FILE)
        rows = con.execute(
            "SELECT key, value FROM settings WHERE key LIKE 'config:%'"
        ).fetchall()
        con.close()
        return {row[0].removeprefix("config:"): row[1] for row in rows}
    except Exception:
        return {}


_settings_cache: dict[str, str] = _load_all_settings()


def _get_setting(key: str) -> str | None:
    """从缓存中读取配置值。"""
    return _settings_cache.get(key)


def _cfg(key: str, default: str = "") -> str:
    """配置优先级：settings 表 → 环境变量 → 默认值。"""
    val = _get_setting(key)
    if val is not None:
        return val
    return os.environ.get(key, default)


def get_missing_configs(keys: list[str] | tuple[str, ...]) -> list[str]:
    """返回当前未配置的键列表（settings + env 均为空）。"""
    return [key for key in keys if not _cfg(key)]


def _cfg_list(key: str, default: str = "") -> list:
    """逗号分隔的配置值 → list。"""
    raw = _cfg(key, default)
    return [v.strip() for v in raw.split(",") if v.strip()]


# ── 页面可配置项元数据（不含 ADMIN_USER/ADMIN_PASS/HTTP_PORT） ──────────────────
# (key, desc_zh, desc_en, is_secret)
CONFIG_META: list[tuple[str, str, str, bool]] = [
    # ── 飞书应用配置 ──────────────────────────────────────────────────────────
    ("APP_ID",
     "主应用 App ID。在飞书开发者后台（developer.feishu.cn）创建企业应用后获取。"
     "用于连接飞书开放平台、接收审批事件、发起 OAuth 授权。未配置时系统只启动管理后台。"
     "<br>需要开通的<b>权限</b>：approval:approval、approval:approval:subscribe、"
     "im:message:send_as_bot、im:chat:create、im:chat.group.member:add、contact:user.base:readonly。"
     "<br>需要订阅的<b>事件</b>：审批 — 审批任务（P1 格式，approval_instance）。",
     "Main app App ID. Obtain from the Lark developer console (developer.feishu.cn) after creating an enterprise app. "
     "Used to connect to the Lark Open Platform, receive approval events, and initiate OAuth authorization. "
     "System starts in admin-only mode when not configured."
     "<br>Required <b>permissions</b>: approval:approval, approval:approval:subscribe, "
     "im:message:send_as_bot, im:chat:create, im:chat.group.member:add, contact:user.base:readonly."
     "<br>Required <b>event</b>: Approval — Approval Task (P1 format, approval_instance).",
     False),
    ("APP_SECRET",
     "主应用 App Secret，与 APP_ID 配套。用于获取 tenant_access_token、建立 WebSocket 长连接和调用开放平台接口。",
     "Main app App Secret, paired with APP_ID. Used to obtain tenant_access_token, establish WebSocket connection, and call Open Platform APIs.",
     True),
    ("REDIRECT_URI",
     "OAuth 回调地址，用户完成 /auth 授权后飞书会跳回此地址（通常为 http://host:port/callback）。"
     "系统通过此流程获取管理员的用户级 access_token，用于代表真实用户发送消息、创建/解散群组。",
     "OAuth callback URL. After completing /auth authorization, Lark redirects to this URL (typically http://host:port/callback). "
     "The system uses this flow to obtain the admin's user-level access_token for sending messages and creating/dissolving groups.",
     False),
    ("FEISHU_HOST",
     "飞书开放平台域名。公有云默认 https://open.feishu.cn；私有化部署时改为对应的自定义域名。",
     "Lark Open Platform domain. Default https://open.feishu.cn for public cloud; change to custom domain for private deployments.",
     False),
    # ── 飞书审批配置 ──────────────────────────────────────────────────────────
    ("APPROVAL_CODES",
     "需要监听的审批定义 code 列表，多个值用英文逗号分隔。"
     "在飞书审批管理后台的「审批定义」列表中可复制 code；不配置则系统不会自动处理任何审批。",
     "Approval definition code list to monitor, separated by commas. "
     "Copy the code from the 'Approval Definitions' list in Lark admin. No approvals will be processed if left empty.",
     False),
    ("PRE_CHECK_NODE_NAME",
     '预检查审批节点名称。系统在审批任务列表中按此名称查找需要自动预检查的节点，默认值为「预检查」。'
     '与飞书审批流程设计中的节点名称保持一致即可。',
     "Pre-check approval node name. The system looks for nodes with this name in the approval task list. "
     'Default is "预检查". Must match the node name in the Lark approval flow design.',
     False),
    # ── 飞书群配置 ────────────────────────────────────────────────────────────
    ("WORKER_BOT_APP_ID",
     "Openclaw Bot 的 App ID。Openclaw Bot 是工单群中的核心处理机器人，负责接收指令、执行工单任务。"
     "本字段用于获取 Openclaw Bot 的 open_id，以便在群消息中 @机器人触发自动处理。",
     "Openclaw Bot App ID. The core processing bot in task groups, responsible for receiving commands and executing tasks. "
     "Used to obtain the bot's open_id for @mention triggering in group messages.",
     False),
    ("WORKER_BOT_APP_SECRET",
     "Openclaw Bot 的 App Secret，与 Openclaw Bot App ID 配套使用。",
     "Openclaw Bot App Secret, paired with the Openclaw Bot App ID.",
     True),
    ("WORKER_BOT_ADMIN_ID",
     "Openclaw Bot 指令授权人。建群后系统指令中只有此用户发出的指令会被 Bot 接受，避免群内其他成员操控。"
     "支持 <code>open_id</code>（ou_ 开头）、<b>邮箱</b>（含 @）或<b>手机号</b>（纯数字）；"
     "非 open_id 格式会在启动时通过 Openclaw Bot 应用的 tenant_access_token 自动转换。留空则不发送受限模式指令。",
     "Openclaw Bot command authorizer. Only commands from this user will be accepted by the Bot in groups. "
     "Supports <code>open_id</code> (ou_ prefix), <b>email</b> (contains @), or <b>phone number</b> (digits only); "
     "non-open_id formats are auto-resolved at startup. Leave empty to skip restricted mode commands.",
     False),
    ("WORKER_USER_IDS",
     "默认处理人列表，系统自动建群时会将这些人拉入群，多个值用英文逗号分隔。"
     "支持三种格式：<code>open_id</code>（ou_ 开头）、<b>邮箱</b>（含 @）、<b>手机号</b>（纯数字）；"
     "非 open_id 格式会在启动时通过飞书 API 自动转换，无需手动查询。",
     "Default handler list. These users are added to auto-created groups. Separate multiple values with commas. "
     "Supports three formats: <code>open_id</code> (ou_ prefix), <b>email</b> (contains @), <b>phone number</b> (digits only); "
     "non-open_id formats are auto-resolved via Lark API at startup.",
     False),
    ("WORKER_ADMIN_ID",
     "代理操作人，用途：①自动创建处理群时设为群主；②预检查节点自动审批/退回时作为操作身份（需具备审批操作权限）。"
     "同样支持 <code>open_id</code>、<b>邮箱</b>或<b>手机号</b>格式，启动时自动解析。",
     "Proxy operator. Used as: ① group owner when auto-creating processing groups; ② operator identity for pre-check node auto-approve/reject (must have approval permissions). "
     "Also supports <code>open_id</code>, <b>email</b>, or <b>phone number</b> formats, auto-resolved at startup.",
     False),
    ("GROUP_TTL_DAYS",
     "处理群自动解散保留天数。仅对系统自动创建的处理群生效；超过天数后，定时任务会自动尝试解散该群。",
     "Processing group auto-dissolve retention days. Only applies to system-created groups; groups are automatically dissolved after this many days.",
     False),
    # ── 运维配置 ──────────────────────────────────────────────────────────────
    ("ALERT_WEBHOOK",
     "告警 Webhook 地址。预检查或处理流程发生错误时，系统向此飞书机器人 Webhook 推送告警消息；留空则不推送。",
     "Alert Webhook URL. When pre-check or processing errors occur, the system sends alerts to this Lark bot Webhook. Leave empty to disable.",
     False),
]


# == 主应用 ====================================================================
APP_ID     = _cfg("APP_ID")
APP_SECRET = _cfg("APP_SECRET")

# == Worker 机器人 =============================================================
WORKER_BOT_APP_ID     = _cfg("WORKER_BOT_APP_ID")
WORKER_BOT_APP_SECRET = _cfg("WORKER_BOT_APP_SECRET")
WORKER_USER_IDS: list = _cfg_list("WORKER_USER_IDS")
WORKER_ADMIN_ID: str     = _cfg("WORKER_ADMIN_ID")
WORKER_BOT_ADMIN_ID: str = _cfg("WORKER_BOT_ADMIN_ID")

# == 审批配置 ==================================================================
APPROVAL_CODES: list = _cfg_list("APPROVAL_CODES")
FORM_FIELD_NAME: str = "申请事项"  # 隐藏兼容字段名，不对外暴露
PRE_CHECK_NODE_NAME: str = _cfg("PRE_CHECK_NODE_NAME", "预检查")

# == 群管理 ====================================================================
FEISHU_HOST  = _cfg("FEISHU_HOST", "https://open.feishu.cn")
REDIRECT_URI = _cfg("REDIRECT_URI")
HTTP_PORT    = int(os.environ.get("HTTP_PORT", "9999"))  # 仅从 .env 读取

# == 管理页 Basic Auth（仅从 .env 读取，不上页面）================================
ADMIN_USER = os.environ.get("ADMIN_USER", "")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "")

# 只读账号：可查看记录/自定义脚本/系统介绍，不可操作环境变量和重新授权
# 格式：用户名1:密码,用户名2:密码
def _parse_accounts(raw: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for entry in raw.split(","):
        entry = entry.strip()
        if ":" in entry:
            u, _, p = entry.partition(":")
            if u and p:
                result[u.strip()] = p.strip()
    return result

ACCOUNTS: dict[str, str] = _parse_accounts(os.environ.get("ACCOUNTS", ""))

# == 告警 Webhook =============================================================
ALERT_WEBHOOK = _cfg("ALERT_WEBHOOK", "")

# == 群管理 ====================================================================
GROUP_TTL_DAYS = int(_cfg("GROUP_TTL_DAYS", "3"))
