"""在 django shell 里手动插入一条配方的最小示例。

两种运行方式（推荐第 1 种）：

    1) 一条命令跑完
       python manage.py shell -c "exec(open('scripts/seed_one_in_shell.py', encoding='utf-8').read())"

    2) 进交互式 shell 再执行
       python manage.py shell
       >>> exec(open("scripts/seed_one_in_shell.py", encoding="utf-8").read())

注意：不要用 `manage.py shell < 文件` —— 交互式控制台是逐行读取的，
遇到缩进块（for / if / with）会报 IndentationError。

要点：
  - Material 的 name 有 unique 约束，必须 get_or_create，不能直接 create
  - cover 是 ImageField，赋值时传「相对 MEDIA_ROOT 的路径」，不是绝对路径
  - 用料和标签是独立表，得先有配方对象才能挂
  - PROTECT 外键：配方引用的原料不能删，插数据前先建原料
"""

import urllib.request
from pathlib import Path

from django.conf import settings

from recipes.models import FormulaMaterial, FormulaTag, Material, Tag, TeaFormula

# --------------------------------------------------------------------------
# 1. 原料：先建原料，配方才能引用（PROTECT 外键，不能引用不存在的原料）
# --------------------------------------------------------------------------
material_data = [
    ("乌龙茶", "茶叶", "铁观音或冻顶乌龙"),
    ("白桃", "水果", "可用糖水桃罐头替代"),
    ("纯净水", "其他", ""),
    ("冰块", "其他", ""),
]
for name, category, remark in material_data:
    Material.objects.get_or_create(name=name, defaults={"category": category, "remark": remark})

# --------------------------------------------------------------------------
# 2. 标签
# --------------------------------------------------------------------------
for tag_name in ["果茶", "冰饮", "低糖"]:
    Tag.objects.get_or_create(name=tag_name)

# --------------------------------------------------------------------------
# 3. 封面：下载到 media/covers/seed/，数据库里只存相对路径
# --------------------------------------------------------------------------
COVER_DIR = Path(settings.MEDIA_ROOT) / "covers" / "seed"
COVER_DIR.mkdir(parents=True, exist_ok=True)
cover_file = COVER_DIR / "peach-oolong-cold-brew.jpg"
if not cover_file.exists():
    url = "https://images.unsplash.com/photo-1499638673689-79a0b5115d87?w=800&q=80&fm=jpg"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        cover_file.write_bytes(resp.read())

# --------------------------------------------------------------------------
# 4. 配方主体
# --------------------------------------------------------------------------
formula, created = TeaFormula.objects.get_or_create(
    name="白桃乌龙冷泡",
    defaults={
        "cover": "covers/seed/peach-oolong-cold-brew.jpg",  # 相对 MEDIA_ROOT
        "difficulty": 2,
        "duration": 250,
        "temperature_desc": "冰饮 5℃",
        "step_content": "\n".join([
            "1. 乌龙茶 8g 装入冷泡壶。",
            "2. 注入 500ml 冷水，冷藏静置 4 小时。",
            "3. 白桃切块，取一半轻压出汁。",
            "4. 杯中放冰块、白桃果肉，倒入冷泡乌龙。",
        ]),
        "is_on_shelf": True,
    },
)
print("配方:", formula.name, "新建" if created else "已存在，跳过")

# --------------------------------------------------------------------------
# 5. 用料（sort_order 决定前端展示顺序）
# --------------------------------------------------------------------------
for order, (name, qty, unit) in enumerate(
    [("乌龙茶", 8, "g"), ("白桃", 120, "g"), ("纯净水", 500, "ml"), ("冰块", 150, "g")],
    start=1,
):
    FormulaMaterial.objects.get_or_create(
        formula=formula,
        material=Material.objects.get(name=name),
        defaults={"quantity": qty, "unit": unit, "sort_order": order},
    )

# 6. 标签关联（FormulaTag 有 uniq_formula_tag 约束，用 get_or_create 幂等）
for tag_name in ["果茶", "冰饮", "低糖"]:
    FormulaTag.objects.get_or_create(formula=formula, tag=Tag.objects.get(name=tag_name))

print("已插入用料与标签")
print("当前配方总数:", TeaFormula.objects.count())
