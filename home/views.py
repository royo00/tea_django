from django.shortcuts import render


# ---------------------------------------------------------------------------
# 门户首页数据（后续可迁移到 models / fixtures，模板结构无需改动）
# ---------------------------------------------------------------------------

TEA_CATEGORIES = [
    {
        "name": "绿茶",
        "en": "Green Tea",
        "emoji": "🍃",
        "ferment": "不发酵 · 0%",
        "desc": "杀青定香，汤色清亮。代表：西湖龙井、碧螺春、黄山毛峰。",
        "tags": ["鲜爽", "豆香", "春茶"],
        "count": 26,
        "color_from": "#3e9b6b",
        "color_to": "#a8ddc3",
    },
    {
        "name": "白茶",
        "en": "White Tea",
        "emoji": "🌾",
        "ferment": "微发酵 · 5-10%",
        "desc": "不炒不揉，萎凋成茶。代表：白毫银针、白牡丹、寿眉。",
        "tags": ["清甜", "毫香", "可陈化"],
        "count": 14,
        "color_from": "#b9b58f",
        "color_to": "#ecebd8",
    },
    {
        "name": "黄茶",
        "en": "Yellow Tea",
        "emoji": "🌼",
        "ferment": "闷黄 · 10-20%",
        "desc": "闷黄出甜，小众而珍稀。代表：君山银针、蒙顶黄芽。",
        "tags": ["甜醇", "粟香", "稀少"],
        "count": 8,
        "color_from": "#c9a227",
        "color_to": "#f4e2a4",
    },
    {
        "name": "乌龙茶",
        "en": "Oolong Tea",
        "emoji": "🫖",
        "ferment": "半发酵 · 15-70%",
        "desc": "做青摇香，花果并蓄。代表：铁观音、大红袍、凤凰单丛。",
        "tags": ["花果香", "回甘", "耐泡"],
        "count": 32,
        "color_from": "#7a4a2b",
        "color_to": "#d9a463",
    },
    {
        "name": "红茶",
        "en": "Black Tea",
        "emoji": "🍂",
        "ferment": "全发酵 · 80-90%",
        "desc": "发酵生甜，汤色红亮。代表：正山小种、金骏眉、祁门红茶。",
        "tags": ["蜜香", "醇厚", "百搭"],
        "count": 29,
        "color_from": "#9d4b34",
        "color_to": "#e0a184",
    },
    {
        "name": "黑茶",
        "en": "Dark Tea",
        "emoji": "🪵",
        "ferment": "后发酵 · 100%",
        "desc": "渥堆陈化，越陈越香。代表：普洱熟茶、六堡茶、茯砖。",
        "tags": ["陈香", "醇滑", "解腻"],
        "count": 18,
        "color_from": "#4a3a2c",
        "color_to": "#a58a6c",
    },
    {
        "name": "花茶",
        "en": "Scented Tea",
        "emoji": "🌺",
        "ferment": "窨制 · 再加工",
        "desc": "以花窨茶，香气入汤。代表：茉莉花茶、桂花乌龙、玫瑰红茶。",
        "tags": ["花香", "层次", "低咖"],
        "count": 21,
        "color_from": "#b0629a",
        "color_to": "#f2c6e0",
    },
    {
        "name": "奶茶",
        "en": "Milk Tea",
        "emoji": "🥛",
        "ferment": "调和 · 现制",
        "desc": "茶底与奶制的配比实验：珍珠、芋泥、生椰、厚乳。",
        "tags": ["奶香", "厚乳", "热销"],
        "count": 45,
        "color_from": "#8c5f4a",
        "color_to": "#e3bda0",
    },
    {
        "name": "果茶",
        "en": "Fruit Tea",
        "emoji": "🍑",
        "ferment": "冷萃 · 现制",
        "desc": "鲜果与茶汤的清爽组合：柠檬、蜜桃、杨梅、青提。",
        "tags": ["清爽", "低糖", "夏日"],
        "count": 38,
        "color_from": "#c9574f",
        "color_to": "#f6c3a8",
    },
]

