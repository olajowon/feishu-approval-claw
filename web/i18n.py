"""
web/i18n.py — 国际化翻译模块。

提供中/英文翻译字典、t() 查找函数、JS 翻译注入、about 页面 HTML 块。
"""

# ---------------------------------------------------------------------------
# 翻译字典
# ---------------------------------------------------------------------------

_ZH = {
    # ── 导航 ──
    "nav.process_records":         "处理记录",
    "nav.precheck_records":        "预检查记录",
    "nav.process_scripts":         "处理脚本",
    "nav.precheck_scripts":        "预检查脚本",
    "nav.option_callback_scripts": "选项回调脚本",
    "nav.envvars":                 "环境变量",
    "nav.settings":                "系统配置",
    "nav.logs":                    "操作记录",
    "nav.about":                   "系统介绍",

    # ── 页面外壳 ──
    "shell.title":          "飞书审批Claw管理后台",
    "shell.brand":          "飞书审批CLAW",
    "shell.admin":          "管理后台",
    "shell.current_user":   "当前用户：",
    "shell.health":         "🩺 健康检查",
    "shell.reauth":         "🔑 重新授权",
    "shell.logged_out":     "已退出",
    "shell.relogin":        "点击重新登录",

    # ── stage 标签 ──
    "stage.init":           "初始化",
    "stage.fetch_instance": "获取审批详情",
    "stage.fetch_user":     "获取申请人",
    "stage.create_group":   "创建群组",
    "stage.run_script":     "执行脚本",
    "stage.send_message":   "发送通知",
    "stage.done":           "已完成",

    # ── proc_type 标签 ──
    "proc_type.group":  "🏠 建群",
    "proc_type.script": "⚡ 脚本",

    # ── check_status 标签 ──
    "check_status.pending":  "⏳ 待执行",
    "check_status.passed":   "✓ 通过",
    "check_status.rejected": "✗ 不通过",
    "check_status.skipped":  "⊘ 跳过",
    "check_status.error":    "⚠ 错误",

    # ── check_stage 标签 ──
    "check_stage.init":         "初始化",
    "check_stage.run_check":    "执行检查",
    "check_stage.approve_node": "提交审批",
    "check_stage.done":         "已完成",

    # ── proc status ──
    "status.success": "✓ 成功",
    "status.error":   "✗ 失败",
    "status.pending":  "⏳ 处理中",

    # ── token 状态 ──
    "token.access_exp":         "Access Token 到期:",
    "token.remaining_min":      "剩余 {0} 分钟",
    "token.refresh_exp":        "Refresh Token 过期时间:",
    "token.remaining_days":     "剩余 {0} 天",
    "token.refresh_unknown":    "Refresh Token 到期未知，请",
    "token.reauth_once":        "重新授权",
    "token.once":               "一次",
    "token.not_configured":     "未配置用户 Token，请",
    "token.authorize_now":      "立即授权",
    "token.app_not_configured": "主应用尚未完成配置：",
    "token.go_settings":        "请前往",
    "token.config_and_restart": "配置并重启。",

    # ── auth warning ──
    "auth_warn.no_auth_title":        "⚠ 尚未完成飞书授权",
    "auth_warn.no_auth_body":         "系统需要一个<b>飞书用户级 token</b> 才能代表真实用户：①发送群消息 ②创建/解散处理群。主应用（机器人）身份无法执行这些操作。",
    "auth_warn.no_auth_action":       '请先在"系统配置"中完成 APP_ID / APP_SECRET / REDIRECT_URI 设置，然后访问',
    "auth_warn.no_auth_action_end":   "完成授权。",
    "auth_warn.no_token_title":       "⚠ 未找到用户 Token，功能受限",
    "auth_warn.no_token_body":        "没有用户 token，系统将以主应用（机器人）身份发送消息，<b>无法创建/解散群组</b>。",
    "auth_warn.no_token_action":      "请访问",
    "auth_warn.no_token_action_end":  "完成飞书授权，授权后无需重启即生效。",
    "auth_warn.expired_title":        "⚠ 用户 Token 已过期且无法自动续期",
    "auth_warn.expired_body":         "用户 token 已失效，且没有 refresh_token，系统将无法自动刷新。发送消息和群操作可能失败。",
    "auth_warn.expired_action":       "请重新访问",
    "auth_warn.expired_action_end":   "完成授权。",

    # ── 处理记录页 ──
    "proc.applicant":    "申请人",
    "proc.subject":      "申请事项",
    "proc.search":       "搜索",
    "proc.reset":        "重置",
    "proc.refresh":      "刷新",
    "proc.no_records":   "暂无记录",
    "proc.prev":         "◄ 上一页",
    "proc.next":         "下一页 ►",
    "proc.page_info":    "第 {0} / {1} 页（共 {2} 条）",
    "proc.per_page":     "条/页",
    "proc.th_id":        "#",
    "proc.th_code":      "实例 Code",
    "proc.th_approval":  "审批名称",
    "proc.th_subject":   "申请事项",
    "proc.th_applicant": "申请人",
    "proc.th_form":      "表单",
    "proc.th_type":      "处理方式",
    "proc.th_group":     "群名",
    "proc.th_stage":     "当前阶段",
    "proc.th_status":    "处理状态",
    "proc.th_info":      "处理信息",
    "proc.th_time":      "创建时间",
    "proc.th_action":    "操作",
    "proc.view":         "⚠ 查看",
    "proc.dissolved":    "已解散",
    "proc.dissolve":     "解散",
    "proc.retry":        "重试",
    "proc.form_btn":     "表单",

    # ── 预检查记录页 ──
    "check.applicant":    "申请人",
    "check.subject":      "申请事项",
    "check.search":       "搜索",
    "check.reset":        "重置",
    "check.refresh":      "刷新",
    "check.no_records":   "暂无记录",
    "check.prev":         "◄ 上一页",
    "check.next":         "下一页 ►",
    "check.page_info":    "第 {0} / {1} 页（共 {2} 条）",
    "check.per_page":     "条/页",
    "check.th_id":        "#",
    "check.th_code":      "实例 Code",
    "check.th_approval":  "审批名称",
    "check.th_subject":   "申请事项",
    "check.th_form":      "表单",
    "check.th_applicant": "申请人",
    "check.th_task_id":   "节点 Task ID",
    "check.th_stage":     "当前阶段",
    "check.th_status":    "检查状态",
    "check.th_reason":    "检查原因",
    "check.th_error":     "错误信息",
    "check.th_time":      "创建时间",
    "check.th_action":    "操作",
    "check.view":         "查看",
    "check.view_error":   "⚠ 查看",
    "check.retry":        "重试",

    # ── 系统配置页 ──
    "settings.section.feishu_app":      "飞书应用配置",
    "settings.section.feishu_approval": "飞书审批配置",
    "settings.section.feishu_group":    "飞书群配置",
    "settings.section.ops":             "运维配置",
    "settings.th_key":        "配置键",
    "settings.th_desc":       "说明",
    "settings.th_value":      "配置值",
    "settings.th_source":     "来源",
    "settings.source_db":     "数据库",
    "settings.source_env":    ".env",
    "settings.source_default": "默认",
    "settings.multi_hint":    "多个值用英文逗号分隔",
    "settings.save":          "保存配置",
    "settings.save_restart":  "保存并重启",
    "settings.missing_notice": "当前缺少主应用启动配置：",
    "settings.missing_notice2": '。服务现在仍可启动并打开管理后台，但不会连接飞书、不会接收审批事件，/auth 也暂不可用。请先在本页补齐配置，再点击「保存并重启」。',

    # ── 环境变量页 ──
    "envvars.hint":           "在此配置的变量会注入到脚本的 <code>ENV</code> 字典中，脚本通过 <code>ENV.get(\"KEY\")</code> 读取。",
    "envvars.add":            "+ 新增环境变量",
    "envvars.th_key":         "变量名",
    "envvars.th_desc":        "说明",
    "envvars.th_value":       "值",
    "envvars.th_time":        "更新时间",
    "envvars.th_action":      "操作",
    "envvars.empty":          "暂无环境变量，点击「新增」添加",
    "envvars.empty_val":      "（空）",
    "envvars.edit":           "编辑",
    "envvars.delete":         "删除",
    "envvars.modal_add":      "新增环境变量",
    "envvars.modal_edit":     "编辑环境变量",
    "envvars.label_key":      "变量名",
    "envvars.label_desc":     "说明",
    "envvars.label_value":    "值",
    "envvars.key_placeholder":  "如 VOLCENGINE_AK",
    "envvars.desc_placeholder": "简要说明此变量用途",
    "envvars.val_placeholder_new":  "输入实际值",
    "envvars.val_placeholder_edit": "输入新值（留空则不修改）",
    "envvars.var_label":      "变量：",
    "envvars.cancel":         "取消",
    "envvars.save":           "保存",

    # ── 操作记录页 ──
    "logs.username":     "用户名",
    "logs.action":       "操作类型",
    "logs.search":       "搜索",
    "logs.reset":        "重置",
    "logs.refresh":      "刷新",
    "logs.no_records":   "暂无记录",
    "logs.prev":         "◄ 上一页",
    "logs.next":         "下一页 ►",
    "logs.page_info":    "第 {0} / {1} 页（共 {2} 条）",
    "logs.per_page":     "条/页",
    "logs.th_id":        "#",
    "logs.th_username":  "用户名",
    "logs.th_ip":        "来源 IP",
    "logs.th_action":    "操作类型",
    "logs.th_detail":    "详情",
    "logs.th_time":      "时间",

    # ── 脚本页 ──
    "scripts.title_precheck":  "自定义预检查脚本",
    "scripts.title_process":   "自定义处理任务脚本",
    "scripts.add":             "新增脚本",
    "scripts.th_subject":      "申请事项",
    "scripts.th_status":       "状态",
    "scripts.th_time":         "更新时间",
    "scripts.th_action":       "操作",
    "scripts.enabled":         "✓ 启用",
    "scripts.disabled":        "✗ 禁用",
    "scripts.edit":            "编辑",
    "scripts.delete":          "删除",
    "scripts.no_scripts":      "暂无脚本",
    "scripts.modal_new":       "新增脚本",
    "scripts.modal_edit":      "编辑脚本: ",
    "scripts.enable_label":    "启用",
    "scripts.save":            "保存",
    "scripts.history":         "历史版本",
    "scripts.close":           "关闭",
    "scripts.name_label":      "申请事项",
    "scripts.editor_label":    "代码编辑器",
    "scripts.debug_label":     "调试面板",
    "scripts.hist_select":     "填入历史记录",
    "scripts.hist_default":    "-- 选择历史记录自动填入 --",
    "scripts.run_debug":       "执行调试（使用编辑器中的代码）",
    "scripts.await_exec":      "等待执行……",
    "scripts.executing":       "执行中……",

    # ── 操作类型标签 ──
    "action.save_settings":  "保存配置",
    "action.restart":        "重启服务",
    "action.retry_task":     "重试处理",
    "action.retry_check":    "重试预检",
    "action.dissolve_group": "解散群",
    "action.precheck_create": "新增预检脚本",
    "action.precheck_edit":  "编辑预检脚本",
    "action.precheck_delete": "删除预检脚本",
    "action.process_create": "新增处理脚本",
    "action.process_edit":   "编辑处理脚本",
    "action.process_delete": "删除处理脚本",
    "action.option_callback_create": "新增选项回调脚本",
    "action.option_callback_edit":   "编辑选项回调脚本",
    "action.option_callback_delete": "删除选项回调脚本",
    "action.envvar_create":  "新增环境变量",
    "action.envvar_edit":    "修改环境变量",
    "action.envvar_delete":  "删除环境变量",

    # ── 403 ──
    "forbidden": "此操作仅主管理员可执行。",
}

