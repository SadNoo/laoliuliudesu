# API 契约

所有业务接口使用 `/api/v1`，成功与失败都返回 `request_id`。

## 公开接口

- `GET /health/live`
- `GET /health/ready`
- `POST /api/v1/auth/login`

## 登录接口

- `GET /api/v1/auth/me`：返回当前用户并轮换内存 CSRF Token。
- `POST /api/v1/auth/change-password`
- `POST /api/v1/auth/logout`
- `GET /api/v1/draws?page=1&page_size=30`
- `GET /api/v1/analysis/latest`
- `POST /api/v1/analysis/ai`
- `GET /api/v1/analysis/runs`

除登录和只读 GET 外，写接口必须带 `X-CSRF-Token`。业务会话通过 HttpOnly Cookie
传递，不返回给 JavaScript。

## 管理员接口

- `GET /api/v1/admin/users`
- `POST /api/v1/admin/users`
- `PATCH /api/v1/admin/users/{id}/status`
- `GET /api/v1/admin/ai-provider`
- `PUT /api/v1/admin/ai-provider`
- `POST /api/v1/admin/sync/history`
- `POST /api/v1/admin/sync/current`
- `GET /api/v1/admin/sync-runs`

AI 配置查询只返回 `has_api_key`，绝不返回完整 Key 或密文。

## 错误信封

```json
{
  "success": false,
  "data": null,
  "error": {"code": "AUTHENTICATION_REQUIRED", "message": "请先登录"},
  "request_id": "..."
}
```
