# 茶饮配方手册 · REST API 文档

> 基于 Django REST Framework 3.18 + SimpleJWT 5.5 构建，服务于移动 APP 与门户网页。
> 文档版本 v1.1 · 最后更新 2026-10-31

---

## 目录

1. [概览](#1-概览)
2. [认证机制](#2-认证机制)
3. [通用约定](#3-通用约定)
4. [用户模块 `/api/users/`](#4-用户模块-apiusers)
5. [配方模块 `/api/recipes/`](#5-配方模块-apirecipes)
6. [收藏模块 `/api/collects/`](#6-收藏模块-apicollects)
7. [数据字典](#7-数据字典)
8. [典型业务流程](#8-典型业务流程)
9. [错误码附录](#9-错误码附录)

---

## 1. 概览

| 项目 | 说明 |
| --- | --- |
| 开发环境 Base URL | `http://localhost:8000` |
| 请求/响应格式 | `application/json; charset=utf-8` |
| 文件上传 | `multipart/form-data` |
| 时间格式 | `YYYY-MM-DD HH:MM:SS`，时区 `Asia/Shanghai`（北京时间，无时区后缀） |
| 分页方式 | 页码分页，参数 `page` / `page_size` |
| 认证方式 | JWT（移动 APP）/ Session Cookie（门户网页） |
| 调试入口 | 浏览器直接访问任意 GET 接口可打开 DRF 可视化调试页 |

所有业务接口都在 `/api/` 前缀下，按领域分为三组：

```
/api/users/      用户注册、登录、资料、头像、密码
/api/recipes/    配方浏览、搜索、详情、标签
/api/collects/   收藏列表、添加、取消、状态查询
```

---

## 2. 认证机制

系统同时支持两条认证通道，**同一套接口两端通用**。

| 通道 | 适用端 | 凭证 | 实现 |
| --- | --- | --- | --- |
| JWT | 移动 APP | `Authorization: Bearer <access>` | `rest_framework_simplejwt` |
| Session | 门户网页 | `sessionid` Cookie | `django.contrib.sessions` |

DRF 的认证顺序为 `JWTAuthentication → SessionAuthentication`，先尝试 Bearer 头，失败再回落 Session。

### 2.1 账号说明

- 登录账号支持**用户名**或**手机号**，由自定义认证后端 `UsernameOrPhoneBackend` 统一处理。
- 用户名与手机号都全局唯一；手机号可为空，为空时不影响登录。

### 2.2 Token 有效期

| Token | 有效期 | 说明 |
| --- | --- | --- |
| `access` | 2 小时 | 放请求头，过期后返回 401 |
| `refresh` | 14 天 | 只用于换新 access，不要放请求头 |

> ⚠️ **刷新会轮换 refresh token**
> 项目开启了 `ROTATE_REFRESH_TOKENS` + `BLACKLIST_AFTER_ROTATION`：每调用一次 `token/refresh/`，服务端会返回**新的 refresh**，同时把旧的加入黑名单立即失效。
> **客户端必须用响应里的新 refresh 覆盖本地旧值**，否则下次刷新会 401。这也是推荐做法——refresh token 泄露后只能被用一次。

### 2.3 请求头示例

```http
GET /api/users/me/ HTTP/1.1
Host: localhost:8000
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### 2.4 未认证时的响应

```json
{ "detail": "身份认证信息未提供。" }
```

状态码 `401`。前端捕获 401 后应引导用户重新登录（或用 refresh 换新 access 后重试一次）。

---

## 3. 通用约定

### 3.1 分页

列表接口统一返回以下信封结构：

```json
{
  "count": 6,
  "next": "http://localhost:8000/api/recipes/formulas/?page=2&page_size=2",
  "previous": null,
  "results": []
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `count` | int | 过滤后的总条数 |
| `next` | string \| null | 下一页完整地址，无则为 `null` |
| `previous` | string \| null | 上一页完整地址，无则为 `null` |
| `results` | array | 当前页数据 |

分页参数：`?page=1&page_size=10`。页码越界返回 `404 {"detail": "无效页面。"}`。

各模块默认值不同：

| 模块 | 默认 `page_size` | 最大 `page_size` | 是否分页 |
| --- | --- | --- | --- |
| 配方列表 | 10 | 50 | 是 |
| 收藏列表 | 20 | 50 | 是 |
| 标签列表 | — | — | **否**，直接返回数组 |

### 3.2 排序

列表接口通过 `?ordering=<field>` 控制排序，`-` 前缀表示倒序。**非白名单字段会被静默忽略并回落到默认排序**，不会报错（例如 `?ordering=-name` 等价于不传）。

| 模块 | 白名单字段 | 默认排序 |
| --- | --- | --- |
| 配方 | `create_time` `view_count` `difficulty` `duration` `id` | `-create_time, -id` |
| 收藏 | `collect_time` `id` | `-collect_time, -id` |

> **次级排序固定为 `-id`**：当排序字段取值相同时（同一秒创建的两条配方、同一秒收藏的两条记录），按 id 倒序兜底，保证翻页顺序稳定，不会出现重复项或漏项。显式指定 `?ordering=collect_time` 时次级排序仍是 `-id`。

### 3.3 错误响应格式

**字段校验失败（400）** —— 以字段名为 key：

```json
{
  "formula_id": ["配方不存在或已下架"]
}
```

```json
{
  "password": ["This password is too short. It must contain at least 8 characters.", "这个密码太常见了。"],
  "phone": ["该手机号已被注册"]
}
```

DRF 内置校验器的文案已中文化，字段缺失 / 类型错误也是同样的结构，可直接展示：

```json
{ "formula_id": ["该字段是必填项。"] }
```

```json
{ "formula_id": ["请填写合法的整数值。"] }
```

**通用错误（401 / 404 / 405）** —— 统一用 `detail` 字段：

```json
{ "detail": "尚未收藏该配方" }
```

> 提示：`password` 字段的错误可能同时返回中英双语，因为部分校验器来自 Django 内置翻译，APP 端建议原样展示数组首项，不要按文案做逻辑判断。

### 3.4 布尔与数值类型注意

- `quantity`（用量）是**字符串**，如 `"10.00"`，因为后端用 `DecimalField` 保证精度。APP 端需要转成数字再计算。
- `cover`、`avatar` 无图时为 `null`，有图时是**绝对 URL**（如 `http://localhost:8000/media/covers/2026/10/xxx.jpg`）。

---

## 4. 用户模块 `/api/users/`

| 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- |
| POST | `/api/users/register/` | 否 | 注册 |
| POST | `/api/users/token/` | 否 | 换取 JWT |
| POST | `/api/users/token/refresh/` | 否 | 刷新 access |
| POST | `/api/users/logout/` | 是 | 登出（拉黑 refresh） |
| GET | `/api/users/session/` | 否 | 查询 Session 登录态 |
| POST | `/api/users/session/login/` | 否 | 门户 AJAX 登录 |
| POST | `/api/users/session/logout/` | 否 | 清空 Session |
| GET / PATCH | `/api/users/me/` | 是 | 读取 / 更新资料 |
| POST / DELETE | `/api/users/me/avatar/` | 是 | 上传 / 删除头像 |
| POST | `/api/users/me/password/` | 是 | 修改密码 |

---

### 4.1 注册

```
POST /api/users/register/
```

无需认证。支持 JSON 或 `multipart/form-data`（需要同时上传头像时用后者）。

**请求参数**

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `username` | string | 是 | 最长 150，唯一（大小写不敏感判重） |
| `password` | string | 是 | 需通过 Django 密码强度校验：至少 8 位、不能纯数字、不能是常见密码 |
| `password_confirm` | string | 是 | 必须与 `password` 一致 |
| `phone` | string | 否 | 11 位大陆手机号，`1[3-9]` 开头，全局唯一；传空串等同未填 |
| `email` | string | 否 | 唯一（大小写不敏感） |
| `avatar` | file | 否 | jpg / png / webp，≤ 2MB，边长 ≤ 4000px |

**请求示例**

```bash
curl -X POST http://localhost:8000/api/users/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "reg_demo",
    "password": "Doc-pass-2026",
    "password_confirm": "Doc-pass-2026",
    "phone": "13900000010"
  }'
```

**成功响应 `201`**（返回完整用户对象）

```json
{
  "id": 5,
  "username": "reg_demo",
  "phone": "13900000010",
  "email": "",
  "avatar": null,
  "display_name": "reg_demo",
  "first_name": "",
  "last_name": "",
  "is_staff": false,
  "is_superuser": false,
  "date_joined": "2026-10-31 11:40:44",
  "last_login": null
}
```

**失败响应 `400`**

```json
{
  "password": ["This password is too short. It must contain at least 8 characters."],
  "phone": ["该手机号已被注册"]
}
```

> 注册接口**不会**自动登录，也不返回 token。APP 端注册成功后需再调 `token/` 换取凭证。

---

### 4.2 获取 Token

```
POST /api/users/token/
```

**请求参数**

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `username` | string | 是 | 用户名**或手机号**，字段名固定为 `username` |
| `password` | string | 是 | 密码 |

```bash
curl -X POST http://localhost:8000/api/users/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "13900000009", "password": "Doc-pass-2026"}'
```

**成功响应 `200`**

```json
{
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Access Token 载荷**（已解码，供 APP 本地渲染用户信息用）

```json
{
  "token_type": "access",
  "exp": 1793425244,
  "iat": 1793418044,
  "jti": "124bb6bf1aee4ed59c8f1dd4fc8922c0",
  "user_id": "4",
  "username": "doc_demo",
  "phone": "13900000009",
  "avatar": ""
}
```

> `user_id` 是**字符串**类型。`avatar` 为空时是空串 `""` 而非 `null`。

**失败响应 `401`**

```json
{ "detail": "No active account found with the given credentials" }
```

账号不存在、密码错误、账号被禁用（`is_active=False`）都会返回同一个 401，不区分原因，避免账号探测。

---

### 4.3 刷新 Token

```
POST /api/users/token/refresh/
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `refresh` | string | 是 | 上一步拿到的 refresh |

**成功响应 `200`**

```json
{
  "access": "eyJ...",
  "refresh": "eyJ..."
}
```

> ⚠️ 响应里**同时包含新的 refresh**，旧的立即失效。客户端务必覆盖本地存储，详见 [2.2](#22-token-有效期)。

**失败响应 `401`**

```json
{ "detail": "Token is invalid", "code": "token_not_valid" }
```

refresh 过期、被拉黑、格式错误都返回此结构，`detail` 文案可能为 `Token is invalid` 或 `Token is invalid or expired`。

---

### 4.4 登出

```
POST /api/users/logout/
Authorization: Bearer <access>
```

把 refresh token 加入黑名单。**需要携带有效的 access 头**（即使 refresh 已过期）。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `refresh` | string | 是 | 要作废的 refresh |

**成功响应 `204`**，无响应体。

**失败响应**

| 状态码 | 响应体 | 场景 |
| --- | --- | --- |
| `400` | `{"detail": "缺少 refresh 字段"}` | 未传 refresh |
| `400` | `{"detail": "refresh token 无效或已失效"}` | refresh 已过期或格式错误 |

> access 本身无法吊销（无状态），登出后应立即清除本地所有 token。

---

### 4.5 查询 Session 状态

```
GET /api/users/session/
```

门户页面初始化时判断登录态用。**不返回 401**，未登录也返回 200。

**未登录 `200`**

```json
{ "authenticated": false, "user": null }
```

**已登录 `200`**

```json
{
  "authenticated": true,
  "user": { "id": 3, "username": "collect_demo", "phone": "13900000001", "...": "..." }
}
```

---

### 4.6 Session 登录 / 登出

```
POST /api/users/session/login/
```

门户 AJAX 登录，成功后服务端写入 `sessionid` Cookie。

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `username` | string | 二选一 | 用户名或手机号 |
| `phone` | string | 二选一 | `username` 的别名，两者取其一即可 |
| `password` | string | 是 | 密码 |

**成功响应 `200`**：返回完整用户对象（同 `me/`）。

**失败响应 `400`**

```json
{ "detail": "账号或密码错误" }
```

```json
{ "detail": "请提供账号和密码" }
```

> 注意与 JWT 的差异：Session 登录失败返回 **400** 且文案为中文，JWT 登录失败返回 **401**。两端错误处理逻辑不要共用。
> 若当前已登录再调此接口，DRF 的 SessionAuthentication 会校验 CSRF，需要带 `X-CSRFToken`。

```
POST /api/users/session/logout/
```

**成功响应 `204`**，无响应体。幂等，未登录调用同样返回 204。

---

### 4.7 获取 / 更新当前用户

```
GET   /api/users/me/
PATCH /api/users/me/
```

同时支持 JWT 与 Session。`PATCH` 为部分更新，**只传需要改的字段**（`PUT` 行为与 `PATCH` 一致）。

**可更新字段**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `email` | string | 唯一，可传空串清空 |
| `phone` | string \| null | 唯一，传空串或 `null` 表示解绑 |
| `first_name` | string | |
| `last_name` | string | |
| `avatar` | file | 走 `multipart/form-data`；一般用下面的专用接口 |

**成功响应 `200`**

```json
{
  "id": 3,
  "username": "collect_demo",
  "phone": "13900000001",
  "email": "",
  "avatar": null,
  "display_name": "collect_demo",
  "first_name": "",
  "last_name": "",
  "is_staff": false,
  "is_superuser": false,
  "date_joined": "2026-10-31 11:37:08",
  "last_login": "2026-10-31 11:37:23"
}
```

**失败响应 `400`**

```json
{ "phone": ["该手机号已被注册"] }
```

---

### 4.8 头像上传 / 删除

```
POST   /api/users/me/avatar/     multipart/form-data，字段名 avatar
DELETE /api/users/me/avatar/
```

**上传限制**：≤ 2MB；仅 jpg / jpeg / png / webp；宽高 ≤ 4000px；必须是可解析的真实图片。

**成功响应 `200`**：返回更新后的用户对象，`avatar` 为绝对 URL。

```json
{
  "id": 3,
  "username": "collect_demo",
  "avatar": "http://localhost:8000/media/avatars/2026/10/6f1c9a2b8d4e4c1f9a7b3d5e2c8f1a0b.jpg",
  "...": "..."
}
```

**失败响应**

| 状态码 | 响应体 |
| --- | --- |
| `400` | `{"detail": "请使用 avatar 字段上传图片"}` |
| `400` | `{"avatar": ["头像不能超过 2MB"]}` |
| `400` | `{"avatar": ["头像仅支持 jpg / png / webp 格式"]}` |

上传新头像会**自动删除旧文件**。`DELETE` 成功同样返回用户对象，`avatar` 变为 `null`。

---

### 4.9 修改密码

```
POST /api/users/me/password/
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `old_password` | string | 是 | 原密码，错误返回 400 |
| `new_password` | string | 是 | 需通过强度校验，且不能与原密码相同 |
| `new_password_confirm` | string | 是 | 必须与 `new_password` 一致 |

**成功响应 `200`**

```json
{ "detail": "密码修改成功" }
```

**失败响应 `400`**

```json
{ "old_password": ["原密码不正确"] }
```

```json
{ "new_password_confirm": ["两次输入的新密码不一致"] }
```

> 走 Session 通道时，改密后服务端会自动续期 Session，用户不会掉线；
> 走 JWT 通道时，**已签发的 access / refresh 不会失效**（无状态），如需强制下线请配合登出接口。

---

## 5. 配方模块 `/api/recipes/`

| 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/recipes/formulas/` | 否 | 配方列表（筛选 + 搜索 + 排序 + 分页） |
| GET | `/api/recipes/search/` | 否 | 与上一接口完全等价（参数、响应、分页全部一致），仅路径不同 |
| GET | `/api/recipes/formulas/<id>/` | 否 | 配方详情 |
| GET | `/api/recipes/tags/` | 否 | 标签列表 |

全部接口 `AllowAny`，**游客可浏览**。统一只返回 `is_on_shelf=True`（已上架）的配方，下架配方对 APP 完全不可见（访问详情返回 404）。

### 5.1 配方列表

```
GET /api/recipes/formulas/
GET /api/recipes/search/        ← 同一视图，参数、响应、分页完全一致，仅路径不同
```

两个路径都支持下面的全部参数，`search/` 并非只能传 `search`（`tag`、`ordering`、`page` 同样生效）。

**查询参数**

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `tag` | string | 标签筛选。纯数字按 id 匹配（`?tag=3`），否则按名称精确匹配、忽略大小写（`?tag=奶茶`）。**只支持单个标签**，不支持 `?tag=1,2` |
| `search` | string | 关键词，匹配**配方名称**或**原料名称**，模糊包含 |
| `q` | string | `search` 的别名，两者都传时 `search` 优先 |
| `difficulty` | int | 难度 1–5，非数字忽略；超出 1–5（如 `99`）返回空列表 |
| `ordering` | string | 排序字段，见 [3.2](#32-排序) |
| `page` / `page_size` | int | 分页，默认 10 / 最大 50；`page_size` 超过 50 按 50 处理，不报错 |

参数可任意组合，多个条件为 `AND` 关系。**参数值非法不会报错**：标签不存在返回空列表（`count: 0`），`difficulty` 非数字则忽略该条件。

- **空值**：`?tag=`、`?search=`、`?ordering=` 传空串等同不传，按无条件处理。
- **多标签**：不支持逗号分隔。`?tag=1,2` 会被当作标签名精确匹配（值不是纯数字），静默返回 `count: 0`，不会提示参数错误。需要多标签筛选时请分多次请求。

**请求示例**

```bash
# 只看奶茶类，按浏览量倒序，每页 1 条（便于演示分页）
curl "http://localhost:8000/api/recipes/formulas/?tag=%E5%A5%B6%E8%8C%B6&ordering=-view_count&page_size=1"

# 搜索含「红茶」的配方（配方名或原料名）
curl "http://localhost:8000/api/recipes/formulas/?search=%E7%BA%A2%E8%8C%B6&page_size=5"
```

**成功响应 `200`**

```json
{
  "count": 2,
  "next": "http://localhost:8000/api/recipes/formulas/?ordering=-view_count&page=2&page_size=1&tag=%E5%A5%B6%E8%8C%B6",
  "previous": null,
  "results": [
    {
      "id": 1,
      "name": "经典红茶奶茶",
      "cover": null,
      "difficulty": 1,
      "difficulty_display": "简单",
      "duration": 8,
      "temperature_desc": "热饮 85℃",
      "tags": [
        { "id": 1, "name": "奶茶" },
        { "id": 4, "name": "热饮" }
      ]
    }
  ]
}
```

> 列表页用的是轻量序列化器，**不含** `step_content` / `materials` / `view_count`。卡片展示所需字段齐全，可直接渲染。

### 5.2 配方详情

```
GET /api/recipes/formulas/<id>/
```

**成功响应 `200`**

```json
{
  "id": 1,
  "name": "经典红茶奶茶",
  "cover": null,
  "difficulty": 1,
  "difficulty_display": "简单",
  "duration": 8,
  "temperature_desc": "热饮 85℃",
  "tags": [
    { "id": 1, "name": "奶茶" },
    { "id": 4, "name": "热饮" }
  ],
  "step_content": "1. 将红茶放入茶壶中。\n2. 加入 300ml 热水，浸泡 5 分钟。\n3. 过滤茶汤，加入牛奶。\n4. 根据个人口味加入适量白砂糖。\n5. 搅拌均匀即可饮用。",
  "steps": [
    "1. 将红茶放入茶壶中。",
    "2. 加入 300ml 热水，浸泡 5 分钟。",
    "3. 过滤茶汤，加入牛奶。",
    "4. 根据个人口味加入适量白砂糖。",
    "5. 搅拌均匀即可饮用。"
  ],
  "materials": [
    { "id": 1, "material_id": 1, "material_name": "红茶", "quantity": "10.00", "unit": "g", "quantity_display": "10 g", "sort_order": 1 },
    { "id": 2, "material_id": 4, "material_name": "牛奶", "quantity": "200.00", "unit": "ml", "quantity_display": "200 ml", "sort_order": 2 },
    { "id": 3, "material_id": 6, "material_name": "白砂糖", "quantity": "15.00", "unit": "g", "quantity_display": "15 g", "sort_order": 3 }
  ],
  "view_count": 3,
  "create_time": "2026-10-31 11:15:09",
  "update_time": "2026-10-31 11:15:09"
}
```

**字段说明**

- `step_content`：原始纯文本，每行一步，保留原始序号。
- `steps`：后端按行切分好的数组，已去掉空行与首尾空格。**APP 建议直接用这个**，不要自己 split。`step_content` 为空时返回空数组 `[]`，不会是 `null`。
- `materials`：已按 `sort_order` 升序排好。没有用料记录时返回 `[]`。
- `quantity` 是字符串 `"10.00"`；`quantity_display` 是去掉尾随零的展示文案 `"10 g"`。
- `cover` 未上传时是 `null`，APP 需自备占位图。

> ⚠️ **每次请求详情，`view_count` 会 +1**，采用数据库侧 `F()` 自增，并发安全。返回的 `view_count` 是自增后的值。
> 前端做预加载、下拉刷新、重复请求都会累计浏览量与 `update_time` 无关（`auto_now` 不会因为计数更新而变化）。

**失败响应 `404`**

```json
{ "detail": "No TeaFormula matches the given query." }
```

id 不存在、或该配方已下架（`is_on_shelf=False`）都返回此 404，不区分原因，避免通过状态码反推下架信息。
路径中的 id 必须是纯数字（路由用 `<int:pk>`），`/formulas/abc/` 不匹配路由，同样返回 404。

### 5.3 标签列表

```
GET /api/recipes/tags/
```

**不分页**，直接返回数组。只返回至少挂了一个**已上架**配方的标签，避免筛出空结果。

**成功响应 `200`**

```json
[
  { "id": 6, "name": "低糖" },
  { "id": 5, "name": "冰饮" },
  { "id": 1, "name": "奶茶" },
  { "id": 2, "name": "果茶" },
  { "id": 4, "name": "热饮" },
  { "id": 3, "name": "纯茶" }
]
```

> 排序按标签 `name` 升序（受数据库排序规则影响，中文不是拼音序，例如上例「低糖」排在「冰饮」前，不是按拼音 l/d 排）。
> 没打标签的配方**不会**出现在按标签筛选的结果里，但仍会出现在配方列表和搜索结果中——列表接口不要求配方必须有标签。

---

## 6. 收藏模块 `/api/collects/`

| 方法 | 路径 | 认证 | 说明 |
| --- | --- | --- | --- |
| GET | `/api/collects/` | **是** | 我的收藏列表 |
| POST | `/api/collects/` | **是** | 添加收藏 |
| DELETE | `/api/collects/<formula_id>/` | **是** | 取消收藏 |
| GET | `/api/collects/<formula_id>/status/` | **是** | 查询某配方收藏状态 |

全部接口要求登录（JWT 或 Session），且**只能操作自己的收藏**，用户之间互不可见。

> 路径里的 `<formula_id>` 是**配方 id**，不是收藏记录 id。设计上是为了让 APP 在详情页只凭当前配方就能取消收藏，省一次查询。

### 6.1 我的收藏列表

```
GET /api/collects/
```

| 参数 | 说明 |
| --- | --- |
| `ordering` | `collect_time`（最早在前）/ `-collect_time`（最新在前，默认）/ `id`；次级排序固定 `-id` |
| `page` / `page_size` | 默认 20 / 最大 50；超过 50 按 50 处理 |

> `ordering=id` 按收藏记录的自增 id 排序，效果等价于「收藏先后」；`collect_time` 对外只精确到秒，同一秒内收藏多条时靠次级 `-id` 兜底，顺序依然稳定。

**成功响应 `200`**

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 3,
      "collect_time": "2026-10-31 11:37:24",
      "formula": {
        "id": 6,
        "name": "原味冷泡绿茶",
        "cover": null,
        "difficulty": 1,
        "difficulty_display": "简单",
        "duration": 240,
        "temperature_desc": "冰饮 5℃",
        "tags": [
          { "id": 6, "name": "低糖" },
          { "id": 5, "name": "冰饮" },
          { "id": 3, "name": "纯茶" }
        ]
      }
    }
  ]
}
```

> `formula` 内层结构与配方列表卡片**完全一致**，APP 可以复用同一个卡片组件与解析逻辑。
> 若收藏的配方后来被下架，该记录会从列表中隐藏（但不会被删除），`count` 也不计入它——**`count` 统计的是「当前可见」的收藏数，不等于该用户在数据库里的收藏总数**。
> ⚠️ **列表项没有 `formula_id` 字段**，配方 id 在 `item.formula.id`。取消收藏时取这个值拼 `DELETE /api/collects/<formula_id>/`，不要拿 `item.id`（那是收藏记录 id）。

### 6.2 添加收藏

```
POST /api/collects/
Content-Type: application/json

{ "formula_id": 1 }
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `formula_id` | int | 是 | 配方 id，必须存在且已上架 |

**首次收藏成功 `201`**

```json
{
  "detail": "收藏成功",
  "created": true,
  "collect": {
    "id": 3,
    "collect_time": "2026-10-31 11:37:24",
    "formula": { "id": 6, "name": "原味冷泡绿茶", "...": "..." }
  }
}
```

**重复收藏 `200`**（幂等，不会产生脏数据）

```json
{
  "detail": "该配方已在收藏中",
  "created": false,
  "collect": { "id": 3, "collect_time": "2026-10-31 11:37:24", "formula": { "...": "..." } }
}
```

> 用 `created` 字段区分「新收藏」与「已存在」。APP 端可以据此决定是否弹提示，但**两个状态都视为收藏成功**，按钮统一置为已收藏。

**失败响应 `400`**

```json
{ "formula_id": ["配方不存在或已下架"] }
```

```json
{ "formula_id": ["该字段是必填项。"] }
```

```json
{ "formula_id": ["请填写合法的整数值。"] }
```

> 三种情况都是字段级错误，APP 可统一取 `formula_id` 数组首项做 toast。未携带有效凭证时返回 `401 {"detail": "身份认证信息未提供。"}`（见 [2.4](#24-未认证时的响应)）。

### 6.3 取消收藏

```
DELETE /api/collects/<formula_id>/
```

**成功响应 `204`**，无响应体。

**失败响应 `404`**

```json
{ "detail": "尚未收藏该配方" }
```

> 幂等性提示：重复取消会返回 404 而非 204。前端把 404 视同「已取消」处理即可，不必报错。
> 本接口**不校验配方是否已上架**：配方下架后虽然不出现在收藏列表里，但仍可直接取消（返回 204）。

### 6.4 查询收藏状态

```
GET /api/collects/<formula_id>/status/
```

详情页初始化收藏按钮状态用。**未收藏也返回 200**，避免前端把 404 当成请求失败。

**已收藏 `200`**

```json
{
  "formula_id": 6,
  "collected": true,
  "collect": {
    "id": 3,
    "collect_time": "2026-10-31 11:37:24",
    "formula": { "id": 6, "name": "原味冷泡绿茶", "...": "..." }
  }
}
```

**未收藏 `200`**

```json
{ "formula_id": 99999, "collected": false, "collect": null }
```

> 配方 id 不存在时同样返回 `collected: false`，不报错。
>
> ⚠️ **本接口不校验配方上架状态，与收藏列表口径不一致**：配方下架后 `collected` 仍为 `true`，`collect.formula` 也会返回该下架配方的完整卡片，但这条记录不会出现在 [6.1 收藏列表](#61-我的收藏列表) 里，也不计入 `count`。
> 正常流程下下架配方的详情页已返回 404，用户走不到这个接口；若 APP 要求任何场景下都与列表一致，请以列表数据为准，或由后端在配方下架时清理对应收藏。

---

## 7. 数据字典

### 7.1 用户对象 `User`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | int | 主键 |
| `username` | string | 用户名，唯一 |
| `phone` | string \| null | 手机号，唯一，可为 `null` |
| `email` | string | 邮箱，未填为空串 `""` |
| `avatar` | string \| null | 头像绝对 URL，无图为 `null` |
| `display_name` | string | 姓名（`first_name`+`last_name`）或用户名 |
| `first_name` | string | 名 |
| `last_name` | string | 姓 |
| `is_staff` | bool | 是否可进 Django 后台 |
| `is_superuser` | bool | 是否超级管理员 |
| `date_joined` | datetime | 注册时间 |
| `last_login` | datetime \| null | 上次登录时间，从未登录为 `null` |

### 7.2 配方卡片 `FormulaCard`（列表 / 收藏内层）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | int | 配方 id |
| `name` | string | 配方名称 |
| `cover` | string \| null | 封面绝对 URL |
| `difficulty` | int | 难度 1–5 |
| `difficulty_display` | string | 难度中文：简单 / 较简单 / 中等 / 较难 / 困难 |
| `duration` | int | 制作耗时（分钟） |
| `temperature_desc` | string | 适用温度描述，如 `热饮 85℃` |
| `tags` | array | `[{id, name}]`，可能为空数组 |

### 7.3 配方详情 `FormulaDetail`

在 `FormulaCard` 全部字段基础上追加：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `step_content` | string | 制作步骤原始文本，`\n` 分行 |
| `steps` | string[] | 按行切分后的步骤数组 |
| `materials` | array | 用料清单，见 7.4 |
| `view_count` | int | 浏览量（本次请求已 +1） |
| `create_time` | datetime | 创建时间 |
| `update_time` | datetime | 更新时间 |

### 7.4 用料 `FormulaMaterial`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | int | 用料行 id |
| `material_id` | int | 原料 id |
| `material_name` | string | 原料名称，如 `红茶` |
| `quantity` | string | 用量，字符串形式的两位小数，如 `"10.00"` |
| `unit` | string | 单位，如 `g` / `ml` / `个` |
| `quantity_display` | string | 展示文案，已去掉尾随零，如 `10 g` |
| `sort_order` | int | 展示顺序，升序 |

### 7.5 收藏记录 `UserCollect`

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | int | 收藏记录 id |
| `collect_time` | datetime | 收藏时间 |
| `formula` | object | 配方卡片 `FormulaCard` |

---

## 8. 典型业务流程

### 8.1 APP 冷启动到收藏一条配方

```text
1. GET  /api/recipes/formulas/?page_size=10         → 首页卡片列表（游客可看）
2. 用户点击「收藏」但未登录
3. POST /api/users/token/  {username: 手机号, password}
   ← {access, refresh}    本地安全存储
4. POST /api/collects/  {formula_id: 1}  + Bearer
   ← 201 {created: true}
5. 进入详情页：
   GET /api/recipes/formulas/1/            → 详情（浏览量 +1）
   GET /api/collects/1/status/             → {collected: true} 点亮按钮
```

### 8.2 access 过期后的处理

```text
GET /api/users/me/  → 401 {"detail": "身份认证信息未提供。"}
  ↓
POST /api/users/token/refresh/  {refresh}
  ← 200 {access: 新, refresh: 新}     ⚠️ 两个都要覆盖本地
  ↓
重试原请求
```

若 refresh 也返回 401，说明 14 天有效期已过或被拉黑，清空本地凭证并跳登录页。

### 8.3 门户网页

```text
1. GET  /api/users/session/            → {authenticated: false}
2. 表单提交 POST /users/login/          → 302 到个人中心（页面级 Session 登录）
   或 AJAX  POST /api/users/session/login/  → 200 + Set-Cookie
3. 之后所有请求自动带 sessionid Cookie
4. POST /api/users/session/logout/     → 204
```

> 门户的页面路由（`/users/login/`、`/users/profile/`）是 Django 模板视图，不属于本 API 文档范围。

---

## 9. 错误码附录

| 状态码 | 含义 | 常见场景 |
| --- | --- | --- |
| `200` | 成功 | GET 查询、重复收藏、PATCH 更新 |
| `201` | 已创建 | 注册、首次收藏 |
| `204` | 成功无内容 | 登出、取消收藏、删除头像 |
| `400` | 参数校验失败 | 字段格式错误、密码不一致、手机号重复、Session 登录失败 |
| `401` | 未认证 / 凭证无效 | 未带 token、token 过期、JWT 登录账号密码错误 |
| `404` | 资源不存在 | 配方不存在或已下架、收藏不存在、页码越界 |
| `405` | 方法不允许 | 对只接受 POST 的接口发 GET |
| `500` | 服务端异常 | 需查后端日志 |

### 已知的响应不一致点（对接时注意）

1. **登录失败状态码不同**：JWT 登录失败 `401`，Session 登录失败 `400`。
2. **详情 404 文案是英文**：`No TeaFormula matches the given query.`，来自 DRF 默认实现；其余 404 文案为中文。
3. **重复取消收藏返回 404**，而非幂等的 204。
4. **`quantity` 是字符串**，不是数字。
5. **刷新 token 会换新 refresh**，忘记覆盖会导致下次刷新失败。
6. **筛选参数非法不报错**，标签不存在时静默返回空列表。
7. **收藏状态与收藏列表口径不一致**：配方下架后 `status/` 仍返回 `collected: true`，但该记录不在列表里、不计入 `count`（详见 [6.4](#64-查询收藏状态)）。
8. **`tag` 不支持多值**：`?tag=1,2` 不会报错，会当作标签名匹配并返回空列表。
9. **收藏列表 `count` 只统计上架配方的收藏**，不等于用户收藏总数。

---

## 变更记录

| 版本 | 日期 | 内容 |
| --- | --- | --- |
| v1.0 | 2026-10-31 | 首版：用户 / 配方 / 收藏三模块，共 18 个接口 |
| v1.1 | 2026-10-31 | 按实际接口行为核实配方与收藏模块：补充 `tag` 单值限制与空值处理、`difficulty` 超范围、`page_size` 超限截断、次级排序 `-id`、`steps`/`materials` 空数组；明确收藏列表项无 `formula_id`、`count` 只统计上架配方、`status/` 与列表在下架场景的口径差异、取消收藏不校验上架；修正 5.1 分页示例不自洽与 5.3 标签说明表述 |