_EN = {
    # ── nav ──
    "nav.process_records":         "Process Records",
    "nav.precheck_records":        "Precheck Records",
    "nav.process_scripts":         "Process Scripts",
    "nav.precheck_scripts":        "Precheck Scripts",
    "nav.option_callback_scripts": "Option Callback Scripts",
    "nav.envvars":                 "Env Variables",
    "nav.settings":                "Settings",
    "nav.logs":                    "Audit Log",
    "nav.about":                   "About",

    # ── shell ──
    "shell.title":          "Lark Approval Claw Admin",
    "shell.brand":          "Lark Approval Claw",
    "shell.admin":          "Admin",
    "shell.current_user":   "User: ",
    "shell.health":         "🩺 Health",
    "shell.reauth":         "🔑 Reauthorize",
    "shell.logged_out":     "Logged Out",
    "shell.relogin":        "Click to login again",

    # ── stage ──
    "stage.init":           "Init",
    "stage.fetch_instance": "Fetch Instance",
    "stage.fetch_user":     "Fetch Applicant",
    "stage.create_group":   "Create Group",
    "stage.run_script":     "Run Script",
    "stage.send_message":   "Send Notification",
    "stage.done":           "Done",

    # ── proc_type ──
    "proc_type.group":  "🏠 Group",
    "proc_type.script": "⚡ Script",

    # ── check_status ──
    "check_status.pending":  "⏳ Pending",
    "check_status.passed":   "✓ Passed",
    "check_status.rejected": "✗ Rejected",
    "check_status.skipped":  "⊘ Skipped",
    "check_status.error":    "⚠ Error",

    # ── check_stage ──
    "check_stage.init":         "Init",
    "check_stage.run_check":    "Run Check",
    "check_stage.approve_node": "Submit Approval",
    "check_stage.done":         "Done",

    # ── status ──
    "status.success": "✓ Success",
    "status.error":   "✗ Failed",
    "status.pending":  "⏳ Processing",

    # ── token ──
    "token.access_exp":         "Access Token expires:",
    "token.remaining_min":      "{0} min remaining",
    "token.refresh_exp":        "Refresh Token expires:",
    "token.remaining_days":     "{0} days remaining",
    "token.refresh_unknown":    "Refresh Token expiry unknown, please",
    "token.reauth_once":        "reauthorize",
    "token.once":               "once",
    "token.not_configured":     "User Token not configured, please",
    "token.authorize_now":      "authorize now",
    "token.app_not_configured": "Main app not configured: ",
    "token.go_settings":        "Please go to",
    "token.config_and_restart": "to configure and restart.",

    # ── auth warning ──
    "auth_warn.no_auth_title":        "⚠ Lark Authorization Not Completed",
    "auth_warn.no_auth_body":         "The system requires a <b>Lark user-level token</b> to act as a real user: ① send group messages ② create/dissolve processing groups. The main app (bot) identity cannot perform these operations.",
    "auth_warn.no_auth_action":       "Please complete APP_ID / APP_SECRET / REDIRECT_URI in 'Settings' first, then visit",
    "auth_warn.no_auth_action_end":   "to authorize.",
    "auth_warn.no_token_title":       "⚠ User Token Not Found, Limited Functionality",
    "auth_warn.no_token_body":        "Without a user token, the system will send messages as the main app (bot), <b>unable to create/dissolve groups</b>.",
    "auth_warn.no_token_action":      "Please visit",
    "auth_warn.no_token_action_end":  "to complete Lark authorization. No restart needed.",
    "auth_warn.expired_title":        "⚠ User Token Expired, Cannot Auto-renew",
    "auth_warn.expired_body":         "User token has expired and there is no refresh_token. The system cannot auto-refresh. Messaging and group operations may fail.",
    "auth_warn.expired_action":       "Please revisit",
    "auth_warn.expired_action_end":   "to reauthorize.",

    # ── process records ──
    "proc.applicant":    "Applicant",
    "proc.subject":      "Subject",
    "proc.search":       "Search",
    "proc.reset":        "Reset",
    "proc.refresh":      "Refresh",
    "proc.no_records":   "No records",
    "proc.prev":         "◄ Prev",
    "proc.next":         "Next ►",
    "proc.page_info":    "Page {0} / {1} ({2} total)",
    "proc.per_page":     "/page",
    "proc.th_id":        "#",
    "proc.th_code":      "Instance Code",
    "proc.th_approval":  "Approval Name",
    "proc.th_subject":   "Subject",
    "proc.th_applicant": "Applicant",
    "proc.th_form":      "Form",
    "proc.th_type":      "Type",
    "proc.th_group":     "Group",
    "proc.th_stage":     "Stage",
    "proc.th_status":    "Status",
    "proc.th_info":      "Info",
    "proc.th_time":      "Created",
    "proc.th_action":    "Action",
    "proc.view":         "⚠ View",
    "proc.dissolved":    "Dissolved",
    "proc.dissolve":     "Dissolve",
    "proc.retry":        "Retry",
    "proc.form_btn":     "Form",

    # ── precheck records ──
    "check.applicant":    "Applicant",
    "check.subject":      "Subject",
    "check.search":       "Search",
    "check.reset":        "Reset",
    "check.refresh":      "Refresh",
    "check.no_records":   "No records",
    "check.prev":         "◄ Prev",
    "check.next":         "Next ►",
    "check.page_info":    "Page {0} / {1} ({2} total)",
    "check.per_page":     "/page",
    "check.th_id":        "#",
    "check.th_code":      "Instance Code",
    "check.th_approval":  "Approval Name",
    "check.th_subject":   "Subject",
    "check.th_form":      "Form",
    "check.th_applicant": "Applicant",
    "check.th_task_id":   "Node Task ID",
    "check.th_stage":     "Stage",
    "check.th_status":    "Check Status",
    "check.th_reason":    "Reason",
    "check.th_error":     "Error Info",
    "check.th_time":      "Created",
    "check.th_action":    "Action",
    "check.view":         "View",
    "check.view_error":   "⚠ View",
    "check.retry":        "Retry",

    # ── settings ──
    "settings.section.feishu_app":      "Lark App Config",
    "settings.section.feishu_approval": "Lark Approval Config",
    "settings.section.feishu_group":    "Lark Group Config",
    "settings.section.ops":             "Ops Config",
    "settings.th_key":        "Key",
    "settings.th_desc":       "Description",
    "settings.th_value":      "Value",
    "settings.th_source":     "Source",
    "settings.source_db":     "DB",
    "settings.source_env":    ".env",
    "settings.source_default": "Default",
    "settings.multi_hint":    "Multiple values separated by commas",
    "settings.save":          "Save",
    "settings.save_restart":  "Save & Restart",
    "settings.missing_notice": "Missing core config: ",
    "settings.missing_notice2": ". The service can still start and open the admin panel, but will not connect to Lark or receive approval events. /auth is also unavailable. Please complete the config here, then click 'Save & Restart'.",

    # ── envvars ──
    "envvars.hint":           "Variables configured here are injected into scripts as the <code>ENV</code> dict, accessed via <code>ENV.get(\"KEY\")</code>.",
    "envvars.add":            "+ Add Variable",
    "envvars.th_key":         "Key",
    "envvars.th_desc":        "Description",
    "envvars.th_value":       "Value",
    "envvars.th_time":        "Updated",
    "envvars.th_action":      "Action",
    "envvars.empty":          "No variables yet. Click 'Add' to create one.",
    "envvars.empty_val":      "(empty)",
    "envvars.edit":           "Edit",
    "envvars.delete":         "Delete",
    "envvars.modal_add":      "Add Variable",
    "envvars.modal_edit":     "Edit Variable",
    "envvars.label_key":      "Key",
    "envvars.label_desc":     "Description",
    "envvars.label_value":    "Value",
    "envvars.key_placeholder":  "e.g. VOLCENGINE_AK",
    "envvars.desc_placeholder": "Brief description of this variable",
    "envvars.val_placeholder_new":  "Enter value",
    "envvars.val_placeholder_edit": "Enter new value (leave empty to keep)",
    "envvars.var_label":      "Variable: ",
    "envvars.cancel":         "Cancel",
    "envvars.save":           "Save",

    # ── logs ──
    "logs.username":     "Username",
    "logs.action":       "Action",
    "logs.search":       "Search",
    "logs.reset":        "Reset",
    "logs.refresh":      "Refresh",
    "logs.no_records":   "No records",
    "logs.prev":         "◄ Prev",
    "logs.next":         "Next ►",
    "logs.page_info":    "Page {0} / {1} ({2} total)",
    "logs.per_page":     "/page",
    "logs.th_id":        "#",
    "logs.th_username":  "Username",
    "logs.th_ip":        "Source IP",
    "logs.th_action":    "Action",
    "logs.th_detail":    "Detail",
    "logs.th_time":      "Time",

    # ── scripts ──
    "scripts.title_precheck":  "Precheck Scripts",
    "scripts.title_process":   "Processing Scripts",
    "scripts.add":             "New Script",
    "scripts.th_subject":      "Subject",
    "scripts.th_status":       "Status",
    "scripts.th_time":         "Updated",
    "scripts.th_action":       "Action",
    "scripts.enabled":         "✓ Enabled",
    "scripts.disabled":        "✗ Disabled",
    "scripts.edit":            "Edit",
    "scripts.delete":          "Delete",
    "scripts.no_scripts":      "No scripts",
    "scripts.modal_new":       "New Script",
    "scripts.modal_edit":      "Edit Script: ",
    "scripts.enable_label":    "Enabled",
    "scripts.save":            "Save",
    "scripts.history":         "History",
    "scripts.close":           "Close",
    "scripts.name_label":      "Subject",
    "scripts.editor_label":    "Code Editor",
    "scripts.debug_label":     "Debug Panel",
    "scripts.hist_select":     "Load from history",
    "scripts.hist_default":    "-- Select a record to auto-fill --",
    "scripts.run_debug":       "Run Debug (using editor code)",
    "scripts.await_exec":      "Awaiting execution…",
    "scripts.executing":       "Executing…",

    # ── action labels ──
    "action.save_settings":  "Save Settings",
    "action.restart":        "Restart Service",
    "action.retry_task":     "Retry Process",
    "action.retry_check":    "Retry Precheck",
    "action.dissolve_group": "Dissolve Group",
    "action.precheck_create": "Create Precheck Script",
    "action.precheck_edit":  "Edit Precheck Script",
    "action.precheck_delete": "Delete Precheck Script",
    "action.process_create": "Create Process Script",
    "action.process_edit":   "Edit Process Script",
    "action.process_delete": "Delete Process Script",
    "action.option_callback_create": "Create Option Callback Script",
    "action.option_callback_edit":   "Edit Option Callback Script",
    "action.option_callback_delete": "Delete Option Callback Script",
    "action.envvar_create":  "Create Env Variable",
    "action.envvar_edit":    "Edit Env Variable",
    "action.envvar_delete":  "Delete Env Variable",

    # ── 403 ──
    "forbidden": "This operation is restricted to the admin user.",
}