SEASON_FEATURED = [
    {
        "name": "冷萃茉莉银针",
        "category": "花茶 · 冷萃",
        "desc": "4℃ 冷萃 6 小时，茉莉香更细腻，尾段带银针的清甜。",
        "time": "6 小时",
        "temp": "4℃",
        "level": "入门",
        "color_from": "#b0629a",
        "color_to": "#e8cfe4",
    },
    {
        "name": "蜜桃乌龙气泡",
        "category": "果茶 · 气泡",
        "desc": "单丛茶底加蜜桃果泥，气泡水补满，甜度 30% 最平衡。",
        "time": "10 分钟",
        "temp": "冰饮",
        "level": "进阶",
        "color_from": "#d1795c",
        "color_to": "#f8d3bd",
    },
    {
        "name": "陈皮普洱厚乳",
        "category": "奶茶 · 热饮",
        "desc": "熟普与陈皮同煮，厚乳打发后注入，咸甜交织不腻口。",
        "time": "25 分钟",
        "temp": "85℃",
        "level": "进阶",
        "color_from": "#6a4a34",
        "color_to": "#c9a184",
    },
    {
        "name": "桂花金骏眉",
        "category": "红茶 · 热泡",
        "desc": "90℃ 定点注水，出汤 25 秒，起杯前撒干桂花提香。",
        "time": "5 分钟",
        "temp": "90℃",
        "level": "入门",
        "color_from": "#9d4b34",
        "color_to": "#e6b48f",
    },
]

RANKING = [
    {"name": "生椰拿铁茶", "category": "奶茶", "views": "12.6k"},
    {"name": "杨梅冰乌龙", "category": "果茶", "views": "9.8k"},
    {"name": "冷萃茉莉银针", "category": "花茶", "views": "8.4k"},
    {"name": "陈皮普洱厚乳", "category": "奶茶", "views": "7.1k"},
    {"name": "桂花金骏眉", "category": "红茶", "views": "6.5k"},
]

BREW_GUIDE = [
    {
        "title": "绿茶 · 80℃ 玻璃杯上投法",
        "open": True,
        "body": "先注水至七分满，水温 80℃ 左右，再投入 3g 茶叶，静置 1 分钟即可饮用。"
                "避免沸水直冲，否则茶多酚析出过快会发苦。",
    },
    {
        "title": "乌龙茶 · 100℃ 盖碗快出汤",
        "body": "茶水比 1:15，沸水高冲激发香气，前 3 泡控制在 15-20 秒出汤，之后每泡递增 5 秒，可冲泡 7 泡以上。",
    },
    {
        "title": "红茶 · 90℃ 留根续泡",
        "body": "90℃ 水温、3g 茶、150ml 水，闷泡 2 分钟后出汤，每次留 1/3 茶汤再续水，口感更稳定。",
    },
    {
        "title": "黑茶 · 先醒茶再煮饮",
        "body": "紧压茶先以沸水快速润洗 1-2 次唤醒茶性；老茶可投入煮茶壶，水沸后转小火煮 3-5 分钟，陈香更足。",
    },
]

BREW_TABLE = [
    {"name": "绿茶", "temp": "80℃", "time": "1 分钟"},
    {"name": "白茶（新）", "temp": "85℃", "time": "2 分钟"},
    {"name": "黄茶", "temp": "85℃", "time": "2 分钟"},
    {"name": "乌龙茶", "temp": "100℃", "time": "15-20 秒"},
    {"name": "红茶", "temp": "90℃", "time": "2 分钟"},
    {"name": "黑茶", "temp": "100℃", "time": "20 秒 / 煮饮"},
    {"name": "花茶", "temp": "85℃", "time": "2 分钟"},
]

NEWS = [
    {"date": "10 / 28", "title": "秋茶季：凤凰单丛新茶上市，蜜兰香批次已入库", "tag": "茶事"},
    {"date": "10 / 21", "title": "配方更新：新增 6 款低糖果茶，含完整糖度换算表", "tag": "更新"},
    {"date": "10 / 14", "title": "器具测评：5 款常用盖碗的出水与聚香对比", "tag": "测评"},
    {"date": "10 / 07", "title": "冲泡参数表修订，补全白茶与黄茶的注水手法", "tag": "指南"},
]

STATS = [
    {"number": "9", "label": "茶类图谱"},
    {"number": "231", "label": "收录配方"},
    {"number": "48", "label": "冲泡参数"},
    {"number": "12k+", "label": "茶友订阅"},
]


def index(request):
    """门户首页：导航与页脚由 base.html 提供，此处只负责内容区数据。"""
    context = {
        "tea_categories": TEA_CATEGORIES,
        "season_featured": SEASON_FEATURED,
        "ranking": RANKING,
        "brew_guide": BREW_GUIDE,
        "brew_table": BREW_TABLE,
        "news": NEWS,
        "stats": STATS,
    }
    return render(request, "home/index.html", context)
