# exmail-mcp

本地 IMAP/SMTP 邮件 MCP 服务 —— 让任何支持 [Model Context Protocol](https://modelcontextprotocol.io) 的 AI 客户端（Claude Desktop、WorkBuddy、pi 等）直接读写你的邮箱：查未读、搜索、发信、回复、转发、标记、移动、删信、下载附件，全部通过自然语言完成。

- **纯本地**：stdio 传输，不开放网络端口，凭据不出本机
- **多账号**：一个 `accounts.yaml` 管多个邮箱（腾讯企业邮箱 / QQ / 163 / Gmail 等任何标准 IMAP 服务商）
- **零依赖框架**：仅 Python 标准库 + `mcp` + `pyyaml`，单文件服务器
- **写操作带安全阀**：发送/删除均两段式确认，删除只移入「已删除」文件夹，绝不物理清除

> 经过真实邮箱全链路验证：自发自收、外部转发（企业邮箱→163）、加星、跨文件夹移动（收件箱↔垃圾邮件）、4.5MB 附件下载均正常。

## 工具清单（12 个）

### 发现 / 读取（只读）

| 工具 | 说明 |
|------|------|
| `list_accounts` | 列出已配置账号（含收发服务器） |
| `list_folders` | 列出某账号的全部文件夹 |
| `list_unread` | 未读邮件列表（新→旧），返回 `uid` |
| `search_emails` | 按主题关键词（支持中文）/发件人/日期/未读组合搜索，返回 `uid` |
| `get_email` | 按 `uid` 读完整邮件：头部 + 正文 + 附件清单 |

### 写操作

| 工具 | 安全机制 |
|------|----------|
| `send_email` | 新邮件，支持 cc/bcc/HTML/本地附件。`confirmed=false` 只返回预览不发送 |
| `reply_email` | 回复：自动「回复：」前缀、`In-Reply-To`/`References` 线程头、引用原文；`reply_all` 全回复 |
| `forward_email` | 转发：自动「转发：」前缀，携带原附件 |
| `mark_email` | `read` / `unread` / `star` / `unstar` |
| `download_attachment` | 按 `uid` + 文件名把附件保存到本地目录 |
| `move_email` | 优先 `UID MOVE`（RFC 6851），不支持时回退 `COPY` + `\Deleted` |
| `delete_email` | **两段式**：先返回摘要，`confirm=true` 后移入「已删除」文件夹（可恢复） |

## 快速开始

### 1. 安装

```bash
# 建议使用独立 venv（Python ≥ 3.10）
python3 -m venv ~/.venvs/exmail-mcp
~/.venvs/exmail-mcp/bin/pip install "mcp<2" pyyaml
```

> **为什么锁 `mcp<2`**：MCP Python SDK 2.x 将 `FastMCP` 更名为 `MCPServer`，API 不兼容。本项目基于 1.x API。

### 2. 配置账号

复制示例配置并填入你的邮箱：

```bash
cp accounts.example.yaml accounts.yaml
```

```yaml
accounts:
  - name: 我的邮箱            # 自定义别名
    address: you@example.com
    password: xxxx            # 客户端专用密码/授权码（不是网页登录密码）
    imap_host: imap.qq.com
    imap_port: 993
    smtp:                     # 可省略：默认按 imap→smtp、端口 465 推导
      host: smtp.qq.com
      port: 465
      from_name: 你的名字
```

常见服务商：

| 服务商 | IMAP | SMTP |
|--------|------|------|
| 腾讯企业邮箱 | `imap.exmail.qq.com:993` | `smtp.exmail.qq.com:465` |
| QQ 邮箱 | `imap.qq.com:993` | `smtp.qq.com:465` |
| 163 邮箱 | `imap.163.com:993` | `smtp.163.com:465` |
| Gmail | `imap.gmail.com:993` | `smtp.gmail.com:465` |

> **授权码获取**：QQ/163/Gmail 需在网页端开启 IMAP 并生成「授权码/App Password」；腾讯企业邮箱路径为「设置 → 账户 → 客户端专用密码」。注意：**重新生成授权码会使旧密码立即失效**。

### 3. 接入 MCP 客户端

**Claude Desktop / 通用 stdio 客户端**（`claude_desktop_config.json`）：

```json
{
  "mcpServers": {
    "exmail-mcp": {
      "command": "/absolute/path/to/venv/bin/python",
      "args": ["/absolute/path/to/exmail-mcp/server.py"]
    }
  }
}
```

**WorkBuddy**（`~/.workbuddy/mcp.json`）：

```json
{
  "mcpServers": {
    "exmail-mcp": {
      "type": "stdio",
      "command": "/absolute/path/to/venv/bin/python",
      "args": ["/absolute/path/to/exmail-mcp/server.py"]
    }
  }
}
```

重启客户端后，在连接器管理页信任该服务即可。

### 4. 验证

配置一个账号后，对 AI 客户端说：

> 「列出我的邮箱账号」→「查一下未读邮件」→「读第一封」

## 安全设计

| 机制 | 说明 |
|------|------|
| 凭据本地化 | 密码只存在本机 `accounts.yaml`，任何工具响应都不回显密码 |
| 两段式发送 | `send/reply/forward` 首次调用仅返回完整预览，`confirmed=true` 才出站 |
| 两段式删除 | `delete_email` 先返回摘要，`confirm=true` 后仅移入「已删除」 |
| 只读优先 | 读取类工具以 `readonly=True` 打开邮箱，绝不误触状态 |
| UID 定位 | 所有写操作用 IMAP UID 而非序号，避免列表变动导致误操作 |
| stdio 传输 | 不监听任何 TCP 端口，进程间通信仅限本机 |

**务必**：`accounts.yaml` 含明文密码，请加入 `.gitignore`，勿提交、勿同步网盘。

## 已知限制与实战经验

来自真实邮箱环境的踩坑记录：

1. **腾讯 IMAP 忽略 `CHARSET UTF-8` 搜索条件**——中文关键词在服务端过滤会返回全部邮件。本服务已实现兜底：日期条件仍走服务端，主题/发件人改在本地逐封过滤（见 `server.py` 中 `has_non_ascii` 分支，勿删）。
2. **跨文件夹移动后 UID 会重新分配**——`COPY+DELETE` 方式移动邮件后，邮件在新文件夹中获得新 UID。工作流应为「移动 → 重新 `search_emails` → 再操作」，勿缓存旧 UID。
3. **删除为软删除**——只移入「已删除」文件夹，永不 `EXPUNGE` 物理清除。需要彻底清除请在邮箱客户端手动操作。
4. **`forward_email` 不支持额外添加本地文件附件**——它只携带原邮件自身附件。需要「转发 + 新附件」时，用 `send_email` + 引用原文的方式替代。
5. **中文文件夹名直接填中文**——腾讯的垃圾邮件文件夹实际名为 `Junk`，其余如「已删除」「已发送」直接填中文即可。

## 项目结构

```
exmail-mcp/
├── server.py              # MCP 服务器（单文件，~800 行）
├── accounts.example.yaml  # 账号配置模板
├── test_smoke.py          # 冒烟测试（stdio 端到端，写操作仅测预览路径）
├── .gitignore
├── LICENSE                # MIT
└── README.md
```

## 冒烟测试

```bash
# 先在 accounts.yaml 配好真实账号
~/.venvs/exmail-mcp/bin/python test_smoke.py
```

测试内容：stdio 握手 → 12 工具注册 → 账号/未读/搜索/详情读取 → 写操作安全路径（删除未确认、非法 action、发送预览模式）。**不会真实发送任何邮件。**

## License

[MIT](LICENSE)
