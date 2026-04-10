"""
handlers/precheck.py — 预检查节点自动审批编排逻辑。

check 脚本规范：
  def check(applicant: dict, form: dict) -> tuple[bool, str]: ...
"""
import json
import logging
import types

import config as _config
from config import PRE_CHECK_NODE_NAME
from services.approval import (
    approve_task_node,
    get_instance_detail,
    reject_task_node,
)
from services.user_profile import get_user
from services.db import (
    delete_check_task,
    get_check_task,
    get_precheck_script,
    update_check_task,
    upsert_check_task,
)

logger = logging.getLogger(__name__)


def run_precheck(instance_code: str, approval_code: str = "") -> None:
    """
    对一个审批实例执行预检查。
    幂等：若 check_status 已为 passed/rejected 则直接跳过。
    失败时更新 check_status=error 并 raise。
    """
    upsert_check_task(instance_code, approval_code)
    rec = get_check_task(instance_code)
    if rec and rec["check_status"] in ("passed", "rejected"):
        logger.info("[precheck] 已完成，跳过 instance_code=%s", instance_code)
        return

    # ── Step 1: 获取实例详情 + task_list，单次 API ─────────────────────────
    try:
        applicant_id, subject, approval_status, form_dict, task_list, approval_name = \
            get_instance_detail(instance_code)
    except Exception as exc:
        err = str(exc)
        logger.error("[precheck] 获取审批实例失败: %s", err)
        update_check_task(instance_code, check_status="error",
                          stage="init", extra_info=err)
        raise

    logger.info("[precheck] instance_code=%s subject=%s approval_status=%s",
                instance_code, subject, approval_status)
    logger.info("[precheck] form_dict=%s task_list=%s", form_dict, task_list)

    # ── Step 2: 从 task_list 找待审批的「预检查」节点 ─────────────────────
    task_id = None
    task_operator = None   # 飞书流程中该节点配置的审批人 open_id
    for task in task_list:
        if task["node_name"] == PRE_CHECK_NODE_NAME and task["status"] == "PENDING":
            task_id = task["id"]
            task_operator = task.get("open_id") or None
            break

    # 无预检查节点 → 删除临时记录，跳过
    if not task_id:
        delete_check_task(instance_code)
        logger.info("[precheck] 无待审批的「%s」节点，删除记录 instance_code=%s",
                    PRE_CHECK_NODE_NAME, instance_code)
        return

    # 有匹配节点 → 永久记录
    update_check_task(instance_code, subject=subject, applicant_open_id=applicant_id,
                      task_id=task_id, approval_name=approval_name,
                      form_json=json.dumps(form_dict, ensure_ascii=False),
                      stage="fetch_user")

    # ── Step 3: 获取申请人（失败则报错，不继续） ───────────────────────────
    try:
        applicant = get_user(applicant_id)
        if not applicant:
            raise RuntimeError(f"获取申请人返回空，open_id={applicant_id}")
    except Exception as exc:
        err = str(exc)
        logger.error("[precheck] 获取申请人失败: %s", err)
        update_check_task(instance_code, check_status="error",
                          stage="fetch_user", extra_info=err)
        raise

    applicant_dict = applicant  # get_user 已返回 dict
    update_check_task(instance_code,
                      applicant_name=applicant_dict["name"],
                      applicant_json=json.dumps(applicant_dict, ensure_ascii=False),
                      stage="run_check")

    # ── Step 4: 执行 check 脚本，得出检查结论 (passed, reason) ──────────────
    script_row = get_precheck_script(subject)
    if not script_row or not script_row.get("enabled"):
        logger.info("[precheck] 无对应脚本（或已禁用），将自动通过 instance_code=%s subject=%s",
                    instance_code, subject)
        passed, reason = True, "无预检查脚本，自动通过"
    else:
        try:
            from services.db import get_script_envvars_dict
            mod = types.ModuleType(f"_chk_{subject}")
            mod.__dict__["ENV"] = get_script_envvars_dict()
            exec(compile(script_row["code"], f"precheck_scripts/{subject}.py", "exec"), mod.__dict__)
            if not hasattr(mod, "check"):
                logger.info("[precheck] precheck_scripts/%s 无 check 函数，将自动通过", subject)
                passed, reason = True, f"precheck_scripts/{subject} 无 check 函数，自动通过"
            else:
                passed, reason = mod.check(applicant_dict, form_dict)
                passed = bool(passed)
                reason = str(reason) if reason else ""
                logger.info("[precheck] check 结果: passed=%s reason=%s subject=%s",
                            passed, reason, subject)
        except Exception as exc:
            err = str(exc)
            logger.error("[precheck] 执行 check 脚本失败: %s", err)
            update_check_task(instance_code, check_status="error",
                              stage="run_check", extra_info=err)
            raise

    # 落库检查结论，stage 推进到 approve_node（标记「即将调用飞书 API」）
    update_check_task(instance_code,
                      check_passed=1 if passed else 0,
                      check_reason=reason,
                      stage="approve_node")

    # ── Step 5: 根据结论调用飞书 API 执行审批操作 ─────────────────────────
    # 操作人优先用流程中该节点配置的审批人（task_operator），如为空则降级为 WORKER_ADMIN_ID。
    # 出错仅在此处记录 stage="approve_node"，与 Step 4 错误阶段严格区分。
    # 重试时：若节点已被审批（不再 PENDING），Step 2 找不到 task_id 会提前退出，
    # 不会重复调用本步，避免幂等问题。
    operator = task_operator or _config.WORKER_ADMIN_ID
    if not task_operator:
        logger.info(
            "[precheck] 预检查节点未配置审批人，降级使用 WORKER_ADMIN_ID=%s", _config.WORKER_ADMIN_ID
        )
    else:
        logger.info("[precheck] 使用流程配置的审批人 open_id=%s 执行操作", task_operator)
    try:
        if passed:
            approve_task_node(
                task_id, instance_code, approval_code, operator,
                comment=reason or "预检查通过",
            )
            update_check_task(instance_code, check_status="passed", stage="done")
        else:
            reject_task_node(
                task_id, instance_code, approval_code, operator,
                reason=reason or "预检查不通过——建议修改后重新提交",
            )
            update_check_task(instance_code, check_status="rejected", stage="done")
    except Exception as exc:
        err = str(exc)
        logger.error("[precheck] 执行审批操作失败: %s", err)
        update_check_task(instance_code, check_status="error",
                          stage="approve_node", extra_info=err)
        raise


def retry_precheck(instance_code: str) -> None:
    """重试失败的预检查任务（仅 error 状态可重试）。"""
    rec = get_check_task(instance_code)
    if not rec:
        raise ValueError(f"找不到预检查记录：{instance_code}")
    if rec["check_status"] not in ("error", "pending"):
        raise ValueError(f"当前状态 {rec['check_status']} 不允许重试")
    approval_code = rec.get("approval_code") or ""
    update_check_task(instance_code,
                      check_status="pending",
                      stage="init",
                      check_passed=-1,
                      check_reason="",
                      extra_info="")
    run_precheck(instance_code, approval_code=approval_code)
