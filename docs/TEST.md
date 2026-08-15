# 测试计划与记录

## 自动化范围

- 生肖锚点与 1～49 映射。
- 特码生肖条件匹配与下一期选择。
- 同一期相同生肖多次累计。
- 数据源 6+1、期号、时间、范围、唯一性和 `pet` 验证。
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
- Pytest：12 项通过，0 项失败；存在 1 条来自 FastAPI/Starlette TestClient 的上游
  弃用警告，不影响运行路径。
- PostgreSQL 17：`0001_initial` 升级成功；`alembic check` 无 schema 漂移。
- Docker 镜像：使用哈希锁定依赖构建成功；容器 `/health/ready` 返回 200。
- 真实历史源：首次读取 226、插入 226；第二次读取 226、插入 0、跳过 226。
- 最新真实统计：第 `2026226` 期、特码 `17`、生肖虎；有效转移样本 22、平码计数
  132。前六名依次为馬 16、虎 13、狗 13、牛 12、雞 12、鼠 11。
- 浏览器视觉检查：桌面与 390×844 窄屏登录页布局正常，控制台 0 条 warning/error。
- 真实 OpenAI 请求：未执行，符合“未经另行授权不产生付费调用”的边界。
