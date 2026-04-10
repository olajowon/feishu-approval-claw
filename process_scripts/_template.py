"""
_template.py — 自定义脚本模板，复制此文件并重命名为申请事项名称即可。

示例用法：
    申请事项为「服务器扩容」时，将本文件保存为 process_scripts/服务器扩容.py
    并实现 run 函数中的具体逻辑。

环境变量（ENV）：
  在管理后台「环境变量」Tab 中配置的 KV 会在脚本执行时自动注入为 ENV 字典。
  使用示例：
    api_key = ENV.get("MY_API_KEY", "")
"""
import logging

from services.notify import send_feishu_message

logger = logging.getLogger(__name__)


def run(applicant: dict, form: dict):
    """
    Parameters
    ----------
    applicant : dict
        申请人信息字典，常用键：
          applicant["name"]     — 姓名
          applicant["open_id"]  — 飞书 open_id
          applicant["email"]    — 邮箱
          applicant["enterprise_email"] — 企业邮箱
          applicant["mobile"]   — 手机号
          applicant["employee_no"] — 工号
    form : {'字段名': '值', ...}  — 审批表单所有字段

    Returns
    -------
    str | None  处理结果说明，写入 extra_info；返回 None 或不写 return 亦可
    抛出异常    状态标记为 error，可从管理页重试
    """
    name    = applicant.get("name", "")
    open_id = applicant.get("open_id", "")
    email   = applicant.get("email", "")
    subject = form.get("申请事项", "（无标题）")

    logger.info("[_template] 申请人：%s，表单：%s", name, form)

    # 示例：使用环境变量（需在管理后台「环境变量」Tab 中配置）
    # api_key = ENV.get("MY_API_KEY", "")

    # ------------------------------------------------------------------ #
    # 示例：发送飞书应用消息给申请人                                        #
    # ------------------------------------------------------------------ #
    # 发送飞书应用消息给申请人
    result = send_feishu_message(
        receiver_ids=[open_id],           # 收件人 ID 列表
        receiver_id_type="open_id",       # open_id / user_id / email / chat_id
        title=f"✅ 申请已处理：{subject}",
        content=(
            f"**申请人**：{name}\n\n"
            f"**申请事项**：{subject}\n\n"
            "您的申请已完成自动处理，如有疑问请联系运维团队。"
        ),
        template="green",   # 卡片颜色：blue/green/yellow/orange/red/grey 等
    )

    if not result["ok"]:
        failed = result.get("failed", [])
        not_found = result.get("email_not_found", [])
        raise RuntimeError(f"消息发送失败: failed={failed}, email_not_found={not_found}")

    # ------------------------------------------------------------------ #
    # 在此实现核心业务逻辑                                                  #
    # 例如：调用内部 API、写入 CMDB、发送告警等                              #
    # ------------------------------------------------------------------ #
    raise NotImplementedError("请将此模板复制并实现具体处理逻辑")

    return f"处理完成，已通知申请人 {name}"
