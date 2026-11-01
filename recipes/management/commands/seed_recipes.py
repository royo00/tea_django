"""初始化茶饮配方演示数据：python manage.py seed_recipes

幂等：原料/标签按名称 get_or_create，配方按名称跳过已存在的。
加 --reset 会先清空配方相关数据（不动物料主数据）。
加 --no-cover 跳过封面图下载（离线环境用）。

封面图来自 Unsplash（免费可商用，无需署名），下载后落到
media/covers/seed/<slug>.jpg，数据库里只存相对路径，
接口返回时会自动拼成绝对 URL。
"""

import urllib.error
import urllib.request
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from recipes.models import FormulaMaterial, FormulaTag, Material, Tag, TeaFormula

# (名称, 分类, 备注)
MATERIALS = [
    ("红茶", "茶叶", "祁门红茶，香气醇厚"),
    ("绿茶", "茶叶", "龙井或碧螺春均可"),
    ("乌龙茶", "茶叶", "铁观音"),
    ("伯爵红茶", "茶叶", "佛手柑香气的调味红茶"),
    ("茉莉花茶", "茶叶", "茉莉绿茶，香气清扬"),
    ("抹茶粉", "茶叶", "过筛后更易溶解"),
    ("牛奶", "乳制品", "全脂牛奶口感更好"),
    ("淡奶油", "乳制品", "打发用"),
    ("炼乳", "乳制品", "增稠提香"),
    ("白砂糖", "糖类", ""),
    ("黑糖", "糖类", "熬糖浆用"),
    ("蜂蜜", "糖类", "调味用"),
    ("柠檬", "水果", "切片去籽，避免发苦"),
    ("百香果", "水果", ""),
    ("芒果", "水果", ""),
    ("草莓", "水果", "去蒂对半切"),
    ("柚子", "水果", "取果肉，白瓤去净"),
    ("珍珠", "小料", "煮后过冷水更弹"),
    ("椰果", "小料", ""),
    ("桂花", "花草", "干桂花，出锅前撒"),
    ("玫瑰花", "花草", "干玫瑰花冠"),
    ("薰衣草", "花草", "用量宜少，易发苦"),
    ("红枣", "干货", "去核切片"),
    ("桂圆干", "干货", ""),
    ("薄荷", "香草", "新鲜叶片拍醒"),
    ("冰块", "其他", ""),
    ("纯净水", "其他", ""),
]

TAGS = ["奶茶", "果茶", "纯茶", "热饮", "冰饮", "低糖"]

