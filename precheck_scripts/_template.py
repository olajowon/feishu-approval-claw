"""
precheck_scripts/_template.py — 预检查脚本模板。

命名规则：文件名与「申请事项」字段值完全一致，例如申请事项为「创建 VPN 账号」
则文件名为「创建 VPN 账号.py」。

预检查节点触发时机：
  - 飞书审批实例状态变为 PENDING
  - 存在节点名称为「预检查」且状态为「待审批」(PENDING) 的任务节点

check 函数签名（必须实现）：
  def check(applicant: dict, form: dict) -> tuple[bool, str]:
      返回值：
        (True,  "")          — 通过，节点将被自动审批通过
        (False, "原因说明")   — 不通过，节点将被自动退回，原因作为退回备注提交

环境变量（ENV）：
  在管理后台「环境变量」Tab 中配置的 KV 会在脚本执行时自动注入为 ENV 字典。
  使用示例：
    api_key = ENV.get("MY_API_KEY", "")
"""


def check(applicant: dict, form: dict) -> tuple:
    """
    预检查逻辑示例：校验申请表单中的关键字段。

    Parameters
    ----------
    applicant : dict
        申请人信息字典，常用键：
          applicant["name"]              — 姓名
          applicant["mobile"]            — 手机号
          applicant["email"]             — 邮箱
          applicant["enterprise_email"]  — 企业邮箱
          applicant["open_id"]           — 飞书 open_id
          applicant["employee_no"]       — 工号
    form : dict
        表单所有字段的 {字段名: 值} 字典。

    Returns
    -------
    (passed: bool, reason: str)
        passed — True 表示通过，False 表示不通过
        reason — 未通过时填写退回原因；通过时可填补充说明（可为空字符串）
    """
    # 示例：检查「申请原因」字段是否填写
    reason_field = form.get("申请原因", "").strip()
    if not reason_field:
        return False, "申请原因不能为空，请补充后重新提交"

    # 示例：使用环境变量（需在管理后台「环境变量」Tab 中配置）
    # api_key = ENV.get("MY_API_KEY", "")

    # 示例：禁止关键词检查
    forbidden = ["测试", "test", "临时"]
    for kw in forbidden:
        if kw in reason_field:
            return False, f"申请原因包含不允许的关键词「{kw}」，请修改后重新提交"

    # 所有检查通过
    return True, ""
