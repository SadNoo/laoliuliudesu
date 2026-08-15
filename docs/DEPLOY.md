# 部署与切换

## 目标

- 主机：现有项目服务器（SSH 端口 3553）。
- 测试域名：`https://lhc-api.1151156.xyz`。
- 运行组件：Caddy、FastAPI、Scheduler、PostgreSQL 17。
- 旧项目 API/Worker/Scheduler 在切换后停止，但旧数据库卷、镜像、Compose 文件和备份
  必须保留为只读回滚点。

## 生产编排

- 新项目使用 `compose.production.yaml` 和独立的
  `laoliuliu-production_postgres_data`，不复用或修改旧业务数据库。
- 新 API 以 `laoliuliu-api` 别名加入现有
  `lhc-analysis-production_backend` 网络；现有 Caddy 只更换反向代理目标，继续复用
  已验证的域名、证书和 80/443 入口。
- 数据库密码、数据库 URL、Session pepper 和 Fernet Key 使用宿主机 `0600` 文件与
  Docker Secrets，不写入 Compose、镜像或 Git。一次性 root 初始化容器只把应用所需
  三项复制到专用卷并设为 API 用户 `0400`；API、Scheduler 和迁移容器只读挂载该卷。
- 管理员一次性凭据写入 `deploy/credentials/`，该目录不进入 Git。

## 发布门禁

1. 本地格式、类型、测试、迁移和 Compose 检查全部通过。
2. Git 提交已推送到 `SadNoo/laoliuliudesu`。
3. 只读检查服务器磁盘、内存、旧服务、当前镜像和活动任务。
4. 创建旧 PostgreSQL custom-format 备份，校验 TOC、SHA-256 和关键计数。
5. 备份旧 Compose/Caddy 配置并保留旧镜像标签。
6. 新项目先使用隔离数据库和内部网络启动，迁移、健康检查、历史回填通过。
7. 创建一次性管理员凭据到宿主机 `0600` 文件。
8. 停止旧 API/Worker/Scheduler，将 Caddy 配置替换为已验证的
   `deploy/Caddyfile.shared` 并热重载；保留旧 PostgreSQL/Redis 容器与数据卷。
9. 验证公网登录页、401 门禁、管理员登录/改密、226+ 期数据、确定性排名和日志。
10. 未经用户另行授权，不发送真实付费 AI 请求。

## 回滚

如果新 API、迁移、数据回填或公网验收失败：停止新服务，恢复旧 Compose/Caddy 配置
和旧镜像，不删除新数据库或旧数据库卷。确认旧域名 live/ready 恢复后再调查。

恢复 Caddy 目标后，重新启动旧 `api worker scheduler` 三个服务即可回滚业务入口；
不执行 `down`，避免意外影响旧 PostgreSQL、Redis、证书和网络。

禁止使用 `docker compose down -v`、删除旧卷或覆盖未经验证的备份。

## 秘密

生产 `.env`、数据库密码、Session pepper、Fernet Key、SSH Key 和一次性管理员凭据
不得进入 Git、镜像、日志或文档。供应商 API Key 只能通过管理员 Web 页面写入并在
数据库中加密保存。
