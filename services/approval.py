"""
approval.py — 封装飞书审批实例 API。
"""
import json
import logging
from typing import Dict, List, Tuple

from lark_oapi.api.approval.v4 import (
    ApproveTaskRequest,
    GetInstanceRequest,
    RejectTaskRequest,
)
from lark_oapi.api.approval.v4.model import TaskApprove

from config import FORM_FIELD_NAME
import services.lark_client as _lark_client

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------

def _fetch_instance(instance_code: str):
    """单次调用 GetInstance，返回原始 response.data。"""
    client = _lark_client.get_instance()
    request = (
        GetInstanceRequest.builder()
        .instance_id(instance_code)
        .user_id_type("open_id")
        .build()
    )
    response = client.approval.v4.instance.get(request)
    if not response.success():
        raise RuntimeError(f"获取审批实例失败 [{response.code}]: {response.msg}")
    return response.data


def get_instance_detail(
    instance_code: str,
) -> Tuple[str, str, str, Dict[str, str], List[Dict[str, str]], str]:
    """
    获取审批实例详情。

    Returns
    -------
    (applicant_open_id, subject, status, form_dict, task_list, approval_name)

    subject 取飞书审批定义名称（approval_name）作为申请事项标识；
    若表单中存在名为「申请事项」的字段且有填值，则优先使用该字段值（兼容用法）。
    """
    data = _fetch_instance(instance_code)
    status: str        = data.status or ""
    applicant_id: str  = data.open_id or ""
    approval_name: str = data.approval_name or ""
    form_raw: str      = data.form or "[]"
    try:
        form_items = json.loads(form_raw)
    except json.JSONDecodeError:
        logger.warning("表单 JSON 解析失败，原始内容：%s", form_raw)
        form_items = []
    form_dict = _extract_all_fields(form_items)
    subject = form_dict.get(FORM_FIELD_NAME, "")
    if not subject:
        subject = approval_name
        if approval_name:
            logger.info("表单中无「%s」字段，使用审批名称「%s」作为主题",
                        FORM_FIELD_NAME, approval_name)
        else:
            logger.warning("表单中无「%s」字段且无审批名称，主题将为空", FORM_FIELD_NAME)
    task_list = [
        {
            "id":       str(t.id or ""),
            "node_id":  str(t.node_id or ""),
            "node_name": str(t.node_name or ""),
            "status":   str(t.status or ""),
            "open_id":  str(t.open_id or ""),
            "type":     str(t.type or ""),
        }
        for t in (data.task_list or [])
    ]
    return applicant_id, subject, status, form_dict, task_list, approval_name


def _extract_all_fields(form_items: list) -> Dict[str, str]:
    """递归提取表单所有字段，返回 {name: value} 字典。"""
    result: Dict[str, str] = {}
    for item in form_items:
        name = item.get("name")
        if name and not name.startswith("说明 "):
            value = item.get("value")
            result[name] = str(value) if value is not None else ""
        children = item.get("children") or item.get("items") or []
        result.update(_extract_all_fields(children))
    return result


def approve_task_node(
    task_id: str,
    instance_code: str,
    approval_code: str,
    operator_open_id: str,
    comment: str = "",
) -> None:
    """以应用 token 自动通过审批节点。"""
    client = _lark_client.get_instance()
    request = (
        ApproveTaskRequest.builder()
        .user_id_type("open_id")
        .request_body(
            TaskApprove.builder()
            .approval_code(approval_code)
            .instance_code(instance_code)
            .user_id(operator_open_id)
            .task_id(task_id)
            .comment(comment)
            .build()
        )
        .build()
    )
    response = client.approval.v4.task.approve(request)
    if not response.success():
        raise RuntimeError(f"审批通过失败 [{response.code}]: {response.msg}")
    logger.info("节点已自动通过 task_id=%s instance=%s", task_id, instance_code)


def reject_task_node(
    task_id: str,
    instance_code: str,
    approval_code: str,
    operator_open_id: str,
    reason: str = "",
) -> None:
    """拒绝审批节点（终止审批流程）。"""
    client = _lark_client.get_instance()
    request = (
        RejectTaskRequest.builder()
        .user_id_type("open_id")
        .request_body(
            TaskApprove.builder()
            .approval_code(approval_code)
            .instance_code(instance_code)
            .user_id(operator_open_id)
            .task_id(task_id)
            .comment(reason or "预检查不通过")
            .build()
        )
        .build()
    )
    response = client.approval.v4.task.reject(request)
    if not response.success():
        raise RuntimeError(f"拒绝审批节点失败 [{response.code}]: {response.msg}")
    logger.info("节点已拒绝 task_id=%s instance=%s reason=%s",
                task_id, instance_code, reason)