# cover 是 Unsplash photo id，拼成 https://images.unsplash.com/photo-<id>
# slug 用于封面文件名，避免中文名落到磁盘上
FORMULAS = [
    {
        "name": "经典红茶奶茶",
        "slug": "classic-black-tea-milk",
        "cover": "1544787219-7f47ccb76574",
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
        "slug": "iced-lemon-tea",
        "cover": "1556679343-c7306c1976bc",
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
        "slug": "boba-oolong-milk-tea",
        "cover": "1558857563-b371033873b8",
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
        "slug": "passion-fruit-green-tea",
        "cover": "1499638673689-79a0b5115d87",
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
        "slug": "mango-coconut-smoothie",
        "cover": "1525385133512-2f3bdd039054",
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
        "slug": "cold-brew-green-tea",
        "cover": "1571934811356-5cc061b6821f",
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
        "materials": [("绿茶", 5, "g"), ("纯净水", 500, "ml"), ("冰块", 100, "g")],
    },
    {
        "name": "抹茶拿铁",
        "slug": "matcha-latte",
        "cover": "1515823064-d6e0c04616a7",
        "difficulty": 3,
        "duration": 12,
        "temperature_desc": "热饮 70℃",
        "tags": ["奶茶", "热饮"],
        "steps": [
            "1. 抹茶粉 5g 过筛入碗，避免结块。",
            "2. 加 60ml 70℃ 热水，用茶筅 W 形打发至起细泡。",
            "3. 牛奶加热至 65℃，打出一层薄奶泡。",
            "4. 抹茶液倒入杯中，缓缓注入热牛奶。",
            "5. 表面拉花或直接撒少许抹茶粉点缀。",
        ],
        "materials": [("抹茶粉", 5, "g"), ("牛奶", 220, "ml"), ("白砂糖", 8, "g")],
    },
    {
        "name": "草莓茉莉冰茶",
        "slug": "strawberry-jasmine-iced-tea",
        "cover": "1560508180-03f285f67ded",
        "difficulty": 1,
        "duration": 10,
        "temperature_desc": "冰饮 5℃",
        "tags": ["果茶", "冰饮"],
        "steps": [
            "1. 茉莉花茶用 85℃ 热水冲泡 3 分钟，滤出放凉。",
            "2. 草莓去蒂，一半压成果泥，一半对半切。",
            "3. 杯底放果泥与蜂蜜，倒入茶汤搅匀。",
            "4. 加满冰块，放入草莓块与薄荷叶装饰。",
        ],
        "materials": [("茉莉花茶", 6, "g"), ("草莓", 100, "g"), ("蜂蜜", 15, "g"), ("薄荷", 3, "片"), ("冰块", 150, "g")],
    },
    {
        "name": "蜂蜜柚子茶",
        "slug": "honey-yuzu-tea",
        "cover": "1523371054106-bbf80586c38c",
        "difficulty": 2,
        "duration": 20,
        "temperature_desc": "冰饮 / 热饮皆可",
        "tags": ["果茶", "低糖"],
        "steps": [
            "1. 柚子果肉剥散，白瓤尽量去净以免发苦。",
            "2. 果肉与蜂蜜按 1:1 拌匀，冷藏腌 2 小时成柚子蜜。",
            "3. 取 2 勺柚子蜜放入杯中。",
            "4. 冲入 80℃ 热水或冰水，搅匀即可。",
        ],
        "materials": [("柚子", 200, "g"), ("蜂蜜", 200, "g"), ("纯净水", 300, "ml")],
    },
    {
        "name": "桂花乌龙",
        "slug": "osmanthus-oolong",
        "cover": "1564890369478-c89ca6d9cde9",
        "difficulty": 2,
        "duration": 8,
        "temperature_desc": "热饮 95℃",
        "tags": ["纯茶", "热饮", "低糖"],
        "steps": [
            "1. 乌龙茶用沸水快速润洗一遍，倒掉头道水。",
            "2. 再次注入 95℃ 热水，浸泡 1 分钟出汤。",
            "3. 茶汤倒入公道杯，撒入干桂花。",
            "4. 静置 30 秒待桂花香气散开，趁热饮用。",
        ],
        "materials": [("乌龙茶", 8, "g"), ("桂花", 2, "g"), ("纯净水", 300, "ml")],
    },
    {
        "name": "玫瑰红枣花茶",
        "slug": "rose-red-date-tea",
        "cover": "1597318181409-cf64d0b5d8a2",
        "difficulty": 1,
        "duration": 15,
        "temperature_desc": "热饮 90℃",
        "tags": ["热饮", "低糖"],
        "steps": [
            "1. 红枣去核切片，与桂圆干一同放入壶中。",
            "2. 注入 90℃ 热水 400ml，焖泡 8 分钟。",
            "3. 放入干玫瑰花，再焖 2 分钟。",
            "4. 依口味加少许蜂蜜，温热饮用。",
        ],
        "materials": [("玫瑰花", 5, "朵"), ("红枣", 3, "颗"), ("桂圆干", 10, "g"), ("蜂蜜", 10, "g"), ("纯净水", 400, "ml")],
    },
    {
        "name": "英式伯爵红茶",
        "slug": "earl-grey-tea",
        "cover": "1576092768241-dec231879fc3",
        "difficulty": 1,
        "duration": 6,
        "temperature_desc": "热饮 95℃",
        "tags": ["纯茶", "热饮"],
        "steps": [
            "1. 温杯后放入伯爵红茶茶包。",
            "2. 注入 95℃ 热水 250ml。",
            "3. 浸泡 3 分钟，取出茶包不要挤压。",
            "4. 可加一片柠檬或少量牛奶调味。",
        ],
        "materials": [("伯爵红茶", 5, "g"), ("纯净水", 250, "ml")],
    },
    {
        "name": "薄荷柠檬绿茶",
        "slug": "mint-lemon-green-tea",
        "cover": "1621263764928-df1444c5e859",
        "difficulty": 2,
        "duration": 10,
        "temperature_desc": "冰饮 6℃",
        "tags": ["果茶", "冰饮", "低糖"],
        "steps": [
            "1. 绿茶用 80℃ 热水冲泡 2 分钟，滤出放凉。",
            "2. 柠檬切片，薄荷叶拍醒出香。",
            "3. 杯中依次放冰块、柠檬片、薄荷叶。",
            "4. 倒入绿茶，加少量蜂蜜调匀。",
        ],
        "materials": [("绿茶", 5, "g"), ("柠檬", 3, "片"), ("薄荷", 6, "片"), ("蜂蜜", 10, "g"), ("冰块", 150, "g")],
    },
    {
        "name": "桂圆红枣暖红茶",
        "slug": "longan-red-date-black-tea",
        "cover": "1594631252845-29fc4cc8cde9",
        "difficulty": 1,
        "duration": 18,
        "temperature_desc": "热饮 90℃",
        "tags": ["热饮", "低糖"],
        "steps": [
            "1. 红枣去核、桂圆干略冲洗。",
            "2. 红枣桂圆加 400ml 水小火煮 10 分钟。",
            "3. 放入红茶，关火焖 3 分钟。",
            "4. 滤渣后倒入杯中，趁热喝。",
        ],
        "materials": [("红茶", 6, "g"), ("红枣", 4, "颗"), ("桂圆干", 12, "g"), ("纯净水", 400, "ml")],
    },
    {
        # 故意下架，用于验证「下架配方不出现在列表/详情 404」的逻辑
        "name": "薰衣草奶茶（下架测试）",
        "slug": "lavender-milk-tea-off-shelf",
        "cover": "1523920290228-4f321a939b4c",
        "difficulty": 4,
        "duration": 15,
        "temperature_desc": "热饮 80℃",
        "is_on_shelf": False,
        "tags": ["奶茶", "热饮"],
        "steps": [
            "1. 薰衣草 1g 与红茶一同用 85℃ 水冲泡 4 分钟。",
            "2. 滤出茶汤，注意不要久泡以免发苦。",
            "3. 加入热牛奶与炼乳搅匀。",
        ],
        "materials": [("薰衣草", 1, "g"), ("红茶", 6, "g"), ("牛奶", 180, "ml"), ("炼乳", 10, "g")],
    },
]

