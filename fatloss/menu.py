from __future__ import annotations

from .models import DinnerRecipe, MealOption, Profile


LUNCH_LIBRARY: list[MealOption] = [
    MealOption("食堂", "一荤一素半碗饭", 560, 34, ["优先选清蒸鱼、鸡腿去皮、瘦牛肉或豆腐", "米饭半碗到一小碗", "蔬菜要双份"], ["少选红烧肉、炸鸡排、勾芡重油菜"]),
    MealOption("盖饭", "番茄牛肉盖饭减饭版", 620, 38, ["请老板米饭少一点", "加一份青菜或海带", "汤汁少浇"], ["避开肥牛重油、糖醋、咖喱浓汁"]),
    MealOption("面/粉", "牛肉面加蛋少汤少油", 590, 35, ["面量少一点", "加卤蛋或豆干", "多要青菜"], ["少喝汤底，少加辣油"]),
    MealOption("麻辣烫", "清汤麻辣烫高蛋白版", 520, 36, ["选鸡蛋、虾滑、豆腐、鸡肉片", "绿叶菜、菌菇、海带占一半", "主食只选一小份粉或土豆"], ["不要油碟、丸子堆满、方便面"]),
    MealOption("便利店", "便利店鸡胸饭团组合", 510, 33, ["鸡胸肉或茶叶蛋两份", "搭配饭团或玉米", "加无糖酸奶或蔬菜杯"], ["不选奶茶、甜面包、炸物"]),
    MealOption("快餐", "汉堡店去酱高蛋白组合", 650, 38, ["选烤鸡堡或牛肉堡", "酱料减半", "饮料换无糖，薯条换玉米或沙拉"], ["不点双层芝士、甜饮、炸鸡桶"]),
    MealOption("小店", "黄焖鸡少饭多菜版", 640, 42, ["鸡肉优先吃瘦肉", "米饭半份", "加青菜或豆腐"], ["少喝汤汁，少选肥皮"]),
]


DINNER_LIBRARY: list[DinnerRecipe] = [
    DinnerRecipe(
        "番茄鸡蛋虾仁豆腐饭",
        25,
        610,
        45,
        ["虾仁 120g", "鸡蛋 1 个", "嫩豆腐 150g", "番茄 1 个", "青菜 250g", "米饭半碗"],
        ["番茄炒出汁后加豆腐和虾仁", "鸡蛋滑熟后回锅", "青菜清炒或水煮", "米饭控制在半碗到一小碗"],
        {"蛋白质": "虾仁、鸡蛋、豆腐", "蔬菜": "番茄、青菜", "主食": "半碗米饭", "调味": "少油，盐和生抽点到为止"},
    ),
    DinnerRecipe(
        "青椒牛肉菌菇饭",
        30,
        650,
        48,
        ["瘦牛肉 130g", "青椒 1 个", "菌菇 200g", "生菜 200g", "米饭半碗"],
        ["牛肉用生抽和淀粉薄薄抓匀", "热锅少油快炒牛肉后盛出", "青椒菌菇炒软后牛肉回锅", "生菜做成清爽配菜"],
        {"蛋白质": "瘦牛肉", "蔬菜": "青椒、菌菇、生菜", "主食": "半碗米饭", "调味": "少油快炒，不用重酱"},
    ),
    DinnerRecipe(
        "蒜香鸡腿肉西兰花杂粮饭",
        30,
        680,
        50,
        ["去皮鸡腿肉 150g", "西兰花 250g", "胡萝卜 80g", "杂粮饭半碗", "蒜末少量"],
        ["鸡腿肉去皮切块", "少油煎熟后加蒜末和黑胡椒", "西兰花胡萝卜焯水后回锅", "杂粮饭半碗即可"],
        {"蛋白质": "去皮鸡腿肉", "蔬菜": "西兰花、胡萝卜", "主食": "半碗杂粮饭", "调味": "蒜香、黑胡椒、少盐"},
    ),
    DinnerRecipe(
        "豆腐鱼片白菜汤配红薯",
        28,
        570,
        43,
        ["鱼片 150g", "嫩豆腐 150g", "白菜 300g", "红薯 150g", "姜片"],
        ["红薯蒸熟", "白菜和姜片煮汤", "加入豆腐和鱼片煮熟", "出锅前少盐和白胡椒"],
        {"蛋白质": "鱼片、豆腐", "蔬菜": "白菜", "主食": "红薯", "调味": "汤菜少油，姜和白胡椒提味"},
    ),
]


def _contains_blocked_food(text: str, blocked: list[str]) -> bool:
    lowered = text.lower()
    return any(item.lower() in lowered for item in blocked if item)


def lunch_options_for(profile: Profile, limit: int = 4) -> list[MealOption]:
    allowed_places = set(profile.lunch_places or [])
    blocked = profile.avoid_foods + profile.disliked_foods
    options = [
        item for item in LUNCH_LIBRARY
        if (not allowed_places or item.category in allowed_places)
        and not _contains_blocked_food(item.title, blocked)
    ]
    if len(options) < limit:
        for item in LUNCH_LIBRARY:
            if item not in options and not _contains_blocked_food(item.title, blocked):
                options.append(item)
    return options[:limit]


def dinner_recipe_for(profile: Profile) -> DinnerRecipe:
    blocked = profile.avoid_foods + profile.disliked_foods
    candidates = [
        item for item in DINNER_LIBRARY
        if item.cook_minutes <= profile.dinner_minutes
        and not _contains_blocked_food(" ".join([item.title, *item.ingredients]), blocked)
    ]
    if not candidates:
        candidates = [item for item in DINNER_LIBRARY if not _contains_blocked_food(" ".join([item.title, *item.ingredients]), blocked)]
    return candidates[0] if candidates else DINNER_LIBRARY[0]

