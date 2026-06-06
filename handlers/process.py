"""
handlers/process.py — 已通过审批实例的自动化编排逻辑。

与 handlers/precheck.py 对称：负责调用 svc 层接口、运行 process_scripts 或建群，
全程写入 proc_tasks 表，失败可在 admin 重试。
"""
import json
import logging
import threading
import types

import config as _config
from config import APP_ID, WORKER_BOT_APP_ID
from services.approval import get_instance_detail
from services.chat import create_group, send_process_notification
from services.user_profile import get_user
from services.db import get_proc_task, get_process_script, update_proc_task, upsert_proc_task
import services.user_token as _user_token
import services.worker_bot as _worker_bot

logger = logging.getLogger(__name__)

# 正在处理中的 instance_code 集合，防止并发重复处理
_processing_lock = threading.Lock()
_processing_set: set = set()


def run_process(instance_code: str, approval_code: str, source: str = "event") -> None:
    """
    已通过审批实例的统一处理入口。
    基于 proc_tasks 表做分段追踪，支持任意节点失败后重试。

    阶段流转：
      init → fetch_instance → fetch_user → create_group / run_script
                                          → send_message → done
    已缓存的字段不会被重复拉取；get_user 每次都重新拉取（需要完整对象发消息）。
    """
    logger.info("[%s] 进入处理流程 instance_code=%s", source, instance_code)

    # ── Step 0: 去重保护 ─────────────────────────────────────────────
    with _processing_lock:
        if instance_code in _processing_set:
            logger.info("[%s] 任务正在处理中，跳过重复请求 instance_code=%s",
                        source, instance_code)
            return
        _processing_set.add(instance_code)

    try:
        _do_run_process(instance_code, approval_code, source)
    finally:
        with _processing_lock:
            _processing_set.discard(instance_code)