def t(key: str, lang: str = "zh") -> str:
    """查找翻译。fallback: EN → ZH → key。"""
    if lang == "en":
        return _EN.get(key) or _ZH.get(key) or key
    return _ZH.get(key) or _EN.get(key) or key


# ---------------------------------------------------------------------------
# JS 翻译（注入 window._T）
# ---------------------------------------------------------------------------

def js_translations(lang: str = "zh") -> dict:
    """返回 JS 侧需要的翻译 dict，在 _page_shell 中注入为 window._T。"""
    keys = {
        # retryTask
        "js.retry_proc_title":     ("重试处理：", "Retry process: "),
        "js.retry_proc_confirm":   ("\\n\\n将从上次失败节点继续，确认重试？",
                                     "\\n\\nWill continue from last failed step. Confirm retry?"),
        "js.retry_ok":             ("✓ 重试成功", "✓ Retry succeeded"),
        "js.retry_fail":           ("✗ 重试失败：", "✗ Retry failed: "),
        # retryCheckTask
        "js.retry_check_title":    ("重试预检查：", "Retry precheck: "),
        "js.retry_check_confirm":  ("\\n\\n将重新执行检查脚本并自动审批节点，确认？",
                                     "\\n\\nWill re-run the check script and auto-approve. Confirm?"),
        "js.retry_check_ok":       ("✓ 预检查重试成功", "✓ Precheck retry succeeded"),
        # dissolve
        "js.dissolve_step1":       ("【第一步确认】\\n即将解散群组：\\n",
                                     "[Step 1] About to dissolve group:\\n"),
        "js.dissolve_step1_end":   ("\\n\\n此操作不可撤销，是否继续？",
                                     "\\n\\nThis is irreversible. Continue?"),
        "js.dissolve_step2":       ("【第二步确认】\\n再次确认：\\n解散后群组将永久消失，成员会被移出。\\n\\n确认解散？",
                                     "[Step 2] Final confirmation:\\nThe group will be permanently removed and all members will be kicked out.\\n\\nConfirm?"),
        "js.dissolve_ok":          ("✓ 已成功解散群组", "✓ Group dissolved successfully"),
        "js.dissolve_no_perm":     ("✗ Token 缺少 im:chat 权限，无法通过接口解散。\\n\\n"
                                     "请点击【确定】重新授权（会在新标签页打开），授权后刷新本页再试。\\n"
                                     "也可让群主在飞书客户端直接解散群。",
                                     "✗ Token lacks im:chat permission, cannot dissolve via API.\\n\\n"
                                     "Click OK to reauthorize (opens in new tab), then refresh and retry.\\n"
                                     "Alternatively, the group owner can dissolve it in the Lark app."),
        "js.dissolve_fail":        ("✗ 解散失败：", "✗ Dissolve failed: "),
        # settings
        "js.config_saved":         ("配置已保存", "Settings saved"),
        "js.save_fail":            ("保存失败: ", "Save failed: "),
        "js.confirm_restart":      ("配置已保存。确认重启服务？", "Settings saved. Confirm restart?"),
        "js.restarting":           ("服务正在重启，请等待几秒后刷新页面……",
                                     "Service is restarting, please wait a few seconds and refresh…"),
        # envvars
        "js.ev_key_empty":         ("变量名不能为空", "Variable name cannot be empty"),
        "js.ev_val_empty":         ("新增时值不能为空", "Value is required when creating"),
        "js.ev_save_fail":         ("保存失败: ", "Save failed: "),
        "js.ev_del_confirm":       ("确认删除环境变量 ", "Confirm delete variable "),
        "js.ev_del_confirm_end":   (" ？", "?"),
        "js.ev_del_fail":          ("删除失败: ", "Delete failed: "),
        # scripts
        "js.sc_modal_new":         ("新增脚本", "New Script"),
        "js.sc_modal_edit":        ("编辑脚本: ", "Edit Script: "),
        "js.sc_await":             ("等待执行……", "Awaiting execution…"),
        "js.sc_executing":         ("执行中……", "Executing…"),
        "js.sc_name_empty":        ("名称不能为空", "Name cannot be empty"),
        "js.sc_saved":             ("✓ 已保存", "✓ Saved"),
        "js.sc_del_confirm":       ("确认删除脚本: ", "Confirm delete script: "),
        "js.sc_del_confirm_end":   ("？", "?"),
        "js.sc_deleted":           ("✓ 已删除", "✓ Deleted"),
        "js.sc_load_fail":         ("加载失败: ", "Load failed: "),
        "js.sc_code_empty":        ("代码不能为空", "Code cannot be empty"),
        "js.sc_applicant_err":     ("applicant JSON 格式错误", "applicant JSON format error"),
        "js.sc_form_err":          ("form JSON 格式错误", "form JSON format error"),
        "js.sc_request_fail":      ("❌ 请求失败: ", "❌ Request failed: "),
        "js.sc_no_history":        ("暂无历史版本", "No version history"),
        "js.sc_hist_title":        ("版本历史（最近 ", "Version history (last "),
        "js.sc_hist_title_end":    (" 条）：\\n\\n", " entries):\\n\\n"),
        "js.sc_hist_prompt":       ("\\n输入序号回滚到该版本（取消则不操作）：",
                                     "\\nEnter number to rollback (cancel to abort):"),
        "js.sc_hist_invalid":      ("无效序号", "Invalid number"),
        "js.sc_hist_confirm":      ("确认回滚到 ", "Confirm rollback to "),
        "js.sc_hist_confirm_end":  (" 的版本？当前编辑器中的代码将被覆盖。",
                                     "? Current editor code will be overwritten."),
        "js.sc_hist_ok":           ("✓ 已回滚", "✓ Rolled back"),
        "js.sc_open_first":        ("请先打开一个脚本", "Please open a script first"),
        "js.sc_hist_load_fail":    ("加载失败: ", "Load failed: "),
        # envvars modal
        "js.ev_modal_add":         ("新增环境变量", "Add Variable"),
        "js.ev_modal_edit":        ("编辑环境变量", "Edit Variable"),
        "js.ev_key_empty":         ("变量名不能为空", "Variable name cannot be empty"),
        "js.ev_val_empty":         ("新增时值不能为空", "Value is required when creating"),
        "js.ev_save_fail":         ("保存失败: ", "Save failed: "),
        "js.ev_del_confirm":       ("确认删除环境变量 ", "Confirm delete variable "),
        "js.ev_del_confirm_end":   (" ？", "?"),
        "js.ev_del_fail":          ("删除失败: ", "Delete failed: "),
        "js.ev_val_ph_new":        ("输入实际值", "Enter value"),
        "js.ev_val_ph_edit":       ("输入新值（留空则不修改）", "Enter new value (leave empty to keep)"),
        # debug output
        "js.debug_error":          ("❌ 异常:\\n", "❌ Error:\\n"),
        "js.debug_result":         ("📋 返回值:\\n", "📋 Return value:\\n"),
        "js.debug_stdout":         ("📤 stdout:\\n", "📤 stdout:\\n"),
        "js.debug_stderr":         ("⚠️ stderr:\\n", "⚠️ stderr:\\n"),
        "js.debug_done":           ("✓ 执行完成（无输出）", "✓ Execution complete (no output)"),
    }
    idx = 0 if lang == "zh" else 1
    return {k: v[idx] for k, v in keys.items()}


