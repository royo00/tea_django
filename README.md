## tea django

### 账号

| 用途 | 地址 |
| --- | --- |
| 管理后台 | http://localhost:8000/admin/ |
| 门户首页 | http://localhost:8000/home/ |
| 门户登录 / 注册 / 个人中心 | http://localhost:8000/users/login/ · `/users/register/` · `/users/profile/` |

管理员账号 `admin`，初始密码 `admin123`（首次部署后请立即修改）。

### 后台管理（admin）

后台做了品牌化改造，配色与门户站点一致（茶绿主色 + 米金点缀），支持浅色 / 深色两种主题：

| 文件 | 作用 |
| --- | --- |
| `config/urls.py` | 站点文案 `site_header` / `site_title` / `index_title`，并把「查看站点」的 `site_url` 指向 `/home/` |
| `static/css/admin_theme.css` | 后台主题：品牌色变量、页头渐变、模块卡片、表格 / 表单 / 按钮、登录页、仪表盘样式 |
| `templates/admin/base_site.html` | 页头品牌标识（logo + 中英文标题）、favicon、加载主题 CSS |
| `templates/admin/index.html` | 仪表盘：欢迎横幅 + 数据概览卡片 + 应用列表 |
| `templates/admin/login.html` | 登录页：左侧品牌介绍 + 右侧登录表单 |
| `home/templatetags/admin_stats.py` | 仪表盘数据卡片的统计标签（配方 / 原料 / 用户 / 收藏） |

> 想恢复 Django 默认外观，删除 `templates/admin/` 下的自定义模板并移除 `config/urls.py` 中的品牌配置即可。

### 默认数据库配置
驱动：pymysql
地址：http://localhost
端口：3306
数据库名：tea_django
账号：root
密码：123456

#### MySQL 时区表（必做，否则后台报错）

项目 `USE_TZ = True`，admin 的 `date_hierarchy`、`__date` / `__year` 查询都会生成
`CONVERT_TZ(..., 'UTC', 'Asia/Shanghai')`。Windows 版 MySQL 不预装时区数据，
`mysql.time_zone*` 四张表为空时 `CONVERT_TZ` 恒返回 NULL，访问
`/admin/recipes/teaformula/` 会抛：

```
Database returned an invalid datetime value. Are time zone definitions for your database installed?
```

导入时区数据（可重复执行，需要 root 权限）：

```bash
uv run python scripts/import_mysql_timezones.py
# 只导入常用时区：uv run python scripts/import_mysql_timezones.py --only Asia/Shanghai UTC
```

脚本直接解析 tzdata 的 TZif 文件，并额外做了两件 MySQL 官方工具做不到的事：

- 展开 slim 格式尾部的 POSIX TZ 字符串，把 2007 年之后的夏令时切换补齐到 2037 年
- 丢弃超过 2038-01-19 的 transition——只要存在这种记录，MySQL 会整条时区加载失败
  （`Asia/Gaza`、`Asia/Hebron` 就是被这个坑到 `CONVERT_TZ` 返回 NULL）

导入后**需重启 MySQL 服务**清空时区缓存，之前查询过的时区才会用上新数据
（`FLUSH TABLES` 无效，时区缓存独立于表缓存）。

### 用户模块（users）

门户网页走 **Session** 认证，移动 APP 走 **JWT**，两者共用 `users.User` 一张表。

> 完整的接口文档（参数、响应样例、错误码）见 [API.md](API.md)。

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
- 浏览 / 搜索 / 详情均为 `AllowAny`，游客可看；收藏等写接口在 `collects` 模块，要求登录

| 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/recipes/formulas/` | 无 | 首页分页卡片列表 |
| GET | `/api/recipes/formulas/<id>/` | 无 | 配方详情，自动 `view_count += 1` |
| GET | `/api/recipes/search/` | 无 | 搜索入口，等价于 `formulas/?search=` |
| GET | `/api/recipes/tags/` | 无 | 标签列表（只含有上架配方的标签，不分页） |

列表 / 搜索通用查询参数：

| 参数 | 说明 |
| --- | --- |
| `tag` | 标签 id 或标签名，如 `?tag=3`、`?tag=果茶`；**只支持单个标签**，不支持 `?tag=1,2` |
| `search` | 关键词，匹配配方名称**或**原料名称（内部 `distinct()` 去重） |
| `difficulty` | 难度 1-5 |
| `ordering` | `create_time` / `view_count` / `difficulty` / `duration` / `id`，前缀 `-` 倒序，默认 `-create_time` |
| `page` / `page_size` | 页码分页，默认 10 条，最大 50 条 |

响应结构为 DRF 标准分页：`{count, next, previous, results}`。搜索无结果时 `count=0`、`results=[]`，由前端给友好提示。

列表卡片字段：`id / name / cover / difficulty / difficulty_display / duration / temperature_desc / tags[]`；
详情在此基础上多出 `step_content / steps[] / materials[] / view_count / create_time / update_time`，
`materials[]` 已按 `sort_order` 升序，并带 `quantity_display`（如 `"10 g"`）。

### 收藏模块（collects）

`UserCollect` 只有 4 个字段：`id / user_id / formula_id / collect_time`，`(user, formula)` 唯一，重复收藏不会产生脏数据；
另建 `(user, -collect_time)` 复合索引，支撑「我的收藏」按时间翻页。

接口全部要求登录（JWT 或 Session），且只能操作自己的收藏：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/collects/` | 我的收藏列表，`?ordering=-collect_time`（默认，最新在前）/ `collect_time`（最早在前）/ `id` |
| POST | `/api/collects/` | 添加收藏 `{"formula_id": 1}`，新建返回 201，已收藏返回 200 且 `created=false` |
| DELETE | `/api/collects/<formula_id>/` | 取消收藏，成功 204，未收藏 404 |
| GET | `/api/collects/<formula_id>/status/` | 查询是否已收藏，未收藏也返回 200 + `collected=false` |

- 列表项结构：`{id, collect_time, formula: {…配方卡片字段…}}`，`formula` 直接复用配方模块的卡片序列化器，APP 端可共用一套渲染逻辑
- 列表项**不含 `formula_id`**，配方 id 在 `formula.id`（`item.id` 是收藏记录 id）
- 只收藏上架配方；配方下架后自动从收藏列表隐藏，收藏记录仍保留（重新上架即恢复），`count` 只统计可见的收藏
- 分页默认 20 条，`page_size` 可调，上限 50

### 常用命令

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py runserver
uv run python manage.py test users
uv run python manage.py test recipes
uv run python manage.py test collects
uv run python manage.py seed_recipes        # 导入演示配方数据（--reset 先清空）
```
