<p align="center">
  <img src="docs/logo.svg" width="80" height="80" alt="Logo">
</p>
<h1 align="center">飞书审批Claw</h1>

> 通过 WebSocket 长连接实时监听飞书审批事件，自动完成**预检查 → 审批通过 → 建处理群 → @Openclaw Bot自动办理 （或编写低代码脚本处理）**的全链路审批自动化。

---

## 核心设计：审批 → 处理群 → Openclaw 自动办理

```
用户在飞书提交审批
        ↓
审批流到达「预检查」节点
        ↓  自动执行预检查脚本（Python）
        ↓  (True, ...)  → 节点自动通过
        ↓  (False, ...) → 节点自动退回，退回原因写入飞书备注
        ↓
审批最终通过
        ↓
按「申请事项」匹配处理脚本
        ├─ 有处理脚本 → 执行脚本处理（Python，可对接 n8n / Dify 等工作流）
        └─ 无处理脚本 → 自动建飞书处理群
                            ├─ 拉入处理人（WORKER_USER_IDS）
                            ├─ 拉入 Openclaw Bot（WORKER_BOT_APP_ID）
                            └─ 发送结构化 @ 消息 → Openclaw Bot 触发 Skill 自动处理
```

<!-- TODO: 替换为实际截图 -->
![处理群 @Openclaw Bot 自动办理](docs/screenshots/openclaw-bot-group.png)

---

## 功能概览

| 功能 | 说明 |
|------|------|
| **预检查自动化** | 审批到「预检查」节点时执行脚本，自动通过或退回，无需人工操作 |
| **处理群自动化** | 审批通过无脚本时，自动建群、拉人、@Openclaw Bot |
| **自定义处理脚本** | 按「申请事项」匹配执行 Python 脚本，几行代码即可对接 n8n、Dify 等外部工作流 |
| **脚本在线编辑** | 后台语法高亮编辑 + 实时传参调试，新增/编辑分离防覆盖 |
| **环境变量管理** | 后台配置 KV，脚本执行时自动注入为 `ENV` 字典，集中管理密钥/参数 |
| **操作记录** | 所有管理操作自动入库，含操作类型、用户名、IP、详情、时间 |
| **配置热更新** | 所有配置项可在后台修改，「保存并重启」一键生效 |
| **Token 自动续期** | 定时巡检用户 access_token，剩余 < 30 分钟时自动刷新 |

---

## 系统架构

```
飞书审批平台
    ↓ WebSocket 长连接（approval_instance P1 事件，无需公网回调）
main.py ── 入口：初始化各组件、订阅审批事件、启动 WebSocket + HTTP 服务
    │
    ├─ handlers/                     ── 审批事件处理
    │   ├─ approval.py               ── 事件路由（分发预检查 / 处理流程）
    │   ├─ precheck.py               ── 预检查节点：执行脚本 → 自动通过/退回
    │   └─ process.py                ── 审批通过：执行脚本 或 建群 + @Openclaw Bot
    │
    ├─ services/                     ── 基础服务层
    │   ├─ db.py                     ── SQLite 数据层（WAL 模式，7 张表）
    │   ├─ chat.py                   ── 飞书 IM（建群 / 拉人 / @Bot / 解散群）
    │   ├─ approval.py               ── 审批实例详情拉取 + 表单解析
    │   ├─ user_token.py             ── 用户 OAuth token（持久化 + 自动刷新 + 线程安全）
    │   ├─ user_profile.py           ── 用户资料查询（email/手机号 → open_id 解析）
    │   ├─ lark_client.py            ── 主应用 lark.Client 单例
    │   ├─ worker_bot.py             ── Openclaw Bot lark.Client 单例 + bot open_id
    │   └─ notify.py                 ── 飞书消息发送（脚本内可调用）
    │
    ├─ web/server.py                 ── 管理后台 HTTP 服务（FastAPI + uvicorn）
    │   ├─ /admin 路由（8 个 Tab）
    │   └─ /auth + /callback         ── 飞书 OAuth 2.0 授权
    │
    ├─ scheduler/                    ── 后台定时任务
    │   ├─ 群 TTL 清理（每小时）       ── 解散超期处理群
    │   └─ Token 巡检（每 10 分钟）    ── access_token 剩余 < 30 分钟自动 refresh
    │
    └─ data/                         ── 数据持久化（SQLite，Docker 挂载）
```

### 数据库表

| 表名 | 说明 |
|------|------|
| `proc_tasks` | 处理任务记录（建群状态、脚本执行结果） |
| `check_tasks` | 预检查记录（脚本执行结果、通过/退回原因） |
| `precheck_scripts` | 预检查脚本（name, code, enabled） |
| `process_scripts` | 处理脚本（name, code, enabled） |
| `script_envvars` | 环境变量（key, desc, value, updated_at） |
| `settings` | 系统配置（key-value，优先于 .env） |
| `admin_logs` | 管理员操作日志（username, ip, action, detail, created_at） |

---

## 管理后台

> 访问 `http://localhost:9999/admin`（Basic Auth）

<!-- TODO: 替换为实际截图 -->

**处理记录**
![处理记录](docs/screenshots/process-records.png)

**自定义脚本**
![自定义脚本](docs/screenshots/scripts.png)

**系统配置**
![系统配置](docs/screenshots/settings.png)