# ---------------------------------------------------------------------------
# About 页面 HTML 块
# ---------------------------------------------------------------------------

def about_body_zh(is_admin: bool) -> str:
    """返回系统介绍页中文 HTML body。"""
    body = (
        '<div style="max-width:940px">'
        '<h2 style="font-size:18px;color:#1d2129;margin:0 0 4px">飞书审批Claw</h2>'
        '<p style="color:#666;font-size:13px;line-height:1.8;margin:0 0 24px">'
        '通过 WebSocket 长连接实时监听飞书审批事件，自动完成'
        '<b>预检查 → 审批通过 → 建处理群 → @Openclaw Bot 自动办理 或 低代码脚本处理</b>的全链路审批自动化。'
        '</p>'

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
    )
    # 脚本编写规范 + 首次使用向导 保持和 server.py 中 _render_about_page 一致
    body += _about_guide_zh(is_admin)
    body += '</div>'
    return body


def about_body_en(is_admin: bool) -> str:
    """返回系统介绍页英文 HTML body。"""
    body = (
        '<div style="max-width:940px">'
        '<h2 style="font-size:18px;color:#1d2129;margin:0 0 4px">Lark Approval Claw</h2>'
        '<p style="color:#666;font-size:13px;line-height:1.8;margin:0 0 24px">'
        'Real-time Lark approval event listener via WebSocket, automating the full pipeline: '
        '<b>Pre-check → Approval → Processing Group → @Openclaw Bot auto-handling or low-code script processing</b>.'
        '</p>'

        '<h3 style="font-size:15px;color:#1a73e8;border-left:3px solid #1a73e8;'
        'padding-left:10px;margin:0 0 12px">Core Design: Approval → Processing Group → Openclaw Bot</h3>'
        '<div style="background:#f7f9ff;border:1px solid #dce8ff;border-radius:8px;'
        'padding:16px 20px;font-size:13px;line-height:2.2;margin-bottom:16px;font-family:monospace">'
        'User submits approval in Lark<br>'
        '&nbsp;&nbsp;&nbsp;&nbsp;↓ Reaches "Pre-check" node<br>'
        '&nbsp;&nbsp;&nbsp;&nbsp;↓ <b>Auto-execute pre-check script</b> → pass continues, fail auto-rejects<br>'
        '&nbsp;&nbsp;&nbsp;&nbsp;↓ Approval finally approved<br>'
        '&nbsp;&nbsp;&nbsp;&nbsp;↓ Match processing script by "Subject"<br>'
        '&nbsp;&nbsp;&nbsp;&nbsp;├─ Script found → <b>Low-code script processing</b> (integrate with n8n / Dify)<br>'
        '&nbsp;&nbsp;&nbsp;&nbsp;└─ No script → <b>Auto-create group + add members + @Openclaw Bot</b><br>'
        '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'
        '↓ Openclaw Bot receives @mention → matches Skill → auto-executes task'
        '</div>'

        '<h3 style="font-size:15px;color:#1a73e8;border-left:3px solid #1a73e8;'
        'padding-left:10px;margin:0 0 12px">Openclaw Bot Integration</h3>'
        '<div style="background:#fffbe6;border:1px solid #ffe58f;border-radius:8px;'
        'padding:14px 18px;font-size:13px;line-height:1.9;margin-bottom:16px">'
        '<b>⚠️ Prerequisite: Openclaw Bot must have pre-trained Skills</b><br>'
        'After approval, the system auto-creates a Lark group, adds <b>Openclaw Bot</b> '
        '(WORKER_BOT_APP_ID), sends a structured @mention message (applicant, subject, form fields). '
        'Openclaw Bot receives the @message and auto-processes based on trained Skills.'
        '<br><br>'
        'For integration to work, Openclaw needs the following setup:'
        '</div>'
        '<table style="border-collapse:collapse;width:100%;margin-bottom:20px">'
        '<tr>'
        '<th style="background:#f0f4ff;color:#1d2129;padding:8px 12px;text-align:left;font-size:13px;'
        'border:1px solid #dce8ff;width:200px">Item</th>'
        '<th style="background:#f0f4ff;color:#1d2129;padding:8px 12px;text-align:left;font-size:13px;'
        'border:1px solid #dce8ff">Description</th>'
        '</tr>'
        '<tr><td style="padding:8px 12px;border:1px solid #eee;font-weight:600">Train Skills</td>'
        '<td style="padding:8px 12px;border:1px solid #eee;font-size:13px;color:#444">'
        'For each "Subject" (e.g., VPN access, DB permissions), pre-train a corresponding Skill in Openclaw '
        'that can recognize the message format sent by this system (applicant name, subject keywords, parameters).'
        '</td></tr>'
        '<tr><td style="padding:8px 12px;border:1px solid #eee;font-weight:600">Message Format</td>'
        '<td style="padding:8px 12px;border:1px solid #eee;font-size:13px;color:#444">'
        'The @mention message format is fixed: <code>applicant</code> (name + open_id), '
        '<code>subject</code> (form field value), <code>form fields</code> (all k/v pairs). '
        'Openclaw Skills should be designed to parse this format.'
        '</td></tr>'
        '<tr><td style="padding:8px 12px;border:1px solid #eee;font-weight:600">Bot in Group</td>'
        '<td style="padding:8px 12px;border:1px solid #eee;font-size:13px;color:#444">'
        'The app specified by WORKER_BOT_APP_ID must have "Bot" capability enabled and be authorized to join groups. '
        'The system adds the bot via its open_id and sends @messages for Openclaw to trigger Skills.'
        '</td></tr>'
        '<tr><td style="padding:8px 12px;border:1px solid #eee;font-weight:600">Human Fallback</td>'
        '<td style="padding:8px 12px;border:1px solid #eee;font-size:13px;color:#444">'
        'WORKER_USER_IDS handlers are also added to the group as human oversight. '
        'If Openclaw cannot match or execute a Skill, handlers can manually process in the group.'
        '</td></tr>'
        '</table>'

        '<h3 style="font-size:15px;color:#1a73e8;border-left:3px solid #1a73e8;'
        'padding-left:10px;margin:0 0 12px">Feature Modules</h3>'
        '<table style="border-collapse:collapse;width:100%;margin-bottom:20px">'
        '<tr><th style="background:#f0f4ff;color:#1d2129;padding:8px 12px;text-align:left;font-size:13px;'
        'border:1px solid #dce8ff;width:160px">Module</th>'
        '<th style="background:#f0f4ff;color:#1d2129;padding:8px 12px;text-align:left;font-size:13px;'
        'border:1px solid #dce8ff">Description</th></tr>'
        '<tr><td style="padding:8px 12px;border:1px solid #eee;font-weight:600">Pre-check Automation</td>'
        '<td style="padding:8px 12px;border:1px solid #eee;font-size:13px;color:#444">'
        'When the approval flow reaches the "Pre-check" node, auto-execute the script. '
        '<code>(True, reason)</code> auto-approves, <code>(False, reason)</code> auto-rejects. No manual intervention needed.</td></tr>'
        '<tr><td style="padding:8px 12px;border:1px solid #eee;font-weight:600">Processing Group</td>'
        '<td style="padding:8px 12px;border:1px solid #eee;font-size:13px;color:#444">'
        'When approved with no matching script, auto-create a Lark group, add handlers and Openclaw Bot, '
        'send notification and @mention to trigger auto-processing.</td></tr>'
        '<tr><td style="padding:8px 12px;border:1px solid #eee;font-weight:600">Low-code Scripts</td>'
        '<td style="padding:8px 12px;border:1px solid #eee;font-size:13px;color:#444">'
        'Match processing scripts by "Subject". When matched, execute <code>run(applicant, form)</code>, '
        'taking priority over default group creation. Just a few lines of Python to integrate with n8n, Dify, or any API.</td></tr>'
        '<tr><td style="padding:8px 12px;border:1px solid #eee;font-weight:600">Online Script Editor</td>'
        '<td style="padding:8px 12px;border:1px solid #eee;font-size:13px;color:#444">'
        'Create/edit Python scripts directly in the admin panel with syntax highlighting and live debugging. '
        'Scripts can <code>import requests</code> to call external APIs with zero barrier.</td></tr>'
        '<tr><td style="padding:8px 12px;border:1px solid #eee;font-weight:600">Environment Variables</td>'
        '<td style="padding:8px 12px;border:1px solid #eee;font-size:13px;color:#444">'
        'Configure KV pairs in the "<a href="/admin/envvars" style="color:#1a73e8">Env Variables</a>" tab. '
        'Auto-injected as <code>ENV</code> dict during script execution. Ideal for managing API keys and sensitive params.</td></tr>'
        '<tr><td style="padding:8px 12px;border:1px solid #eee;font-weight:600">Audit Log</td>'
        '<td style="padding:8px 12px;border:1px solid #eee;font-size:13px;color:#444">'
        'All admin operations (create/edit/delete scripts, save settings, restart, etc.) are logged with operator, source IP, and timestamp.</td></tr>'
        '<tr><td style="padding:8px 12px;border:1px solid #eee;font-weight:600">Hot Reload Config</td>'
        '<td style="padding:8px 12px;border:1px solid #eee;font-size:13px;color:#444">'
        'All settings can be modified in the admin panel. "Save & Restart" to apply. Priority: DB > .env > defaults.</td></tr>'
        '</table>'

        '<h3 style="font-size:15px;color:#1a73e8;border-left:3px solid #1a73e8;'
        'padding-left:10px;margin:0 0 12px">Architecture</h3>'
        '<div style="background:#f7f9ff;border:1px solid #dce8ff;border-radius:8px;'
        'padding:14px 18px;font-size:13px;line-height:2;margin-bottom:20px;font-family:monospace">'
        'Lark Approval Platform<br>'
        '&nbsp;&nbsp;&nbsp;&nbsp;↓ WebSocket long connection (approval_instance P1 event, no public callback)<br>'
        'main.py — Entry: init components, subscribe events, start WebSocket + HTTP<br>'
        '│<br>'
        '├─ handlers/ — Approval event processing<br>'
        '│&nbsp;&nbsp;&nbsp;&nbsp;├─ approval.py — Event router (dispatch precheck / process)<br>'
        '│&nbsp;&nbsp;&nbsp;&nbsp;├─ precheck.py — Precheck node: run script → auto approve/reject<br>'
        '│&nbsp;&nbsp;&nbsp;&nbsp;└─ process.py — Approved: run script or create group + @Openclaw Bot<br>'
        '│<br>'
        '├─ services/ — Core services<br>'
        '│&nbsp;&nbsp;&nbsp;&nbsp;├─ db.py — SQLite data layer (WAL mode, 7 tables)<br>'
        '│&nbsp;&nbsp;&nbsp;&nbsp;├─ chat.py — Lark IM (create group / add members / @Bot / dissolve)<br>'
        '│&nbsp;&nbsp;&nbsp;&nbsp;├─ approval.py — Approval instance details + form parsing<br>'
        '│&nbsp;&nbsp;&nbsp;&nbsp;├─ user_token.py — User OAuth token (persistent + auto-refresh + thread-safe)<br>'
        '│&nbsp;&nbsp;&nbsp;&nbsp;├─ user_profile.py — User profile query (email/phone → open_id)<br>'
        '│&nbsp;&nbsp;&nbsp;&nbsp;├─ lark_client.py — Main app lark.Client singleton<br>'
        '│&nbsp;&nbsp;&nbsp;&nbsp;├─ worker_bot.py — Openclaw Bot lark.Client singleton + bot open_id<br>'
        '│&nbsp;&nbsp;&nbsp;&nbsp;└─ notify.py — Lark message sending (callable from scripts)<br>'
        '│<br>'
        '├─ web/server.py — Admin panel HTTP (FastAPI + uvicorn)<br>'
        '│&nbsp;&nbsp;&nbsp;&nbsp;├─ /admin routes (8 tabs)<br>'
        '│&nbsp;&nbsp;&nbsp;&nbsp;└─ /auth + /callback — Lark OAuth 2.0<br>'
        '│<br>'
        '├─ scheduler/ — Background scheduled tasks<br>'
        '│&nbsp;&nbsp;&nbsp;&nbsp;├─ Group TTL cleanup (hourly) — Dissolve expired groups<br>'
        '│&nbsp;&nbsp;&nbsp;&nbsp;└─ Token patrol (every 10 min) — Auto-refresh when access_token &lt; 30 min<br>'
        '│<br>'
        '└─ data/ — Data persistence (SQLite, Docker mount)'
        '</div>'
    )
    body += _about_guide_en(is_admin)
    body += '</div>'
    return body


