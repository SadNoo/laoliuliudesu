# laoliuliu

`laoliuliu` 是一个私有 Web 项目，用于管理授权用户、采集 2026 年澳门开奖数据，
并按照已经确认的条件频率规则给出下一期六个平码生肖参考排序。

远程仓库：<https://github.com/SadNoo/laoliuliudesu>

## 当前范围

- 管理员登录、创建子用户、启用或停用子用户。
- 所有账号首次使用一次性密码登录后必须修改密码。
- 首次回填使用同源 `HistoryOpenInfo` 历史接口。
- 每天 `Asia/Hong_Kong` 21:35 使用 `opencode/2032` 增量更新；没有新数据时只做有限重试。
- 只保存和分析 2026 年第 001 期至最新期。
- 展示开奖历史、确定性生肖排名、样本数、出现次数和历史频率。
- 管理员配置一个 OpenAI Chat Completions 兼容服务；API Key 加密保存在服务端。
- AI 只解释确定性统计，不能更换前六名、增加其他评分方法或输出具体号码。

本版本不包含 Windows 客户端、License/设备绑定、具体号码预测、通用综合评分、
组合生成、Excel 导出或其他数据源。

## 判断依据

以数据库最新一期为例：

1. 用该期来源提供的生肖年锚点，将特码映射成生肖。
2. 查找 2026 年内特码生肖相同的历史期数。
3. 每个历史期数必须存在按开奖时间紧随其后的下一期。
4. 将所有下一期的六个平码分别映射成生肖。
5. 生肖出现一次计一次；同一期出现两次就累计两次。
6. 按出现次数降序排列；次数相同时使用固定生肖顺序稳定排序。
7. 输出前六个生肖。

结果是历史条件频率，不是未来开奖保证。

## 数据源

- 站点：<https://00853kkjj.com>
- 每日增量：`GET https://api.00853lhc.com/api/opencode/2032`
- 2026 历史回填：`GET https://api.00853lhc.com/api/HistoryOpenInfo?issueNum=YYYY-MM-DD&lotteryId=2032`
- 时区：`Asia/Hong_Kong`
- `openCode`：前六个号码是平码，第七个是特码。
- 历史响应中的 `pet` 是该期生肖年锚点；不能仅按公历年份猜测生肖映射。

来源内容仅用于本项目私有分析，不在本项目中对外再分发。

## OpenAI 接入边界

浏览器只调用本项目服务端，供应商 API Key 不发送到前端。OpenAI 官方生产建议也
要求避免将 API Key 暴露在代码或公开仓库中，并使用环境变量或秘密管理服务：
<https://developers.openai.com/api/docs/guides/production-best-practices>。

项目使用 OpenAI 兼容的 `POST /v1/chat/completions` 形式，请求模型返回 JSON
解释。即使模型输出异常，后端固定排名也不会被修改。结构化输出设计参考：
<https://developers.openai.com/api/docs/guides/structured-outputs>。

## 本地运行

要求 Docker、Docker Compose 和 Python 3.11+。

```bash
cp .env.example .env
# 替换数据库密码、Session pepper 与 Fernet Key
docker compose --profile tools run --rm migrate
docker compose up -d --build postgres api scheduler caddy
```

创建首个管理员：

```bash
mkdir -p deploy/credentials
docker compose --profile tools run --rm admin \
  bootstrap-admin \
  --username admin \
  --credentials-file /run/credentials/admin.json
```

凭据文件以 `0600` 写入 Git 忽略的 `deploy/credentials/`。管理员首次登录后必须
修改一次性密码。

## 开发检查

```bash
black --check .
ruff check .
mypy
pytest
alembic upgrade head
alembic check
docker compose config --quiet
git diff --check
```

依赖版本由 `uv.lock` 锁定，生产镜像使用由该锁文件导出的哈希校验
`requirements.lock`。

详细设计见 [docs/PRD.md](docs/PRD.md)、[docs/SYSTEM.md](docs/SYSTEM.md)、
[docs/DATABASE.md](docs/DATABASE.md)、[docs/API.md](docs/API.md)、
[docs/UI.md](docs/UI.md)、[docs/DEPLOY.md](docs/DEPLOY.md) 和
[docs/TEST.md](docs/TEST.md)。首次生产发布实录见
[docs/RELEASE.md](docs/RELEASE.md)。
