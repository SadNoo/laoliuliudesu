# 系统设计

## 架构

```text
Browser
  │ HTTPS + HttpOnly session + CSRF
  ▼
Caddy
  ▼
FastAPI ───────────────► OpenAI-compatible API
  │                         (explanation only)
  ▼
PostgreSQL
  ▲
  │
Scheduler ─────────────► 00853 current/history APIs
```

项目使用同源、无构建的 HTML/CSS/JavaScript 页面。浏览器不持有供应商 API Key、
数据库连接或长期 Token。FastAPI 负责认证、授权、统计、AI 边界和管理接口。

## 模块

- `config.py`：环境配置和生产安全校验。
- `models.py` / `db.py`：PostgreSQL 持久化。
- `source.py`：已确认 API 格式、超时、大小限制和解析。
- `ingestion.py`：快照、幂等写入和同步审计。
- `zodiac.py`：按每期 `pet` 锚点构造 1～49 生肖映射。
- `analysis.py`：唯一获批的确定性转移频率算法、生肖内号码计数和历史数据截止点。
- `auth.py`：Argon2id、Opaque Session、CSRF、首次改密和子用户状态。
- `ai.py`：OpenAI 兼容调用以及只解释不改排名的提示词。
- `api.py`：版本化业务 API。
- `scheduler.py`：香港时间每日 21:35 调度。
- `web/`：登录、分析、开奖和管理页面。

## 关键边界

- 当前接口仅保留最近五期且不提供 `pet`；增量新记录继承数据库中最近一次由历史
  接口确认的 2026 生肖锚点。部署前必须先完成历史回填。
- 历史计算对每条记录使用该期自己的锚点；下一期平码使用下一期自己的锚点。
- 按期号查询历史分析时，查询集合先截断到目标期，后续数据不能进入匹配或计数。
- 号码次数只是生肖累计值的可追溯明细；AI 输入仍排除该号码明细。
- AI 结果与确定性结果分别存储，AI 响应异常时保留失败记录但不污染排名。
- 管理员停用用户时立即撤销其所有 Web Session。
- 生产环境必须启用 Secure Cookie、HTTPS 和独立随机 secret。