# ---------------------------------------------------------------------------
# 脚本编写规范 + 首次使用向导（about 页面子块）
# ---------------------------------------------------------------------------

def _about_guide_zh(is_admin: bool) -> str:
    s = (
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
    )
    if is_admin:
        s += (
            '<h3 style="font-size:15px;color:#1a73e8;border-left:3px solid #1a73e8;'
            'padding-left:10px;margin:0 0 12px">首次使用向导（管理员）</h3>'
            '<ol style="font-size:13px;line-height:2.2;color:#444;margin:0 0 20px;padding-left:20px">'
            '<li>在飞书开发者后台创建主应用，开通所需权限，订阅 approval_instance 事件。</li>'
            '<li>在 Openclaw 中为各类申请事项训练好对应 Skill，约定好本系统的消息格式。</li>'
            '<li>在「系统配置」填写 APP_ID / APP_SECRET / WORKER_BOT_APP_ID 等，点击「保存并重启」。</li>'
            '<li>访问 <a href="/auth" style="color:#1a73e8">/auth</a> 完成飞书 OAuth 授权，获取用户级 token。</li>'
            '<li>在飞书审批后台配置审批流（含预检查节点），将 code 填入 APPROVAL_CODES。</li>'
            '<li>（可选）在「<a href="/admin/envvars" style="color:#1a73e8">环境变量</a>」Tab 中添加脚本所需的密钥/参数。</li>'
            '<li>（可选）在「自定义处理脚本」或「自定义预检查脚本」中编写 Python 脚本。</li>'
            '<li>发起测试审批，在「预检查记录」和「处理记录」中观察执行结果。</li>'
            '</ol>'
        )
    else:
        s += (
            '<h3 style="font-size:15px;color:#1a73e8;border-left:3px solid #1a73e8;'
            'padding-left:10px;margin:0 0 12px">新增申请事项向导（配置用户）</h3>'
            '<ol style="font-size:13px;line-height:2.2;color:#444;margin:0 0 20px;padding-left:20px">'
            '<li>在飞书审批后台确认目标审批表单中「申请事项」字段的精确取值。</li>'
            '<li>进入「<a href="/admin/precheck-scripts" style="color:#1a73e8">自定义预检查脚本</a>」，新建同名脚本。</li>'
            '<li>实现 <code>def check(applicant, form) -> tuple[bool, str]</code>。</li>'
            '<li>（可选）在「调用参数」区测试。</li>'
            '<li>进入「<a href="/admin/process-scripts" style="color:#1a73e8">自定义处理脚本</a>」，新建同名脚本。</li>'
            '<li>同样测试后保存。</li>'
            '<li>发起测试审批，确认状态为 success。</li>'
            '</ol>'
            '<p style="font-size:12px;color:#888;margin:-8px 0 20px">'
            '如需添加环境变量或修改系统配置，请联系 admin。'
            '</p>'
        )
    return s


