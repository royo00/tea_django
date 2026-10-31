"""初始化茶饮配方演示数据：python manage.py seed_recipes

幂等：原料/标签按名称 get_or_create，配方按名称跳过已存在的。
加 --reset 会先清空配方相关数据（不动物料主数据）。
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from recipes.models import FormulaMaterial, FormulaTag, Material, Tag, TeaFormula

MATERIALS = [
    ("红茶", "茶叶", "祁门红茶，香气醇厚"),
    ("绿茶", "茶叶", "龙井或碧螺春均可"),
    ("乌龙茶", "茶叶", "铁观音"),
    ("牛奶", "乳制品", "全脂牛奶口感更好"),
    ("淡奶油", "乳制品", "打发用"),
    ("白砂糖", "糖类", ""),
    ("蜂蜜", "糖类", "调味用"),
    ("柠檬", "水果", "切片去籽，避免发苦"),
    ("百香果", "水果", ""),
    ("芒果", "水果", ""),
    ("珍珠", "小料", "煮后过冷水更弹"),
    ("椰果", "小料", ""),
    ("冰块", "其他", ""),
]

TAGS = ["奶茶", "果茶", "纯茶", "热饮", "冰饮", "低糖"]

# name, difficulty, duration, temperature, tags, steps, materials[(原料, 用量, 单位)]
FORMULAS = [
    {
        "name": "经典红茶奶茶",
        "difficulty": 1,
        "duration": 8,
        "temperature_desc": "热饮 85℃",
        "tags": ["奶茶", "热饮"],
        "steps": [
            "1. 将红茶放入茶壶中。",
            "2. 加入 300ml 热水，浸泡 5 分钟。",
            "3. 过滤茶汤，加入牛奶。",
            "4. 根据个人口味加入适量白砂糖。",
            "5. 搅拌均匀即可饮用。",
        ],
        "materials": [("红茶", 10, "g"), ("牛奶", 200, "ml"), ("白砂糖", 15, "g")],
    },
    {
        "name": "冰镇柠檬茶",
        "difficulty": 2,
        "duration": 12,
        "temperature_desc": "冰饮 5℃",
        "tags": ["果茶", "冰饮", "低糖"],
        "steps": [
            "1. 红茶用 90℃ 热水冲泡 4 分钟，滤出茶汤。",
            "2. 茶汤中加入白砂糖搅拌至融化，放凉。",
            "3. 柠檬切片去籽，取 2 片轻压出汁。",
            "4. 杯中放入冰块，倒入茶汤与柠檬片。",
            "5. 摇匀后即可享用。",
        ],
        "materials": [("红茶", 8, "g"), ("柠檬", 2, "片"), ("白砂糖", 10, "g"), ("冰块", 150, "g")],
    },
    {
        "name": "珍珠乌龙奶茶",
        "difficulty": 3,
        "duration": 25,
        "temperature_desc": "常温 / 可加冰",
        "tags": ["奶茶"],
        "steps": [
            "1. 珍珠倒入沸水煮 20 分钟，关火焖 5 分钟。",
            "2. 捞出珍珠过冷水，拌入蜂蜜备用。",
            "3. 乌龙茶用 95℃ 热水冲泡 3 分钟。",
            "4. 茶汤与牛奶按 1:1 混合，加入珍珠。",
            "5. 依口味补糖，搅拌均匀。",
        ],
        "materials": [("乌龙茶", 8, "g"), ("牛奶", 150, "ml"), ("珍珠", 50, "g"), ("蜂蜜", 10, "g")],
    },
    {
        "name": "百香果绿茶",
        "difficulty": 2,
        "duration": 10,
        "temperature_desc": "冰饮 8℃",
        "tags": ["果茶", "冰饮"],
        "steps": [
            "1. 绿茶用 85℃ 热水冲泡 3 分钟，滤出放凉。",
            "2. 百香果对半切开，挖出果肉放入杯中。",
            "3. 加入蜂蜜搅匀。",
            "4. 倒入绿茶与冰块，搅拌后饮用。",
        ],
        "materials": [("绿茶", 6, "g"), ("百香果", 1, "个"), ("蜂蜜", 15, "g"), ("冰块", 120, "g")],
    },
    {
        "name": "芒果椰果奶昔",
        "difficulty": 2,
        "duration": 15,
        "temperature_desc": "冰饮 4℃",
        "tags": ["果茶", "冰饮"],
        "steps": [
            "1. 芒果去皮切块，留少许果粒装饰。",
            "2. 芒果块、牛奶、淡奶油一起倒入搅拌机打 30 秒。",
            "3. 杯底铺椰果，倒入打好的奶昔。",
            "4. 表面放芒果粒，冷藏 5 分钟后口感更佳。",
        ],
        "materials": [("芒果", 150, "g"), ("牛奶", 120, "ml"), ("淡奶油", 40, "ml"), ("椰果", 30, "g")],
    },
    {
        "name": "原味冷泡绿茶",
        "difficulty": 1,
        "duration": 240,
        "temperature_desc": "冰饮 5℃",
        "tags": ["纯茶", "冰饮", "低糖"],
        "steps": [
            "1. 绿茶 5g 放入冷泡壶。",
            "2. 注入 500ml 常温纯净水。",
            "3. 冷藏静置 4 小时。",
            "4. 滤出茶叶，直接饮用或加冰。",
        ],
        "materials": [("绿茶", 5, "g"), ("冰块", 100, "g")],
    },
]


class Command(BaseCommand):
    help = "初始化茶饮配方演示数据（原料 / 标签 / 配方 / 用料）"

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="先清空配方、用料、标签关联再重建")

    @transaction.atomic
    def handle(self, *args, **options):
        if options["reset"]:
            FormulaMaterial.objects.all().delete()
            FormulaTag.objects.all().delete()
            TeaFormula.objects.all().delete()
            self.stdout.write(self.style.WARNING("已清空配方相关数据"))

        for name, category, remark in MATERIALS:
            Material.objects.get_or_create(
                name=name, defaults={"category": category, "remark": remark},
            )
        for name in TAGS:
            Tag.objects.get_or_create(name=name)

        created = 0
        for data in FORMULAS:
            if TeaFormula.objects.filter(name=data["name"]).exists():
                continue
            formula = TeaFormula.objects.create(
                name=data["name"],
                difficulty=data["difficulty"],
                duration=data["duration"],
                temperature_desc=data["temperature_desc"],
                step_content="\n".join(data["steps"]),
                is_on_shelf=True,
            )
            for order, (material_name, quantity, unit) in enumerate(data["materials"], start=1):
                FormulaMaterial.objects.create(
                    formula=formula,
                    material=Material.objects.get(name=material_name),
                    quantity=quantity,
                    unit=unit,
                    sort_order=order,
                )
            for tag_name in data["tags"]:
                FormulaTag.objects.create(formula=formula, tag=Tag.objects.get(name=tag_name))
            created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"完成：新增配方 {created} 条，原料 {Material.objects.count()} 个，标签 {Tag.objects.count()} 个"
            )
        )