| Tab | 权限 | 功能 |
|-----|------|------|
| 处理记录 | 全部用户 | 处理历史、脚本执行结果，支持手动重试和解散群 |
| 预检查记录 | 全部用户 | 预检查执行历史、通过/退回原因、错误详情 |
| 自定义处理脚本 | 全部用户 | 新增/编辑处理脚本，语法高亮 + 实时调试 |
| 自定义预检查脚本 | 全部用户 | 新增/编辑预检查脚本，验证返回值格式 |
| 环境变量 | 全部用户 | 管理脚本运行时可用的 KV 环境变量 |
| 系统配置 | 仅 admin | 所有配置项，「保存并重启」一键生效 |
| 操作记录 | 仅 admin | 所有管理操作的完整审计日志 |
| 系统介绍 | 全部用户 | 功能说明、架构图、脚本编写指南 |

---

## 快速开始

### 1. 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 最小配置（.env）

```env
# 管理后台 Basic Auth（仅从 .env 读取，不存数据库）
ADMIN_USER=admin
ADMIN_PASS=your_password

# 普通用户账号（可选，格式：用户名:密码,用户名:密码）
# ACCOUNTS=ops:pass1,dev:pass2

# HTTP 端口（可选，默认 9999）
HTTP_PORT=9999
```

其余所有配置均可在管理后台「系统配置」页面填写和保存。

### 3. 启动

```bash
python main.py
```

或使用 Docker：

```bash
cp .env.example .env
# 编辑 .env 填写配置
docker compose up -d
```

- 缺少核心配置（APP_ID / APP_SECRET）时自动进入**管理后台模式**
- 访问 `http://localhost:9999/admin` 完成配置，「保存并重启」后系统建立飞书 WebSocket 长连接

### 4. 飞书 OAuth 授权

访问 `http://localhost:9999/auth` 完成 OAuth 2.0 授权，获取**用户级 token**（用于发消息、建群、解散群）。授权后无需重启即生效。

---

## 飞书应用配置要求

> 使用 **WebSocket 长连接**接收事件，无需在飞书后台配置回调 URL，在开发者后台开启「长连接接收事件」即可。

### 主应用权限

| 权限标识 | 用途 |
|----------|------|
| `approval:approval` | 读取审批定义 |
| `approval:approval:subscribe` | 订阅审批事件 |
| `im:message:send_as_bot` | 发送群消息 |
| `im:chat:create` | 创建处理群 |
| `im:chat.group.member:add` | 拉处理人和 Bot 入群 |
| `contact:user.base:readonly` | 读取申请人信息 |

### 需要订阅的事件

| 事件 | 格式 | 作用 |
|------|------|------|
| 审批任务 | P1 `approval_instance` | 实时接收审批状态变更，触发预检查和处理 |

---

## 脚本编写规范

### 预检查脚本

**触发时机**：审批流到达与脚本名称同名的节点（`PRE_CHECK_NODE_NAME`，默认「预检查」）。

```python
# ENV 为系统自动注入的环境变量字典（在「环境变量」Tab 中配置）
# api_key = ENV.get("MY_API_KEY", "")

def check(applicant: dict, form: dict) -> tuple[bool, str]:
    """
    applicant: {"name": "张三", "open_id": "...", "email": "...", ...}
    form:      {"申请事项": "...", "申请原因": "...", ...}
    返回: (True, "") 通过  |  (False, "退回原因") 退回
    """
    if not form.get("申请原因", "").strip():
        return False, "申请原因不能为空"
    return True, ""
```

### 处理脚本（低代码）

**触发时机**：审批通过后，「申请事项」与脚本名称**完全匹配**时执行，优先于默认建群逻辑。几行代码即可对接 n8n、Dify 等外部工作流平台，或调用任意 API 完成自动化处理。

```python
import logging
from services.notify import send_feishu_message

logger = logging.getLogger(__name__)

# ENV 为系统自动注入的环境变量字典（在「环境变量」Tab 中配置）
# api_key = ENV.get("MY_API_KEY", "")

def run(applicant: dict, form: dict) -> str:
    """
    返回 str 写入处理记录的 extra_info；抛出异常将状态标记为 error 可重试
    """
    name    = applicant.get("name", "")
    open_id = applicant.get("open_id", "")
    send_feishu_message(
        receiver_ids=[open_id],
        receiver_id_type="open_id",
        title="✅ 申请已处理",
        content="您的申请已完成自动处理。",
    )
    return f"处理完成，已通知 {name}"
```

**对接外部工作流示例**（n8n / Dify 等，只需几行代码）：

```python
import requests

def run(applicant: dict, form: dict) -> str:
    # 触发 n8n Webhook，将审批数据推送到外部工作流
    requests.post(ENV.get("N8N_WEBHOOK_URL"), json={
        "applicant": applicant["name"],
        "subject": form.get("申请事项", ""),
        "form": form,
    }, timeout=30)
    return "已触发 n8n 工作流"
```

### 环境变量（ENV）

在管理后台「**环境变量**」Tab 中配置的 KV，会在脚本执行时自动注入为 `ENV` 字典，适合存放 API 密钥、账号信息等敏感参数，无需硬编码在脚本中。

```python
# 脚本内直接使用，无需 import
api_key  = ENV.get("MY_API_KEY", "")
base_url = ENV.get("API_BASE_URL", "https://example.com")
```

---

## 设计原则

- **轻量部署**：HTTP 服务基于 FastAPI + uvicorn，数据库用 SQLite，无需外部中间件
- **配置三级优先级**：数据库 > `.env` > 默认值，后台修改优先级最高
- **无配置可启动**：缺少核心配置时仍可进入管理后台在线完成初始化
- **脚本隔离执行**：每次在独立 `types.ModuleType` 命名空间中执行，互不污染
- **新增/编辑分离**：API 明确区分 `/create`（含重名检测）和 `/edit`，防止意外覆盖
- **WebSocket 长连接**：无需公网回调地址，内网部署即可接收飞书事件