def _about_guide_en(is_admin: bool) -> str:
    s = (
        '<h3 style="font-size:15px;color:#1a73e8;border-left:3px solid #1a73e8;'
        'padding-left:10px;margin:0 0 12px">Script Writing Guide</h3>'
        '<table style="border-collapse:collapse;width:100%;margin-bottom:20px">'
        '<tr><th style="background:#f0f4ff;color:#1d2129;padding:8px 12px;text-align:left;font-size:13px;'
        'border:1px solid #dce8ff;width:160px">Script Type</th>'
        '<th style="background:#f0f4ff;color:#1d2129;padding:8px 12px;text-align:left;font-size:13px;'
        'border:1px solid #dce8ff">Trigger / Interface</th></tr>'
        '<tr><td style="padding:8px 12px;border:1px solid #eee;font-weight:600">Pre-check Script</td>'
        '<td style="padding:8px 12px;border:1px solid #eee;font-size:13px;color:#444">'
        '<b>Trigger</b>: Executed when approval flow reaches a node matching PRE_CHECK_NODE_NAME.<br>'
        '<b>Interface</b>: <code>def check(applicant: dict, form: dict) -> tuple[bool, str]</code>'
        '</td></tr>'
        '<tr><td style="padding:8px 12px;border:1px solid #eee;font-weight:600">Processing Script</td>'
        '<td style="padding:8px 12px;border:1px solid #eee;font-size:13px;color:#444">'
        '<b>Trigger</b>: After approval, executed when "Subject" exactly matches the script name. '
        'Takes priority over default group creation.<br>'
        '<b>Interface</b>: <code>def run(applicant: dict, form: dict) -> None</code>'
        '</td></tr>'
        '</table>'
    )
    if is_admin:
        s += (
            '<h3 style="font-size:15px;color:#1a73e8;border-left:3px solid #1a73e8;'
            'padding-left:10px;margin:0 0 12px">Getting Started (Admin)</h3>'
            '<ol style="font-size:13px;line-height:2.2;color:#444;margin:0 0 20px;padding-left:20px">'
            '<li>Create a Lark app in the developer console, enable required permissions, subscribe to approval_instance events.</li>'
            '<li>Train corresponding Skills in Openclaw for each subject type.</li>'
            '<li>Fill in APP_ID / APP_SECRET / WORKER_BOT_APP_ID in "Settings", click "Save & Restart".</li>'
            '<li>Visit <a href="/auth" style="color:#1a73e8">/auth</a> to complete Lark OAuth authorization.</li>'
            '<li>Configure approval flows (with pre-check nodes) in Lark admin, add codes to APPROVAL_CODES.</li>'
            '<li>(Optional) Add script secrets/params in the "<a href="/admin/envvars" style="color:#1a73e8">Env Variables</a>" tab.</li>'
            '<li>(Optional) Write Python scripts in "Process Scripts" or "Precheck Scripts".</li>'
            '<li>Submit a test approval and check results in "Precheck Records" and "Process Records".</li>'
            '</ol>'
        )
    else:
        s += (
            '<h3 style="font-size:15px;color:#1a73e8;border-left:3px solid #1a73e8;'
            'padding-left:10px;margin:0 0 12px">Adding a New Subject (User Guide)</h3>'
            '<ol style="font-size:13px;line-height:2.2;color:#444;margin:0 0 20px;padding-left:20px">'
            '<li>Identify the exact "Subject" value in the Lark approval form.</li>'
            '<li>Go to "<a href="/admin/precheck-scripts" style="color:#1a73e8">Precheck Scripts</a>", create a script with the same name.</li>'
            '<li>Implement <code>def check(applicant, form) -> tuple[bool, str]</code>.</li>'
            '<li>(Optional) Test with debug parameters.</li>'
            '<li>Go to "<a href="/admin/process-scripts" style="color:#1a73e8">Process Scripts</a>", create a script with the same name.</li>'
            '<li>Test and save.</li>'
            '<li>Submit a test approval and confirm status is success.</li>'
            '</ol>'
            '<p style="font-size:12px;color:#888;margin:-8px 0 20px">'
            'To add environment variables or modify system settings, contact the admin.'
            '</p>'
        )
    return s


