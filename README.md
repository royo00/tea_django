## tea django

### 账号

| 用途 | 地址 |
| --- | --- |
| 管理后台 | http://localhost:8000/admin/ |
| 门户首页 | http://localhost:8000/home/ |
| 门户登录 / 注册 / 个人中心 | http://localhost:8000/users/login/ · `/users/register/` · `/users/profile/` |

管理员账号 `admin`，初始密码 `admin123`（首次部署后请立即修改）。

### 用户模块（users）

门户网页走 **Session** 认证，移动 APP 走 **JWT**，两者共用 `users.User` 一张表。
`users.User` 在 Django 自带 `AbstractUser` 基础上扩展了：

- `phone`：11 位手机号，唯一，可为空（MySQL 下多个 NULL 不冲突），可作登录账号
- `avatar`：头像，存 `media/avatars/YYYY/MM/`，限 2MB 的 jpg / png / webp

### 门户路由（Session）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET/POST | `/users/login/` | 登录，用户名或手机号均可 |
| POST | `/users/logout/` | 登出（仅 POST，防 CSRF） |
| GET/POST | `/users/register/` | 注册并自动登录 |
| GET/POST | `/users/profile/` | 个人中心，编辑资料与头像 |
| GET/POST | `/users/password/change/` | 修改密码 |

### API 路由（`/api/users/`）

| 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- |
| POST | `register/` | 无 | 注册，返回用户信息 |
| POST | `token/` | 无 | `{username, password}` → `{access, refresh}`，username 处可填手机号 |
| POST | `token/refresh/` | 无 | 刷新 access（开启轮换，旧 refresh 自动拉黑） |
| POST | `logout/` | JWT | `{refresh}` → 加入黑名单 |
| GET | `session/` | 无 | 查询 Session 登录态 |
| POST | `session/login/` | 无 | 门户 AJAX 登录，写 Session Cookie |
| POST | `session/logout/` | 无 | 清空 Session |
| GET/PATCH | `me/` | JWT 或 Session | 读取 / 更新当前用户资料 |
| POST/DELETE | `me/avatar/` | JWT 或 Session | multipart 上传 / 删除头像 |
| POST | `me/password/` | JWT 或 Session | 修改密码 |

APP 端请求头：`Authorization: Bearer <access>`。Token 有效期 access 2 小时、refresh 14 天。

### 常用命令

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py runserver
uv run python manage.py test users
```
