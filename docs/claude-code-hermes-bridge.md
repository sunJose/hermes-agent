# Claude Code ↔ Hermes Bridge — Cheat Sheet

Boss 的 Claude Code session 通过 MCP 与本机 Hermes runtime 双向打通。本文档是
该 bridge 的实操手册。CLAUDE.md 里只放两条最关键的护栏，详情查这里。

> 状态确认：bridge 在线时，Claude Code 会看到 `mcp__hermes__*` 工具。
> 离线时所有工具调用会失败——先在 Telegram 给 Hermes bot 发一条激活会话即可。

---

## 1. 10 个工具速查

| 工具 | 形态 | 用途 | 关键参数 |
|---|---|---|---|
| `conversations_list` | 读 | 列出所有平台正在进行的会话 | `platform?`, `limit=50`, `search?` |
| `conversation_get` | 读 | 单个会话详情 | `session_key` |
| `messages_read` | 读 | 拉某会话最近 N 条消息 | `session_key`, `limit=50` |
| `attachments_fetch` | 读 | 拉某条消息的图片/媒体附件 | `session_key`, `message_id` |
| `channels_list` | 读 | 列出可主动发起的频道（可能为空） | `platform?` |
| `messages_send` | 写 | 给指定 target 发消息 | `target="platform:id"`, `message` |
| `events_poll` | 读 | 拉自 cursor 之后的新事件（非阻塞） | `after_cursor=0`, `session_key?`, `limit=20` |
| `events_wait` | 读阻塞 | 长轮询等下一个事件 | `after_cursor`, `session_key?`, `timeout_ms=30000` |
| `permissions_list_open` | 读 | bridge 期内 Hermes 端待审批的 exec/plugin | — |
| `permissions_respond` | 写 | 替 Hermes 端待审批做决定 | `id`, `decision ∈ {allow-once, allow-always, deny}` |

事件类型只有三种：`message` / `approval_requested` / `approval_resolved`。

---

## 2. 典型协作模式

### 模式 A — 长跑结果回传
```
messages_send(target="telegram:8565933383",
              message="构建完成 ✅ 失败 0 / 通过 142")
```
适合：8 分钟构建、上线脚本、批量数据处理。

### 模式 B — Human-in-the-loop（危险动作前确认）
```
1. messages_send(... "覆盖 prod DB 是否继续？回 yes/no")
2. last = events_poll(session_key=..., after_cursor=0).next_cursor
3. ev   = events_wait(session_key=..., after_cursor=last, timeout_ms=120000)
4. messages_read(session_key=..., limit=3)  # 解析 Boss 回复
```
**注意 timeout_ms 必须 >= 120000**，否则 30 秒超时会被误读成"没回"。

### 模式 C — 跨 session 找回上下文
```
conversations_list(search="项目X")
messages_read(session_key=..., limit=200)
```
适合：Claude Code 新开 session，从 Telegram/微信里捞 Boss 之前的设计决策。

### 模式 D — 远程审批 Hermes 自己的工具调用
```
permissions_list_open() → 看到 Hermes 想 exec 的危险命令
permissions_respond(id=..., decision="allow-once" | "deny")
```

---

## 3. 委派给 Hermes vs Claude Code 自己干

| 场景 | 选择 | 原因 |
|---|---|---|
| 改 3 个文件 + 跑测试 | Claude Code | 短链路 |
| "每天 9 点发昨日 PR 摘要" | **Hermes**（`hermes cron`） | 重复型 |
| 跑 30 分钟批量重构 | **Hermes**（`hermes chat -q ... --max-turns 50`）+ `messages_send` 回传 | 解放 Claude Code 上下文 |
| 等 Boss 回复 Telegram | **`events_wait`** | 比循环 `events_poll` 省 |
| 同 prompt 跑 3 个模型对比 | **Hermes**（多次 `hermes chat -m ...`） | 不该频繁切模型 |
| 5 秒能查完的 grep | Claude Code | 走 MCP 反而绕 |

### 3a. 让 HS 写长 memory 时
- `--max-turns` **至少给 8**（compress + search + add 至少要 3-4 个 tool call，加上 ReAct 思考轮就接近上限）
- prompt 里明确 **"只做一件事：直接 memory_add，不要 search/不要 compress"**——否则 HS 会反复 self-check 把 turn 烧光
- 容量接近上限时 HS 会自己压缩旧 memory 腾空间，但**这步本身吃 turn**，要么先 `/memory` 看容量，要么单独一次 chat 让她先压缩

---

## 4. 踩坑提醒

| # | 坑 | 后果 | 处理 |
|---|---|---|---|
| 1 | `channels_list` 可能为空 | `messages_send` 给陌生 target 失败/静默 | 先用 `conversations_list` 拼 target |
| 2 | `session_key` ≠ `session_id` | 传错 → 报错或空数据 | 看清字段名（带 `agent:main:platform:dm:` 前缀的是 key） |
| 3 | `permissions_*` 只看 bridge 启动后 | 历史审批查不到 | 真要审计走 `~/.hermes/logs/agent.log` |
| 4 | **`events_wait` 默认 30s** | human-in-the-loop 误判"Boss 没回"继续跑危险动作 | 显式 `timeout_ms>=120000` 或外层套循环 |
| 5 | `messages_send` 不区分 Markdown | 跨平台渲染不一致 | 命令/URL/选项用纯文本 |
| 6 | **MCP bridge ≠ `hermes chat`** | 以为派活了其实只是塞了条字进会话 | 要 Hermes 思考必须 `Bash: hermes chat -q "..." -Q --max-turns N` |

#4 和 #6 是必须记住的两条；其余读一遍即可。

---

*Last updated: 2026-04-30 by Claude Code, on Boss instruction.*