# ---------------------------------------------------------------------------
# 脚本编写指南（scripts 页面的 details 展开块）
# ---------------------------------------------------------------------------

def scripts_guide_zh(script_type: str) -> str:
    """返回脚本页中文编写指南 HTML。"""
    if script_type == "precheck":
        return (
            '<details style="margin-bottom:16px;background:#fff;border-radius:8px;padding:16px;'
            'box-shadow:0 1px 4px rgba(0,0,0,.08)">'
            '<summary style="cursor:pointer;font-weight:600;font-size:15px;color:#1a73e8">'
            '自定义预检查脚本说明与编写指南</summary>'
            '<div style="margin-top:12px;font-size:13px;line-height:1.9;color:#333">'
            '<div style="background:#e8f0fe;border-left:4px solid #1a73e8;padding:10px 14px;'
            'border-radius:0 6px 6px 0;margin-bottom:14px">'
            '<b>什么是自定义预检查脚本？</b><br>'
            '当飞书审批流程中包含名为「<b>预检查</b>」的审批节点，'
            '系统会在该节点进入「待审批」时自动执行对应脚本。'
            '通过则节点自动审批；不通过则整个审批自动退回并附上原因。</div>'
            '<h4 style="margin:8px 0 4px">① 触发时机</h4>'
            '<p>同时满足：收到 PENDING 状态推送 + 存在名为「预检查」的待审批节点。</p>'
            '<h4 style="margin:12px 0 4px">② 脚本匹配</h4>'
            '<p>以「申请事项」为键名查找脚本。</p>'
            '<h4 style="margin:12px 0 4px">③ 函数签名</h4>'
            '<p><code>check(applicant: dict, form: dict) -> tuple[bool, str]</code></p>'
            '<h4 style="margin:12px 0 4px">④ 环境变量</h4>'
            '<p><code>ENV.get("KEY", "")</code> 读取环境变量。</p>'
            '</div></details>'
        )
    else:
        return (
            '<details style="margin-bottom:16px;background:#fff;border-radius:8px;padding:16px;'
            'box-shadow:0 1px 4px rgba(0,0,0,.08)">'
            '<summary style="cursor:pointer;font-weight:600;font-size:15px;color:#1a73e8">'
            '自定义处理任务脚本说明与编写指南</summary>'
            '<div style="margin-top:12px;font-size:13px;line-height:1.9;color:#333">'
            '<div style="background:#e6f4ea;border-left:4px solid #1a7f3c;padding:10px 14px;'
            'border-radius:0 6px 6px 0;margin-bottom:14px">'
            '<b>什么是自定义处理任务脚本？</b><br>'
            '当飞书审批最终通过后，系统自动执行 <code>run()</code>，完成自动化业务处理。</div>'
            '<h4 style="margin:8px 0 4px">① 触发时机</h4>'
            '<p>审批实例状态变为 APPROVED 时触发。</p>'
            '<h4 style="margin:12px 0 4px">② 脚本匹配</h4>'
            '<p>以「申请事项」为键名查找脚本。</p>'
            '<h4 style="margin:12px 0 4px">③ 函数签名</h4>'
            '<p><code>run(applicant: dict, form: dict) -> str | None</code></p>'
            '<h4 style="margin:12px 0 4px">④ 环境变量</h4>'
            '<p><code>ENV.get("KEY", "")</code> 读取环境变量。</p>'
            '</div></details>'
        )


