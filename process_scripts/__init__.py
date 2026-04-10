"""
process_scripts — 定制申请事项处理脚本目录。

命名规则
--------
将脚本文件名设为申请事项名称，例如申请事项为「服务器扩容」，则创建：
    process_scripts/服务器扩容.py

每个脚本必须实现 run 函数：

    def run(applicant: dict, form: dict):
        '''
        Parameters
        ----------
        applicant : dict  申请人信息字典（name, open_id, email, enterprise_email, mobile 等）
        form : dict  审批表单的所有字段，格式 {字段名: 值}

        Returns
        -------
        str | None  处理结果描述，将写入 script_runs.run_info
        抛出异常    视为处理失败，状态记录为 error，允许从管理页重试
        '''
        ...

注意事项
--------
- 此目录下的申请事项 **不会** 触发建群流程，完全由脚本自主处理。
- 处理结果记录在 DB 的 proc_tasks 表，管理页「处理记录」区域可查看并重试。
- 脚本在审批通过后异步执行，不要执行超长阻塞操作。
"""
