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

### 配方模块（recipes）

5 张表：`Material` 原料、`TeaFormula` 配方、`FormulaMaterial` 配方用料、`Tag` 标签、`FormulaTag` 配方标签。

几个约定：

- 制作步骤不建表，存在 `TeaFormula.step_content`（纯文本，一行一步），接口额外返回拆好的 `steps` 数组
- 所有对外接口只返回 `is_on_shelf=True` 的配方，未上架配方对 APP 完全不可见
- `FormulaMaterial.material` 用 `PROTECT`，被配方引用的原料无法删除
- `TeaFormula` 建了 `(is_on_shelf, -create_time)` 和 `(is_on_shelf, -view_count)` 两个复合索引
- 浏览 / 搜索 / 详情均为 `AllowAny`，游客可看；收藏等写接口后续再要求 JWT

| 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/recipes/formulas/` | 无 | 首页分页卡片列表 |
| GET | `/api/recipes/formulas/<id>/` | 无 | 配方详情，自动 `view_count += 1` |
| GET | `/api/recipes/search/` | 无 | 搜索入口，等价于 `formulas/?search=` |
| GET | `/api/recipes/tags/` | 无 | 标签列表（只含有上架配方的标签，不分页） |

列表 / 搜索通用查询参数：

| 参数 | 说明 |
| --- | --- |
| `tag` | 标签 id 或标签名，如 `?tag=3`、`?tag=果茶` |
| `search` | 关键词，匹配配方名称**或**原料名称（内部 `distinct()` 去重） |
| `difficulty` | 难度 1-5 |
| `ordering` | `create_time` / `view_count` / `difficulty` / `duration` / `id`，前缀 `-` 倒序，默认 `-create_time` |
| `page` / `page_size` | 页码分页，默认 10 条，最大 50 条 |

响应结构为 DRF 标准分页：`{count, next, previous, results}`。搜索无结果时 `count=0`、`results=[]`，由前端给友好提示。

列表卡片字段：`id / name / cover / difficulty / difficulty_display / duration / temperature_desc / tags[]`；
详情在此基础上多出 `step_content / steps[] / materials[] / view_count / create_time / update_time`，
`materials[]` 已按 `sort_order` 升序，并带 `quantity_display`（如 `"10 g"`）。

### 常用命令

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py runserver
uv run python manage.py test users
uv run python manage.py test recipes
uv run python manage.py seed_recipes        # 导入演示配方数据（--reset 先清空）
```
