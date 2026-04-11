"""
test_basic.py — 基础单元测试，验证各模块可正常导入、工具函数逻辑正确。
不依赖真实飞书 API，使用 mock 对象测试核心逻辑。
"""
import json
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import MagicMock, patch


# ── 测试 config 加载 ──────────────────────────────────────────────────────────
class TestConfig(unittest.TestCase):
    def test_config_imports(self):
        """config 模块可正常导入，关键变量存在。"""
        from config import (
            APP_ID, APP_SECRET, APPROVAL_CODES, WORKER_USER_IDS,
            WORKER_ADMIN_ID, WORKER_BOT_ADMIN_ID, FEISHU_HOST,
            HTTP_PORT, ADMIN_USER, ADMIN_PASS, GROUP_TTL_DAYS,
        )
        self.assertIsInstance(APPROVAL_CODES, list)
        self.assertIsInstance(WORKER_USER_IDS, list)
        self.assertIsInstance(HTTP_PORT, int)
        self.assertIsInstance(GROUP_TTL_DAYS, int)
        self.assertIsInstance(FEISHU_HOST, str)

    def test_cfg_list(self):
        """_cfg_list 正确解析逗号分隔的值。"""
        from config import _cfg_list
        self.assertEqual(_cfg_list("__NONEXISTENT__", ""), [])
        with patch.dict(os.environ, {"__TEST_KEY__": "abc"}):
            self.assertEqual(_cfg_list("__TEST_KEY__"), ["abc"])
        with patch.dict(os.environ, {"__TEST_KEY__": " a , b , c "}):
            self.assertEqual(_cfg_list("__TEST_KEY__"), ["a", "b", "c"])

    def test_get_missing_configs(self):
        """get_missing_configs 正确检测未配置项。"""
        from config import get_missing_configs
        missing = get_missing_configs(["__WILL_NEVER_EXIST_1__", "__WILL_NEVER_EXIST_2__"])
        self.assertEqual(len(missing), 2)

    def test_parse_accounts(self):
        """ACCOUNTS 解析格式 user:pass,user2:pass2。"""
        from config import _parse_accounts
        self.assertEqual(_parse_accounts(""), {})
        self.assertEqual(_parse_accounts("u1:p1,u2:p2"), {"u1": "p1", "u2": "p2"})
        self.assertEqual(_parse_accounts("u1:p1, u2:p2 "), {"u1": "p1", "u2": "p2"})


# ── 测试表单字段提取 ──────────────────────────────────────────────────────────
class TestExtractAllFields(unittest.TestCase):
    def test_flat_fields(self):
        from services.approval import _extract_all_fields
        items = [
            {"name": "申请人", "value": "张三"},
            {"name": "申请事项", "value": "创建火山云账号"},
        ]
        result = _extract_all_fields(items)
        self.assertEqual(result["申请人"], "张三")
        self.assertEqual(result["申请事项"], "创建火山云账号")

    def test_nested_fields(self):
        from services.approval import _extract_all_fields
        items = [
            {
                "name": "明细",
                "value": "",
                "children": [{"name": "申请事项", "value": "开通权限"}],
            }
        ]
        result = _extract_all_fields(items)
        self.assertEqual(result["申请事项"], "开通权限")

    def test_empty_fields(self):
        from services.approval import _extract_all_fields
        result = _extract_all_fields([])
        self.assertEqual(result, {})

    def test_skip_desc_fields(self):
        from services.approval import _extract_all_fields
        items = [
            {"name": "说明 1", "value": "这是说明"},
            {"name": "实际字段", "value": "有效值"},
        ]
        result = _extract_all_fields(items)
        self.assertNotIn("说明 1", result)
        self.assertEqual(result["实际字段"], "有效值")