def scripts_guide_en(script_type: str) -> str:
    """返回脚本页英文编写指南 HTML。"""
    if script_type == "precheck":
        return (
            '<details style="margin-bottom:16px;background:#fff;border-radius:8px;padding:16px;'
            'box-shadow:0 1px 4px rgba(0,0,0,.08)">'
            '<summary style="cursor:pointer;font-weight:600;font-size:15px;color:#1a73e8">'
            'Precheck Script Guide</summary>'
            '<div style="margin-top:12px;font-size:13px;line-height:1.9;color:#333">'
            '<div style="background:#e8f0fe;border-left:4px solid #1a73e8;padding:10px 14px;'
            'border-radius:0 6px 6px 0;margin-bottom:14px">'
            '<b>What are precheck scripts?</b><br>'
            'When the approval flow contains a "Pre-check" node, the system auto-executes '
            'the matching script when the node enters "Pending". Pass → auto-approve; fail → auto-reject with reason.</div>'
            '<h4 style="margin:8px 0 4px">① Trigger</h4>'
            '<p>Both conditions met: PENDING status push + a pending node named "Pre-check".</p>'
            '<h4 style="margin:12px 0 4px">② Script Matching</h4>'
            '<p>Scripts are matched by "Subject" value.</p>'
            '<h4 style="margin:12px 0 4px">③ Function Signature</h4>'
            '<p><code>check(applicant: dict, form: dict) -> tuple[bool, str]</code></p>'
            '<h4 style="margin:12px 0 4px">④ Environment Variables</h4>'
            '<p><code>ENV.get("KEY", "")</code> to read variables.</p>'
            '</div></details>'
        )
    else:
        return (
            '<details style="margin-bottom:16px;background:#fff;border-radius:8px;padding:16px;'
            'box-shadow:0 1px 4px rgba(0,0,0,.08)">'
            '<summary style="cursor:pointer;font-weight:600;font-size:15px;color:#1a73e8">'
            'Process Script Guide</summary>'
            '<div style="margin-top:12px;font-size:13px;line-height:1.9;color:#333">'
            '<div style="background:#e6f4ea;border-left:4px solid #1a7f3c;padding:10px 14px;'
            'border-radius:0 6px 6px 0;margin-bottom:14px">'
            '<b>What are processing scripts?</b><br>'
            'After final approval, the system auto-executes <code>run()</code> to handle the business logic.</div>'
            '<h4 style="margin:8px 0 4px">① Trigger</h4>'
            '<p>Triggered when the approval status becomes APPROVED.</p>'
            '<h4 style="margin:12px 0 4px">② Script Matching</h4>'
            '<p>Scripts are matched by "Subject" value.</p>'
            '<h4 style="margin:12px 0 4px">③ Function Signature</h4>'
            '<p><code>run(applicant: dict, form: dict) -> str | None</code></p>'
            '<h4 style="margin:12px 0 4px">④ Environment Variables</h4>'
            '<p><code>ENV.get("KEY", "")</code> to read variables.</p>'
            '</div></details>'
        )