COVER_DIR = Path(settings.MEDIA_ROOT) / "covers" / "seed"
UNSPLASH = "https://images.unsplash.com/photo-{photo_id}?w=800&q=80&fm=jpg&fit=crop"


def fetch_cover(photo_id: str, slug: str) -> str | None:
    """下载封面到 MEDIA_ROOT/covers/seed/<slug>.jpg，返回相对 MEDIA_ROOT 的路径。"""
    COVER_DIR.mkdir(parents=True, exist_ok=True)
    target = COVER_DIR / f"{slug}.jpg"
    if not target.exists():
        url = UNSPLASH.format(photo_id=photo_id)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                target.write_bytes(resp.read())
        except (urllib.error.URLError, TimeoutError, OSError):
            return None
    return f"covers/seed/{target.name}"


class Command(BaseCommand):
    help = "初始化茶饮配方演示数据（原料 / 标签 / 配方 / 用料 / 封面图）"

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="先清空配方、用料、标签关联再重建")
        parser.add_argument("--no-cover", action="store_true", help="跳过封面图下载")

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

        material_map = {m.name: m for m in Material.objects.all()}
        tag_map = {t.name: t for t in Tag.objects.all()}

        created = skipped = no_cover = backfilled = 0
        for data in FORMULAS:
            existing = TeaFormula.objects.filter(name=data["name"]).first()
            if existing is not None:
                # 已存在则不动业务字段，只在缺封面时补一张，方便老数据升级
                skipped += 1
                if not options["no_cover"] and data.get("cover") and not existing.cover:
                    cover_path = fetch_cover(data["cover"], data["slug"])
                    if cover_path:
                        existing.cover = cover_path
                        existing.save(update_fields=["cover"])
                        backfilled += 1
                continue

            cover_path = None
            if not options["no_cover"] and data.get("cover"):
                cover_path = fetch_cover(data["cover"], data["slug"])
                if cover_path is None:
                    no_cover += 1
                    self.stdout.write(self.style.WARNING(f"  封面下载失败：{data['name']}"))

            formula = TeaFormula.objects.create(
                name=data["name"],
                cover=cover_path or "",
                difficulty=data["difficulty"],
                duration=data["duration"],
                temperature_desc=data["temperature_desc"],
                step_content="\n".join(data["steps"]),
                is_on_shelf=data.get("is_on_shelf", True),
            )
            for order, (material_name, quantity, unit) in enumerate(data["materials"], start=1):
                FormulaMaterial.objects.create(
                    formula=formula,
                    material=material_map[material_name],
                    quantity=quantity,
                    unit=unit,
                    sort_order=order,
                )
            for tag_name in data["tags"]:
                FormulaTag.objects.create(formula=formula, tag=tag_map[tag_name])
            created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"完成：新增配方 {created} 条（跳过已存在 {skipped} 条，补封面 {backfilled} 条，"
                f"封面缺失 {no_cover} 条）｜"
                f"当前共 {TeaFormula.objects.count()} 条配方、{Material.objects.count()} 个原料、"
                f"{Tag.objects.count()} 个标签、{FormulaMaterial.objects.count()} 条用料"
            )
        )