# ── 测试 DB 层 ────────────────────────────────────────────────────────────────
class TestDB(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self._orig_db = None

    def tearDown(self):
        os.unlink(self._tmp.name)

    def _patch_db(self):
        import config
        import services.db as db
        self._orig_db = db.DB_FILE
        db.DB_FILE = self._tmp.name
        config.DB_FILE = self._tmp.name
        db.init_db()
        return db

    def _unpatch_db(self, db):
        import config
        db.DB_FILE = self._orig_db
        config.DB_FILE = self._orig_db

    def test_init_db_idempotent(self):
        db = self._patch_db()
        try:
            db.init_db()
            db.init_db()
        finally:
            self._unpatch_db(db)

    def test_settings_crud(self):
        db = self._patch_db()
        try:
            self.assertIsNone(db.get_setting("test_key"))
            db.set_setting("test_key", "hello")
            self.assertEqual(db.get_setting("test_key"), "hello")
            db.set_setting("test_key", "world")
            self.assertEqual(db.get_setting("test_key"), "world")
        finally:
            self._unpatch_db(db)

    def test_proc_task_crud(self):
        db = self._patch_db()
        try:
            db.upsert_proc_task("INST_001", "APR_001")
            task = db.get_proc_task("INST_001")
            self.assertIsNotNone(task)
            self.assertEqual(task["instance_code"], "INST_001")
            self.assertEqual(task["proc_status"], "pending")

            db.update_proc_task("INST_001", proc_status="success", stage="done")
            task = db.get_proc_task("INST_001")
            self.assertEqual(task["proc_status"], "success")

            db.upsert_proc_task("INST_001", "APR_001")
            task = db.get_proc_task("INST_001")
            self.assertEqual(task["proc_status"], "success")
        finally:
            self._unpatch_db(db)

    def test_check_task_crud(self):
        db = self._patch_db()
        try:
            db.upsert_check_task("INST_002", "APR_002")
            rec = db.get_check_task("INST_002")
            self.assertIsNotNone(rec)
            self.assertEqual(rec["check_status"], "pending")

            db.update_check_task("INST_002", check_status="passed", stage="done")
            rec = db.get_check_task("INST_002")
            self.assertEqual(rec["check_status"], "passed")

            db.delete_check_task("INST_002")
            self.assertIsNone(db.get_check_task("INST_002"))
        finally:
            self._unpatch_db(db)

    def test_script_crud(self):
        db = self._patch_db()
        try:
            db.upsert_precheck_script("test_script", "def check(a,f): return True, ''", 1)
            s = db.get_precheck_script("test_script")
            self.assertIsNotNone(s)
            self.assertEqual(s["name"], "test_script")
            self.assertEqual(s["enabled"], 1)

            scripts = db.list_precheck_scripts()
            self.assertTrue(any(x["name"] == "test_script" for x in scripts))

            db.delete_precheck_script("test_script")
            self.assertIsNone(db.get_precheck_script("test_script"))
        finally:
            self._unpatch_db(db)

    def test_script_history(self):
        db = self._patch_db()
        try:
            db.upsert_process_script("my_script", "code_v1", 1, username="admin")
            db.upsert_process_script("my_script", "code_v2", 1, username="admin")
            db.upsert_process_script("my_script", "code_v3", 1, username="user1")

            history = db.list_script_history("process", "my_script")
            self.assertEqual(len(history), 2)
            codes = {h["code"] for h in history}
            self.assertIn("code_v1", codes)
            self.assertIn("code_v2", codes)

            # 同样代码不产生新历史
            db.upsert_process_script("my_script", "code_v3", 1, username="admin")
            history2 = db.list_script_history("process", "my_script")
            self.assertEqual(len(history2), 2)
        finally:
            self._unpatch_db(db)

    def test_envvars_crud(self):
        db = self._patch_db()
        try:
            db.upsert_script_envvar("MY_KEY", "description", "secret_value")
            envs = db.list_script_envvars()
            self.assertTrue(any(e["key"] == "MY_KEY" for e in envs))

            d = db.get_script_envvars_dict()
            self.assertEqual(d["MY_KEY"], "secret_value")

            db.delete_script_envvar("MY_KEY")
            d2 = db.get_script_envvars_dict()
            self.assertNotIn("MY_KEY", d2)
        finally:
            self._unpatch_db(db)

    def test_admin_logs(self):
        db = self._patch_db()
        try:
            db.log_admin_action("admin", "127.0.0.1", "test_action", "detail_text")
            logs = db.list_admin_logs_paged(1, 10)
            self.assertEqual(len(logs), 1)
            self.assertEqual(logs[0]["action"], "test_action")
            count = db.count_admin_logs()
            self.assertEqual(count, 1)
        finally:
            self._unpatch_db(db)

    def test_paged_queries(self):
        db = self._patch_db()
        try:
            for i in range(5):
                db.upsert_proc_task(f"INST_{i:03d}", "APR_001")
                db.update_proc_task(f"INST_{i:03d}", subject=f"事项{i}")

            page1 = db.list_proc_tasks_paged(1, 3)
            self.assertEqual(len(page1), 3)
            total = db.count_proc_tasks()
            self.assertEqual(total, 5)

            filtered = db.list_proc_tasks_paged(1, 10, subject="事项3")
            self.assertEqual(len(filtered), 1)
        finally:
            self._unpatch_db(db)


# ── 测试事件处理器过滤逻辑 ───────────────────────────────────────────────────
class TestApprovalHandler(unittest.TestCase):
    def test_ignores_unknown_approval_code(self):
        from handlers.approval import handle_approval_v1
        data = MagicMock()
        data.event = {
            "approval_code": "UNKNOWN_CODE",
            "instance_code": "INST_001",
            "status": "APPROVED",
        }
        data.type = "approval_instance"
        handle_approval_v1(data)

    def test_parse_instance_code(self):
        from handlers.approval import _parse_instance_code_from_v1
        self.assertEqual(
            _parse_instance_code_from_v1({"instance_code": "IC001"}), "IC001"
        )
        self.assertEqual(
            _parse_instance_code_from_v1({"instanceCode": "IC002"}), "IC002"
        )
        self.assertEqual(
            _parse_instance_code_from_v1({"process_instance_id": "IC003"}), "IC003"
        )
        self.assertEqual(_parse_instance_code_from_v1({}), "")


# ── 测试 process 去重保护 ────────────────────────────────────────────────────
class TestProcessDedup(unittest.TestCase):
    def test_processing_set_used(self):
        from handlers.process import _processing_lock, _processing_set
        self.assertIsNotNone(_processing_lock)
        self.assertIsInstance(_processing_set, set)


# ── 测试 XSS 辅助函数 ────────────────────────────────────────────────────────
class TestWebHelpers(unittest.TestCase):
    def test_status_badge(self):
        from web.server import _status_badge
        badge = _status_badge("success")
        self.assertIn("✓ 成功", badge)
        self.assertIn("color:", badge)

    def test_applicant_cell_xss(self):
        from web.server import _applicant_cell
        r = {"applicant_name": '<script>alert(1)</script>', "applicant_json": "{}"}
        result = _applicant_cell(r)
        self.assertNotIn("<script>", result)
        self.assertIn("&lt;script&gt;", result)

    def test_form_cell_empty(self):
        from web.server import _form_cell
        self.assertEqual(_form_cell("{}"), "-")
        self.assertEqual(_form_cell(""), "-")


# ── 测试 lark_client 单例 ────────────────────────────────────────────────────
class TestLarkClient(unittest.TestCase):
    def test_get_instance_before_init(self):
        import services.lark_client as lc
        orig = lc._instance
        lc._instance = None
        try:
            with self.assertRaises(RuntimeError):
                lc.get_instance()
        finally:
            lc._instance = orig


# ── 测试 _send_alert 空 webhook 短路 ─────────────────────────────────────────
class TestSendAlert(unittest.TestCase):
    def test_send_alert_noop_when_webhook_empty(self):
        """ALERT_WEBHOOK 为空时 _send_alert 应直接返回，不发请求。"""
        from handlers.approval import _send_alert
        with patch("handlers.approval.ALERT_WEBHOOK", ""):
            # 若未短路会因 requests.post("") 抛 MissingSchema
            _send_alert("test", "body")  # 不应抛异常


# ── 测试 UserTokenManager 公开属性 ───────────────────────────────────────────
class TestUserTokenManagerPublicAPI(unittest.TestCase):
    def test_expires_in(self):
        """expires_in 属性正确返回剩余秒数。"""
        import time
        from services.user_token import UserTokenManager
        mgr = UserTokenManager("id", "secret", "at", "rt",
                               expires_at=time.time() + 3600)
        self.assertAlmostEqual(mgr.expires_in, 3600, delta=5)

    def test_try_refresh_without_refresh_token(self):
        """无 refresh_token 时 try_refresh 返回 False。"""
        from services.user_token import UserTokenManager
        mgr = UserTokenManager("id", "secret", "at", "",
                               expires_at=0)
        self.assertFalse(mgr.try_refresh())


# ── 测试 DB _read_conn query_only 安全性 ─────────────────────────────────────
class TestReadConnQueryOnly(unittest.TestCase):
    def test_read_conn_rejects_writes(self):
        """_read_conn 应拒绝写操作。"""
        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        import services.db as db
        import config
        orig = db.DB_FILE
        db.DB_FILE = tmp.name
        config.DB_FILE = tmp.name
        try:
            db.init_db()
            with db._read_conn() as con:
                with self.assertRaises(sqlite3.OperationalError):
                    con.execute("INSERT INTO settings (key, value) VALUES ('x', 'y')")
        finally:
            db.DB_FILE = orig
            config.DB_FILE = orig
            os.unlink(tmp.name)


if __name__ == "__main__":
    unittest.main()
