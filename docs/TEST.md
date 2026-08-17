# 测试计划与记录

## 自动化范围

- 生肖锚点与 1～49 映射。
- 特码生肖条件匹配与下一期选择。
- 同一期相同生肖多次累计。
- 生肖内号码次数累计、排序及总数一致性。
- 历史期号计算的数据截止边界和未知期号错误。
- 数据源 6+1、期号、时间、范围、唯一性和 `pet` 验证。
- 第 048 期采集下限、数据库约束及第 001～047 期物理清理。
- 历史回填幂等性与冲突关闭。
- Argon2id 登录、首次改密、Opaque Session 和 CSRF。
- 管理员创建/停用子用户及角色门禁。
- AI Base URL 和输出边界。
- 香港时间 21:35 调度计算。

## 发布前命令

```bash
black --check .
ruff check .
mypy
pytest
alembic upgrade head
alembic check
docker compose config --quiet
docker build .
git diff --check
```

## 真实环境边界

自动测试使用 Mock 数据源和 Mock AI，不依赖付费请求。部署验收允许读取用户批准的
开奖 API；真实 OpenAI 调用仍需单独授权或由用户在页面自行触发。

## 当前结果

- Black、Ruff、严格 MyPy、JavaScript 语法和 Git 空白检查：通过。
- Pytest：14 项通过，0 项失败；存在 1 条来自 FastAPI/Starlette TestClient 的上游
  弃用警告，不影响运行路径。
- PostgreSQL 17：`0001_initial` 升级成功；`alembic check` 无 schema 漂移。
- Docker 镜像：使用哈希锁定依赖构建成功；容器 `/health/ready` 返回 200。
- 真实历史源：首次读取 226、插入 226；第二次读取 226、插入 0、跳过 226。
- 最新真实统计：第 `2026227` 期；前六名依次为兔 17、鼠 14、猪 14、羊 13、
  马 12、鸡 11。六个生肖的号码次数之和均与生肖总次数一致。
- 浏览器视觉检查：桌面与 390×844 窄屏登录页布局正常，控制台 0 条 warning/error。
- 真实 DeepSeek 请求：经用户单独授权后执行 1 次；`deepseek-v4-flash` 在关闭思考
  模式后成功返回有效 JSON，摘要 91 字、观察项 6 条，未执行第二次付费验证。
- 生产回填：首次插入 226，第二次插入 0、跳过 226；生产计算结果与本地一致。
- 生产登录 smoke：管理员角色、首次改密标记、Secure/HttpOnly Cookie 和退出均通过；
  未替用户提交首次密码修改。
- 公网：`/health/ready` 返回 200，新登录页返回 200，匿名
  `/api/v1/analysis/latest` 返回 401；线上浏览器控制台 0 条 warning/error。
- 历史分析：可查询 214 个历史期号，最近一期为 `2026226` 且有效样本为 22；匿名
  访问接口返回 401。
- 线上导航：AI 解读、生肖分析、历史分析、开奖数据顺序正确；两个排名表均显示
  “号码出现次数”列，页面无重复 ID，浏览器控制台无错误。
- 切换后：新 API 健康、新 Scheduler 正常等待 21:35；旧 API/Worker/Scheduler
  退出码 0，旧 PostgreSQL、Redis、Caddy 与旧卷继续保留。
