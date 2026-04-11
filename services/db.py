"""
db.py - SQLite data access layer.

Tables:
  proc_tasks        - 审批通过后的处理任务追踪（建群 / 运行脚本）
  check_tasks       - 预检查节点自动审批记录
  settings          - key-value config（存储 user token、系统配置等）
  precheck_scripts  - 预检查脚本（代码存库）
  process_scripts   - 处理脚本（代码存库）
"""
import glob
import logging
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, List, Optional

from config import DATA_DIR, DB_FILE, PROJECT_ROOT

logger = logging.getLogger(__name__)

# 全局写锁：保护 SQLite 多线程并发写入
_write_lock = threading.Lock()

_CREATE_SETTINGS = """
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""

# 处理任务追踪表：审批通过后的建群 / 脚本执行记录。
# proc_type: 'group' | 'script' | ''
# stage: init | fetch_instance | fetch_user | create_group | run_script | send_message | done
# proc_status: pending | success | error
_CREATE_PROC_TASKS = """
CREATE TABLE IF NOT EXISTS proc_tasks (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    instance_code     TEXT    UNIQUE NOT NULL,
    approval_code     TEXT    DEFAULT '',
    approval_name     TEXT    DEFAULT '',
    proc_type         TEXT    DEFAULT '',
    stage             TEXT    DEFAULT 'init',
    proc_status       TEXT    DEFAULT 'pending',
    extra_info        TEXT    DEFAULT '',
    subject           TEXT    DEFAULT '',
    applicant_open_id TEXT    DEFAULT '',
    applicant_name    TEXT    DEFAULT '',
    applicant_json    TEXT    DEFAULT '{}',
    approval_status   TEXT    DEFAULT '',
    form_json         TEXT    DEFAULT '{}',
    chat_id           TEXT    DEFAULT '',
    group_name        TEXT    DEFAULT '',
    is_dissolved      INTEGER DEFAULT 0,
    dissolved_at      DATETIME,
    created_at        DATETIME DEFAULT (datetime('now','localtime')),
    updated_at        DATETIME DEFAULT (datetime('now','localtime'))
);
"""

# 预检查任务表：审批实例中「预检查」节点的自动检查记录。
# stage: init | fetch_user | run_check | approve_node | done
# check_status: pending | passed | rejected | error
_CREATE_CHECK_TASKS = """
CREATE TABLE IF NOT EXISTS check_tasks (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    instance_code     TEXT    UNIQUE NOT NULL,
    approval_code     TEXT    DEFAULT '',
    approval_name     TEXT    DEFAULT '',
    subject           TEXT    DEFAULT '',
    applicant_open_id TEXT    DEFAULT '',
    applicant_name    TEXT    DEFAULT '',
    applicant_json    TEXT    DEFAULT '{}',
    form_json         TEXT    DEFAULT '{}',
    task_id           TEXT    DEFAULT '',
    stage             TEXT    DEFAULT 'init',
    check_status      TEXT    DEFAULT 'pending',
    check_passed      INTEGER DEFAULT -1,
    check_reason      TEXT    DEFAULT '',
    extra_info        TEXT    DEFAULT '',
    created_at        DATETIME DEFAULT (datetime('now','localtime')),
    updated_at        DATETIME DEFAULT (datetime('now','localtime'))
);
"""

# 预检查脚本表
_CREATE_PRECHECK_SCRIPTS = """
CREATE TABLE IF NOT EXISTS precheck_scripts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    UNIQUE NOT NULL,
    code       TEXT    NOT NULL DEFAULT '',
    enabled    INTEGER NOT NULL DEFAULT 1,
    created_at DATETIME DEFAULT (datetime('now','localtime')),
    updated_at DATETIME DEFAULT (datetime('now','localtime'))
);
"""

# 处理脚本表
_CREATE_PROCESS_SCRIPTS = """
CREATE TABLE IF NOT EXISTS process_scripts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    UNIQUE NOT NULL,
    code       TEXT    NOT NULL DEFAULT '',
    enabled    INTEGER NOT NULL DEFAULT 1,
    created_at DATETIME DEFAULT (datetime('now','localtime')),
    updated_at DATETIME DEFAULT (datetime('now','localtime'))
);
"""

# 管理操作日志表
# action: save_settings | restart | dissolve_group | retry_task | retry_check |
#         script_create | script_update | script_delete | send_notify
_CREATE_ADMIN_LOGS = """
CREATE TABLE IF NOT EXISTS admin_logs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    username   TEXT    NOT NULL DEFAULT '',
    ip         TEXT    NOT NULL DEFAULT '',
    action     TEXT    NOT NULL DEFAULT '',
    detail     TEXT    NOT NULL DEFAULT '',
    created_at DATETIME DEFAULT (datetime('now','localtime'))
);
"""

# 脚本环境变量表：供脚本在 exec 上下文中通过 env["KEY"] 读取的 KV 配置
_CREATE_SCRIPT_ENVVARS = """
CREATE TABLE IF NOT EXISTS script_envvars (
    key        TEXT PRIMARY KEY,
    desc       TEXT NOT NULL DEFAULT '',
    value      TEXT NOT NULL DEFAULT '',
    updated_at DATETIME DEFAULT (datetime('now','localtime'))
);
"""

# 脚本版本历史表：每次编辑脚本时保存一份历史快照，支持查看和回滚
_CREATE_SCRIPT_HISTORY = """
CREATE TABLE IF NOT EXISTS script_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    script_type TEXT    NOT NULL DEFAULT '',
    name        TEXT    NOT NULL DEFAULT '',
    code        TEXT    NOT NULL DEFAULT '',
    enabled     INTEGER NOT NULL DEFAULT 1,
    username    TEXT    NOT NULL DEFAULT '',
    created_at  DATETIME DEFAULT (datetime('now','localtime'))
);
"""


@contextmanager
def _conn():
    """写操作连接：持有写锁，自动 commit/rollback。"""
    con = sqlite3.connect(DB_FILE, timeout=30)
    con.row_factory = sqlite3.Row
    try:
        with _write_lock:
            yield con
            con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


@contextmanager
def _read_conn():
    """只读连接：不持有写锁，提升并发读性能。"""
    con = sqlite3.connect(DB_FILE, timeout=30)
    con.row_factory = sqlite3.Row
    try:
        yield con
    finally:
        con.close()


def _migrate_add_column(con, table: str, column: str, coldef: str) -> None:
    """为已存在的表追加列；列已存在则静默忽略。"""
    try:
        con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coldef}")
    except Exception:
        pass  # column already exists


def init_db() -> None:
    """建表（幂等）并执行字段迁移。"""
    os.makedirs(DATA_DIR, exist_ok=True)
    # 启用 WAL 模式提升并发读写性能
    _raw = sqlite3.connect(DB_FILE)
    _raw.execute("PRAGMA journal_mode=WAL")
    _raw.close()
    with _conn() as con:
        con.execute(_CREATE_SETTINGS)
        con.execute(_CREATE_PROC_TASKS)
        con.execute(_CREATE_CHECK_TASKS)
        con.execute(_CREATE_PRECHECK_SCRIPTS)
        con.execute(_CREATE_PROCESS_SCRIPTS)
        con.execute(_CREATE_ADMIN_LOGS)
        con.execute(_CREATE_SCRIPT_ENVVARS)
        con.execute(_CREATE_SCRIPT_HISTORY)
        # 字段迁移：兼容旧版 DB（新字段在 CREATE TABLE 里已包含，ALTER 仅补充旧库）
        _migrate_add_column(con, "proc_tasks",  "approval_name",  "TEXT DEFAULT ''")
        _migrate_add_column(con, "check_tasks", "approval_name",  "TEXT DEFAULT ''")
        _migrate_add_column(con, "check_tasks", "form_json",      "TEXT DEFAULT '{}'")
        _migrate_add_column(con, "proc_tasks",  "applicant_json", "TEXT DEFAULT '{}'")
        _migrate_add_column(con, "check_tasks", "applicant_json", "TEXT DEFAULT '{}'")
    # 首次：将磁盘脚本迁移到 DB
    _migrate_scripts_from_disk()
    logger.info("SQLite initialized: %s", DB_FILE)


def _migrate_scripts_from_disk() -> None:
    """扫描磁盘脚本目录：如果 DB 中尚无同名脚本，则自动导入。已在 DB 中的脚本不受影响。"""
    _SKIP = {"_template.py", "__init__.py"}
    for table, subdir in [("precheck_scripts", "precheck_scripts"),
                          ("process_scripts",  "process_scripts")]:
        scripts_dir = os.path.join(PROJECT_ROOT, subdir)
        if not os.path.isdir(scripts_dir):
            continue
        for fp in sorted(glob.glob(os.path.join(scripts_dir, "*.py"))):
            fname = os.path.basename(fp)
            if fname in _SKIP:
                continue
            name = fname[:-3]  # 去 .py
            try:
                with open(fp, encoding="utf-8") as f:
                    code = f.read()
            except Exception:
                continue
            with _conn() as con:
                exists = con.execute(
                    f"SELECT 1 FROM {table} WHERE name=?", (name,)
                ).fetchone()
                if exists:
                    continue  # DB 中已有，以 DB 为准
                con.execute(
                    f"INSERT OR IGNORE INTO {table} (name, code, enabled) VALUES (?, ?, 1)",
                    (name, code),
                )
            logger.info("migrated %s/%s → DB", subdir, fname)


# ---------------------------------------------------------------------------
# settings
# ---------------------------------------------------------------------------

def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    with _read_conn() as con:
        row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with _conn() as con:
        con.execute(
            "INSERT INTO settings (key, value) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


# ---------------------------------------------------------------------------
# token helpers
# ---------------------------------------------------------------------------

def save_user_token(access_token: str, refresh_token: str, expires_at: float,
                    refresh_expires_at: float = 0.0) -> None:
    """Persist user token to DB settings table."""
    set_setting("user_access_token",  access_token)
    set_setting("user_refresh_token", refresh_token)
    set_setting("user_token_expires_at", str(expires_at))
    if refresh_expires_at > 0:
        set_setting("user_refresh_token_expires_at", str(refresh_expires_at))
    logger.debug("user token persisted to DB")


def load_user_token() -> Optional[Dict]:
    """Return dict(access_token, refresh_token, expires_at) or None."""
    at  = get_setting("user_access_token", "")
    rt  = get_setting("user_refresh_token", "")
    exp = get_setting("user_token_expires_at")
    expires_at = float(exp) if exp else 0.0
    rexp = get_setting("user_refresh_token_expires_at")
    refresh_expires_at = float(rexp) if rexp else 0.0
    return {
        "access_token": at,
        "refresh_token": rt or "",
        "expires_at": expires_at,
        "refresh_expires_at": refresh_expires_at,
    }


# ---------------------------------------------------------------------------
# proc_tasks - write
# ---------------------------------------------------------------------------

def upsert_proc_task(instance_code: str, approval_code: str = "") -> None:
    """INSERT if not exists; leaves existing records untouched."""
    with _conn() as con:
        con.execute(
            "INSERT OR IGNORE INTO proc_tasks (instance_code, approval_code) VALUES (?, ?)",
            (instance_code, approval_code),
        )


def update_proc_task(instance_code: str, **kwargs) -> None:
    """Generic field update for proc_tasks."""
    if not kwargs:
        return
    kwargs["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    set_clause = ", ".join(f"{k}=?" for k in kwargs)
    values = list(kwargs.values()) + [instance_code]
    with _conn() as con:
        con.execute(
            f"UPDATE proc_tasks SET {set_clause} WHERE instance_code=?",
            values,
        )


def dissolve_proc_task_by_chat(chat_id: str) -> None:
    """Mark proc_task group as dissolved."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _conn() as con:
        con.execute(
            "UPDATE proc_tasks SET is_dissolved=1, dissolved_at=?, updated_at=? WHERE chat_id=?",
            (now, now, chat_id),
        )
    logger.info("proc_task dissolved: chat_id=%s", chat_id)


