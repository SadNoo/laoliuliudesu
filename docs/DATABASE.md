# 数据库设计

## 表

| 表 | 目的 |
|---|---|
| `users` | 管理员与子用户、Argon2id 密码、状态和首次改密标记 |
| `web_sessions` | 仅保存 HMAC 摘要的浏览器会话与 CSRF 摘要 |
| `raw_source_snapshots` | 不覆盖的源响应、URL、SHA-256 和获取时间 |
| `draw_records` | 2026 规范化 6+1 开奖与逐期生肖锚点 |
| `source_sync_runs` | 历史/增量同步状态和计数 |
| `ai_providers` | 单个 OpenAI 兼容配置和加密 API Key |
| `analysis_runs` | 固定统计结果、AI 解释、状态和错误码 |
| `audit_logs` | 管理员用户、AI 配置和同步操作审计 |

## 约束

- `draw_records.issue` 唯一；同一期内容不同会由应用层拒绝并回滚。
- 用户名唯一，角色仅为 `admin/user`，状态仅为 `active/disabled`。
- Session Token、CSRF Token 和 API Key 不以明文保存。
- `regular_numbers` 必须由解析器验证为六个互不重复的 1～49 整数；特码也必须合法
  且与平码不重复。
- 所有业务时间存 UTC，页面按 `Asia/Hong_Kong` 显示。

迁移 head：`0001_initial`。
