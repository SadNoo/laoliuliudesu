# 首次生产发布记录

## 发布标识

- 运行时代码提交：`9ac3b48`
- 域名：`https://lhc-api.1151156.xyz`
- 服务器目录：`/opt/laoliuliu/current`
- 新服务：`laoliuliu-production-api-1`、`postgres-1`、`scheduler-1`

## 旧项目回滚点

- 备份目录：
  `/opt/lhc-analysis/backups/pre-laoliuliu-20260815T161852+0800`
- PostgreSQL custom-format 备份：320646 bytes，TOC 176 行。
- 数据库备份 SHA-256：
  `79156936c921a62d76bbe6217c4e28984022c0d057efe27601e4bbadbadfc9bc`
- Compose/Caddy/Secrets 回滚包 SHA-256：
  `aa454f554a7c312d261b6193aa87a72376a6c883fec3bd942598cd06d3c847f7`
- 旧 API、Worker、Scheduler 已停止且退出码为 0；旧 PostgreSQL、Redis、Caddy、
  镜像和数据卷未删除。

## 新项目验收

- secrets 初始化、Alembic 迁移均退出码 0。
- API 使用非 root 用户、只读根文件系统，容器健康检查通过。
- 2026 历史数据 226 期；第二次回填新增 0、跳过 226。
- 最新期 `2026226`，特码 `17`，生肖虎；有效样本 22、计数 132。
- 前六生肖：馬 16、虎 13、狗 13、牛 12、雞 12、鼠 11。
- Scheduler 正常等待香港时间 21:35。
- 公网 ready 200、登录页 200、匿名业务 API 401；浏览器控制台无错误。
- 未配置供应商 API Key，也没有发送真实 OpenAI 请求。

## 管理员交接

- 用户名：`admin`
- 服务器凭据文件：
  `/opt/laoliuliu/shared/deploy/credentials/admin-20260815.json`
- 本地凭据文件：`deploy/credentials/admin-20260815.json`（Git 忽略，权限 0600）。
- 一次性密码已验证可以登录；首次正式登录后必须由用户自行修改。
