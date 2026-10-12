#!/usr/bin/env python3
"""exmail-mcp 冒烟测试：stdio 端到端验证。

覆盖：握手 → 工具注册 → 读取类工具 → 写操作安全路径（预览/校验，不真实发送）。
运行前须在 accounts.yaml 配置至少一个真实账号。

用法：
    python test_smoke.py
"""
import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server.py")
PYTHON = sys.executable

EXPECTED_TOOLS = {
    "list_accounts", "list_folders", "list_unread", "search_emails",
    "get_email", "download_attachment", "mark_email",
    "move_email", "delete_email", "send_email", "reply_email", "forward_email",
}


async def main() -> int:
    params = StdioServerParameters(command=PYTHON, args=[SERVER])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # 1. 工具注册
            tools = await session.list_tools()
            names = {t.name for t in tools.tools}
            missing = EXPECTED_TOOLS - names
            assert not missing, f"工具注册不全: 缺 {missing}"
            print(f"[1] 12 个工具注册完整: {', '.join(sorted(names))}")

            # 2. 账号发现
            res = await session.call_tool("list_accounts", {})
            print("[2] list_accounts:", res.content[0].text.splitlines()[0])
            assert "已配置账号" in res.content[0].text or "未配置" in res.content[0].text

            # 3. 未读列表
            res = await session.call_tool("list_unread", {"limit": 3})
            text = res.content[0].text
            print("[3] list_unread:", text.splitlines()[0])

            # 提取首个 uid
            import re
            uid_m = re.search(r"uid=(\d+)", text)
            uid = int(uid_m.group(1)) if uid_m else None
            print(f"[4] 首个未读 uid: {uid}")

            # 5. 读邮件头部
            if uid:
                res = await session.call_tool("get_email", {"uid": uid, "include_body": False})
                print("[5] get_email:", res.content[0].text.splitlines()[0])

            # 6. 中文搜索（走本地过滤兜底）
            res = await session.call_tool("search_emails", {"query": "测试", "limit": 3})
            print("[6] search_emails:", res.content[0].text.splitlines()[0])

            # 7. 写操作安全路径
            if uid:
                # 未确认删除 → 只返回摘要
                res = await session.call_tool("delete_email", {"uid": uid})
                assert "confirm=true" in res.content[0].text, "删除两段式失效"
                print("[7] delete_email 未确认 → 仅返回摘要 ✓")

                # 非法 action → 校验拒绝
                res = await session.call_tool("mark_email", {"uid": uid, "action": "bogus"})
                assert "仅支持" in res.content[0].text
                print("[8] mark_email 非法 action → 拒绝 ✓")

            # 发送预览模式 → 不出站
            res = await session.call_tool("send_email", {
                "to": "nobody@example.invalid", "subject": "smoke", "body": "preview only",
            })
            assert "未发送" in res.content[0].text
            print("[9] send_email 预览模式 → 不发送 ✓")

            if uid:
                res = await session.call_tool("reply_email", {"uid": uid, "body": "preview"})
                assert "未发送" in res.content[0].text
                print("[10] reply_email 预览模式 → 不发送 ✓")

            print("\n[DONE] 全部通过")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