def _do_run_process(instance_code: str, approval_code: str, source: str) -> None:
    """实际处理逻辑（被去重包装调用）。"""

    # ── Step 0: 建立/获取任务记录 ────────────────────────────────────
    upsert_proc_task(instance_code, approval_code)
    task = get_proc_task(instance_code)

    if task and task["proc_status"] == "success":
        logger.info("[%s] 任务已成功，跳过 instance_code=%s", source, instance_code)
        return

    # ── Step 1: 获取审批详情（有缓存则跳过）──────────────────────────────────
    subject         = task.get("subject") or ""
    form_json       = task.get("form_json") or "{}"
    applicant_id    = task.get("applicant_open_id") or ""
    approval_status = task.get("approval_status") or ""

    if not subject:
        try:
            applicant_id, subject, approval_status, form_dict, _, approval_name = \
                get_instance_detail(instance_code)
            form_json = json.dumps(form_dict, ensure_ascii=False)
            update_proc_task(
                instance_code,
                subject=subject, applicant_open_id=applicant_id,
                approval_status=approval_status, form_json=form_json,
                approval_name=approval_name,
            )
            logger.info("[%s] 审批详情已获取: subject=%s", source, subject)
        except Exception as exc:
            err = str(exc)
            logger.error("[%s] 获取审批详情失败: %s", source, err)
            update_proc_task(instance_code,
                             proc_status="error", stage="fetch_instance", extra_info=err)
            raise
    else:
        form_dict = json.loads(form_json)
        logger.info("[%s] 使用缓存的审批详情: subject=%s", source, subject)

    logger.info("[%s] instance_code=%s subject=%s approval_status=%s",
                source, instance_code, subject, approval_status)
    logger.info("[%s] form_dict=%s", source, form_dict)

    # ── Step 2: 确定处理类型 ──────────────────────────────────────────────────
    proc_type = task.get("proc_type") or ""
    if not proc_type:
        script_row = get_process_script(subject)
        proc_type = "script" if (script_row and script_row.get("enabled")) else "group"
        update_proc_task(instance_code, proc_type=proc_type)

    # ── Step 3: 获取申请人（每次重新获取，保证完整对象）──────────────────────
    try:
        applicant = get_user(applicant_id)
        if not applicant:
            raise RuntimeError(f"无法获取申请人信息，open_id={applicant_id}")
        applicant_dict = applicant  # get_user 已返回 dict
        applicant_name = applicant_dict["name"]
        update_proc_task(instance_code,
                         applicant_name=applicant_name,
                         applicant_json=json.dumps(applicant_dict, ensure_ascii=False))
    except Exception as exc:
        err = str(exc)
        logger.error("[%s] 获取申请人信息失败: %s", source, err)
        update_proc_task(instance_code,
                         proc_status="error", stage="fetch_user", extra_info=err)
        raise

    # ── Step 4a: 脚本处理分支 ─────────────────────────────────────────────────
    if proc_type == "script":
        logger.info("[%s] 脚本处理: %s", source, subject)
        update_proc_task(instance_code, stage="run_script")
        try:
            script_row = get_process_script(subject)
            if not script_row or not script_row.get("code"):
                raise RuntimeError(f"脚本 process_scripts/{subject} 在数据库中不存在或无代码")
            from services.db import get_script_envvars_dict
            mod = types.ModuleType(f"_asr_{subject}")
            mod.__dict__["ENV"] = get_script_envvars_dict()
            exec(compile(script_row["code"], f"process_scripts/{subject}.py", "exec"), mod.__dict__)
            result   = mod.run(applicant_dict, form_dict)
            run_info = str(result) if result is not None else ""
            update_proc_task(instance_code,
                             proc_status="success", stage="done", extra_info=run_info)
            logger.info("[%s] 脚本执行成功: %s", source, run_info)
        except Exception as exc:
            err = str(exc)
            logger.error("[%s] 脚本执行失败: %s", source, err)
            update_proc_task(instance_code,
                             proc_status="error", stage="run_script", extra_info=err)
            raise
        return

    # ── Step 4b: 建群分支 ─────────────────────────────────────────────────────
    task    = get_proc_task(instance_code)  # 重新读取，可能有缓存 chat_id
    if not task:
        logger.error("[%s] 任务记录丢失，跳过建群", source)
        return
    chat_id = task.get("chat_id") or ""

    if not chat_id:
        group_name = task.get("group_name") or f"【{subject}】- {applicant_name}"
        update_proc_task(instance_code, stage="create_group", group_name=group_name)
        user_open_ids = list(dict.fromkeys(
            uid for uid in [*_config.WORKER_USER_IDS, applicant_id] if uid
        ))
        # 用户身份建群时主应用 bot 不会被自动拉入，需显式加入 bot_id_list；
        # 否则后续 send_process_notification（走主应用 SDK）会因 bot 不在群而失败。
        bot_app_ids = list(dict.fromkeys(
            bid for bid in [APP_ID, WORKER_BOT_APP_ID] if bid
        ))
        try:
            chat_id = create_group(
                group_name, user_open_ids, bot_app_ids,
                owner_id=_config.WORKER_ADMIN_ID,
            )
            update_proc_task(instance_code, chat_id=chat_id)
            logger.info("[%s] 群组已建立: chat_id=%s", source, chat_id)
        except Exception as exc:
            err = str(exc)
            logger.error("[%s] 建群失败: %s", source, err)
            update_proc_task(instance_code,
                             proc_status="error", stage="create_group", extra_info=err)
            raise
    else:
        group_name = task.get("group_name") or f"【{subject}】- {applicant_name}"
        logger.info("[%s] 使用已有群组: chat_id=%s", source, chat_id)

    # ── Step 4b-ii: 发送通知消息 ──────────────────────────────────────────────
    update_proc_task(instance_code, stage="send_message")
    try:
        send_process_notification(
            chat_id, applicant, subject, form_dict,
            _worker_bot.get_bot_open_id(), _config.WORKER_USER_IDS, _user_token.get_instance(),
        )
        update_proc_task(instance_code, proc_status="success", stage="done")
        logger.info("[%s] 处理完成 instance_code=%s chat_id=%s",
                    source, instance_code, chat_id)
    except Exception as exc:
        err = str(exc)
        logger.error("[%s] 发送消息失败: %s", source, err)
        update_proc_task(instance_code,
                         proc_status="error", stage="send_message", extra_info=err)
        raise


def retry_proc_task(instance_code: str) -> None:
    """
    任意阶段失败后的重试入口，供 admin 页面调用。
    自动识别当前缓存状态并从失败阶段继续。
    """
    task = get_proc_task(instance_code)
    if not task:
        raise ValueError(f"找不到处理记录：{instance_code}")
    if task["proc_status"] == "error":
        update_proc_task(instance_code, proc_status="pending", extra_info="")
    approval_code = task.get("approval_code") or ""
    run_process(instance_code, approval_code, "manual-retry")
    logger.info("重试完成 instance_code=%s", instance_code)