# ---------------------------------------------------------------------------
# proc_tasks - read
# ---------------------------------------------------------------------------

def get_proc_task(instance_code: str) -> Optional[Dict]:
    with _read_conn() as con:
        row = con.execute(
            "SELECT * FROM proc_tasks WHERE instance_code=?", (instance_code,)
        ).fetchone()
    return dict(row) if row else None


def get_proc_task_by_chat(chat_id: str) -> Optional[Dict]:
    with _read_conn() as con:
        row = con.execute(
            "SELECT * FROM proc_tasks WHERE chat_id=?", (chat_id,)
        ).fetchone()
    return dict(row) if row else None


def list_proc_tasks_paged(page: int = 1, page_size: int = 20,
                          name: str = "", subject: str = "") -> List[Dict]:
    offset = (page - 1) * page_size
    clauses, params = [], []
    if name:
        clauses.append("(applicant_name LIKE ? OR applicant_open_id LIKE ?)")
        params += [f"%{name}%", f"%{name}%"]
    if subject:
        clauses.append("subject LIKE ?")
        params.append(f"%{subject}%")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    params += [page_size, offset]
    with _read_conn() as con:
        rows = con.execute(
            f"SELECT * FROM proc_tasks {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
    return [dict(r) for r in rows]


def count_proc_tasks(name: str = "", subject: str = "") -> int:
    clauses, params = [], []
    if name:
        clauses.append("(applicant_name LIKE ? OR applicant_open_id LIKE ?)")
        params += [f"%{name}%", f"%{name}%"]
    if subject:
        clauses.append("subject LIKE ?")
        params.append(f"%{subject}%")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _read_conn() as con:
        row = con.execute(f"SELECT COUNT(*) FROM proc_tasks {where}", params).fetchone()
    return row[0] if row else 0


def get_old_active_proc_tasks(ttl_days: int) -> List[Dict]:
    """Return group proc_tasks older than ttl_days with an active group."""
    with _read_conn() as con:
        rows = con.execute(
            """
            SELECT * FROM proc_tasks
            WHERE proc_type = 'group'
              AND is_dissolved = 0
              AND chat_id IS NOT NULL
              AND chat_id != ''
              AND created_at <= datetime('now', 'localtime', ? || ' days')
            ORDER BY created_at ASC
            """,
            (f"-{ttl_days}",),
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# check_tasks - write
# ---------------------------------------------------------------------------

def upsert_check_task(instance_code: str, approval_code: str = "") -> None:
    """INSERT if not exists; leaves existing records untouched."""
    with _conn() as con:
        con.execute(
            "INSERT OR IGNORE INTO check_tasks (instance_code, approval_code) VALUES (?, ?)",
            (instance_code, approval_code),
        )


def delete_check_task(instance_code: str) -> None:
    """Delete a check_task record entirely (used when no precheck node exists)."""
    with _conn() as con:
        con.execute("DELETE FROM check_tasks WHERE instance_code=?", (instance_code,))


def update_check_task(instance_code: str, **kwargs) -> None:
    """Generic field update for check_tasks."""
    if not kwargs:
        return
    kwargs["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    set_clause = ", ".join(f"{k}=?" for k in kwargs)
    values = list(kwargs.values()) + [instance_code]
    with _conn() as con:
        con.execute(
            f"UPDATE check_tasks SET {set_clause} WHERE instance_code=?",
            values,
        )


# ---------------------------------------------------------------------------
# check_tasks - read
# ---------------------------------------------------------------------------

def get_check_task(instance_code: str) -> Optional[Dict]:
    with _read_conn() as con:
        row = con.execute(
            "SELECT * FROM check_tasks WHERE instance_code=?", (instance_code,)
        ).fetchone()
    return dict(row) if row else None


def list_check_tasks_paged(page: int = 1, page_size: int = 20,
                           subject: str = "", status: str = "",
                           name: str = "") -> List[Dict]:
    offset = (page - 1) * page_size
    clauses, params = [], []
    if subject:
        clauses.append("subject LIKE ?")
        params.append(f"%{subject}%")
    if status:
        clauses.append("check_status = ?")
        params.append(status)
    if name:
        clauses.append("(applicant_name LIKE ? OR applicant_open_id LIKE ?)")
        params.extend([f"%{name}%", f"%{name}%"])
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    params += [page_size, offset]
    with _read_conn() as con:
        rows = con.execute(
            f"SELECT * FROM check_tasks {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
    return [dict(r) for r in rows]


def count_check_tasks(subject: str = "", status: str = "", name: str = "") -> int:
    clauses, params = [], []
    if subject:
        clauses.append("subject LIKE ?")
        params.append(f"%{subject}%")
    if status:
        clauses.append("check_status = ?")
        params.append(status)
    if name:
        clauses.append("(applicant_name LIKE ? OR applicant_open_id LIKE ?)")
        params.extend([f"%{name}%", f"%{name}%"])
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _read_conn() as con:
        row = con.execute(f"SELECT COUNT(*) FROM check_tasks {where}", params).fetchone()
    return row[0] if row else 0


# ---------------------------------------------------------------------------
# precheck_scripts / process_scripts — CRUD
# ---------------------------------------------------------------------------

def _list_scripts(table: str) -> List[Dict]:
    with _read_conn() as con:
        rows = con.execute(f"SELECT * FROM {table} ORDER BY name").fetchall()
    return [dict(r) for r in rows]


def _get_script(table: str, name: str) -> Optional[Dict]:
    with _read_conn() as con:
        row = con.execute(f"SELECT * FROM {table} WHERE name=?", (name,)).fetchone()
    return dict(row) if row else None


def _upsert_script(table: str, name: str, code: str, enabled: int = 1,
                   username: str = "") -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # 保存旧版本到历史记录（如果存在且代码有变化）
    script_type = "precheck" if "precheck" in table else "process"
    with _conn() as con:
        old = con.execute(f"SELECT code, enabled FROM {table} WHERE name=?", (name,)).fetchone()
        if old and old["code"] != code:
            con.execute(
                "INSERT INTO script_history (script_type, name, code, enabled, username) "
                "VALUES (?, ?, ?, ?, ?)",
                (script_type, name, old["code"], old["enabled"], username),
            )
        con.execute(
            f"INSERT INTO {table} (name, code, enabled, created_at, updated_at) "
            f"VALUES (?, ?, ?, ?, ?) "
            f"ON CONFLICT(name) DO UPDATE SET code=excluded.code, enabled=excluded.enabled, updated_at=excluded.updated_at",
            (name, code, enabled, now, now),
        )


def _delete_script(table: str, name: str) -> None:
    with _conn() as con:
        con.execute(f"DELETE FROM {table} WHERE name=?", (name,))


# -- precheck_scripts 快捷方法 --
def list_precheck_scripts() -> List[Dict]:
    return _list_scripts("precheck_scripts")

def get_precheck_script(name: str) -> Optional[Dict]:
    return _get_script("precheck_scripts", name)

def upsert_precheck_script(name: str, code: str, enabled: int = 1,
                           username: str = "") -> None:
    _upsert_script("precheck_scripts", name, code, enabled, username)

def delete_precheck_script(name: str) -> None:
    _delete_script("precheck_scripts", name)

# -- process_scripts 快捷方法 --
def list_process_scripts() -> List[Dict]:
    return _list_scripts("process_scripts")

def get_process_script(name: str) -> Optional[Dict]:
    return _get_script("process_scripts", name)

def upsert_process_script(name: str, code: str, enabled: int = 1,
                          username: str = "") -> None:
    _upsert_script("process_scripts", name, code, enabled, username)

def delete_process_script(name: str) -> None:
    _delete_script("process_scripts", name)


# ---------------------------------------------------------------------------
# admin_logs - write / read
# ---------------------------------------------------------------------------

def log_admin_action(username: str, ip: str, action: str, detail: str = "") -> None:
    """记录管理员操作日志。"""
    with _conn() as con:
        con.execute(
            "INSERT INTO admin_logs (username, ip, action, detail) VALUES (?,?,?,?)",
            (username or "", ip or "", action or "", detail or ""),
        )


def list_admin_logs_paged(page: int = 1, page_size: int = 50,
                          username: str = "", action: str = "") -> List[Dict]:
    offset = (page - 1) * page_size
    clauses, params = [], []
    if username:
        clauses.append("username LIKE ?")
        params.append(f"%{username}%")
    if action:
        clauses.append("action LIKE ?")
        params.append(f"%{action}%")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    params += [page_size, offset]
    with _read_conn() as con:
        rows = con.execute(
            f"SELECT * FROM admin_logs {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()
    return [dict(r) for r in rows]


def count_admin_logs(username: str = "", action: str = "") -> int:
    clauses, params = [], []
    if username:
        clauses.append("username LIKE ?")
        params.append(f"%{username}%")
    if action:
        clauses.append("action LIKE ?")
        params.append(f"%{action}%")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _read_conn() as con:
        row = con.execute(f"SELECT COUNT(*) FROM admin_logs {where}", params).fetchone()
    return row[0] if row else 0


# ---------------------------------------------------------------------------
# script_envvars
# ---------------------------------------------------------------------------

def list_script_envvars() -> List[Dict]:
    """返回所有环境变量（按 key 排序）。"""
    with _read_conn() as con:
        rows = con.execute(
            "SELECT key, desc, value, updated_at FROM script_envvars ORDER BY key"
        ).fetchall()
    return [dict(r) for r in rows]


def get_script_envvars_dict() -> Dict[str, str]:
    """返回 {key: value} 字典，供脚本 exec 上下文注入。"""
    with _read_conn() as con:
        rows = con.execute("SELECT key, value FROM script_envvars").fetchall()
    return {r["key"]: r["value"] for r in rows}


def upsert_script_envvar(key: str, desc: str, value: str) -> None:
    """新增或更新环境变量（含 value）。"""
    with _conn() as con:
        con.execute(
            "INSERT INTO script_envvars (key, desc, value, updated_at) VALUES (?,?,?,datetime('now','localtime')) "
            "ON CONFLICT(key) DO UPDATE SET desc=excluded.desc, value=excluded.value, updated_at=excluded.updated_at",
            (key or "", desc or "", value or ""),
        )


def update_script_envvar_desc(key: str, desc: str) -> None:
    """仅更新环境变量的说明（不修改已存储的值）。"""
    with _conn() as con:
        con.execute(
            "UPDATE script_envvars SET desc=?, updated_at=datetime('now','localtime') WHERE key=?",
            (desc or "", key or ""),
        )


def delete_script_envvar(key: str) -> None:
    """删除环境变量。"""
    with _conn() as con:
        con.execute("DELETE FROM script_envvars WHERE key=?", (key,))


# ---------------------------------------------------------------------------
# script_history
# ---------------------------------------------------------------------------

def list_script_history(script_type: str, name: str,
                        limit: int = 20) -> List[Dict]:
    """查询指定脚本的版本历史（最新在前）。"""
    with _read_conn() as con:
        rows = con.execute(
            "SELECT * FROM script_history "
            "WHERE script_type=? AND name=? "
            "ORDER BY created_at DESC LIMIT ?",
            (script_type, name, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def get_script_history_item(history_id: int) -> Optional[Dict]:
    """按 ID 获取一条历史记录。"""
    with _read_conn() as con:
        row = con.execute(
            "SELECT * FROM script_history WHERE id=?", (history_id,)
        ).fetchone()
    return dict(row) if row else None
