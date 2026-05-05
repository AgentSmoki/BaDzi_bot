"""Symbolic Stars (神煞) reference tables.

All tables are sourced from the canonical Chinese metaphysics texts
(三命通会, 渊海子平, 神峰通考, 协纪辨方书, 命理探源, 滴天髓), via Gemini Deep Research
v2 (2026-05-05). See doc/research/symbolic_stars_v2_gemini.md for provenance.

Stars are split by anchor type. Each detector in symbolic_stars.py picks the
right table family.

Skipped from this v1 set (require non-trivial logic, deferred to v2):
  - 元辰 (yuanchen, dynamic ±1 from clash branch by year polarity)
  - 勾绞 (goujiao, dynamic ±3 by year polarity)
  - 空亡 (kongwang, requires Xun/decade computation — separate task 2.1.5)
"""

from __future__ import annotations

from dataclasses import dataclass

# ── Star metadata ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class StarMeta:
    name_zh: str
    name_pinyin: str
    name_ru: str
    category: str
    nature: str
    source: str


META: dict[str, StarMeta] = {
    "tianyi": StarMeta(
        "天乙贵人", "tianyi guiren", "Тяньи Благородный", "noble", "auspicious", "三命通会"
    ),
    "taiji": StarMeta(
        "太极贵人", "taiji guiren", "Тайцзи Благородный", "noble", "auspicious", "三命通会"
    ),
    "wenchang": StarMeta(
        "文昌贵人", "wenchang guiren", "Вэньчан", "academic", "auspicious", "渊海子平"
    ),
    "fuxing": StarMeta(
        "福星贵人", "fuxing guiren", "Звезда Счастья", "noble", "auspicious", "三命通会"
    ),
    "guoyin": StarMeta(
        "国印贵人", "guoyin guiren", "Печать Государства", "career", "auspicious", "渊海子平"
    ),
    "tiande": StarMeta(
        "天德贵人", "tiande guiren", "Небесная Добродетель", "noble", "auspicious", "三命通会"
    ),
    "yuede": StarMeta(
        "月德贵人", "yuede guiren", "Лунная Добродетель", "noble", "auspicious", "三命通会"
    ),
    "tiande_he": StarMeta(
        "天德合", "tiande he", "Слияние Небесной Добродетели", "noble", "auspicious", "三命通会"
    ),
    "yuede_he": StarMeta(
        "月德合", "yuede he", "Слияние Лунной Добродетели", "noble", "auspicious", "三命通会"
    ),
    "xuetang": StarMeta("学堂", "xuetang", "Академия", "academic", "auspicious", "三命通会"),
    "ciguan": StarMeta(
        "词馆", "ciguan", "Словесный Павильон", "academic", "auspicious", "渊海子平"
    ),
    "lushen": StarMeta("禄神", "lushen", "Вознаграждение", "wealth", "auspicious", "渊海子平"),
    "yangren": StarMeta("羊刃", "yangren", "Овечий Нож", "violence", "mixed", "三命通会"),
    "feiren": StarMeta("飞刃", "feiren", "Летящий Нож", "violence", "inauspicious", "神峰通考"),
    "jinyu": StarMeta("金舆", "jinyu", "Золотая Карета", "wealth", "auspicious", "三命通会"),
    "hongyan": StarMeta("红艳", "hongyan", "Красная Красота", "romance", "mixed", "三命通会"),
    "liuxia": StarMeta("流霞", "liuxia", "Летящая Заря", "violence", "inauspicious", "渊海子平"),
    "taohua": StarMeta("桃花", "taohua xianchi", "Цветок Персика", "romance", "mixed", "三命通会"),
    "yima": StarMeta("驿马", "yima", "Почтовая Лошадь", "travel", "mixed", "三命通会"),
    "huagai": StarMeta("华盖", "huagai", "Цветущий Балдахин", "spiritual", "mixed", "三命通会"),
    "jiangxing": StarMeta(
        "将星", "jiangxing", "Звезда Генерала", "career", "auspicious", "三命通会"
    ),
    "jiesha": StarMeta("劫煞", "jiesha", "Звезда Грабежа", "calamity", "inauspicious", "三命通会"),
    "zaisha": StarMeta("灾煞", "zaisha", "Звезда Бедствий", "calamity", "inauspicious", "三命通会"),
    "tiansha": StarMeta("天煞", "tiansha", "Небесный Ша", "calamity", "inauspicious", "神峰通考"),
    "yuesha": StarMeta("月煞", "yuesha", "Лунный Ша", "calamity", "inauspicious", "协纪辨方书"),
    "wangshen": StarMeta(
        "亡神", "wangshen", "Звезда Смерти", "death_grave", "inauspicious", "三命通会"
    ),
    "liue": StarMeta("六厄", "liue", "Шесть Бедствий", "calamity", "inauspicious", "渊海子平"),
    "panan": StarMeta("攀鞍", "panan", "Седло", "career", "auspicious", "三命通会"),
    "suiyi": StarMeta("岁驿", "suiyi", "Годовая Почтовая Лошадь", "travel", "mixed", "协纪辨方书"),
    "kuigang": StarMeta("魁罡", "kuigang", "Куй Ган", "punishment", "mixed", "三命通会"),
    "guchen": StarMeta(
        "孤辰", "guchen", "Звезда Одиночества", "loneliness", "inauspicious", "三命通会"
    ),
    "guasu": StarMeta("寡宿", "guasu", "Звезда Вдовы", "loneliness", "inauspicious", "三命通会"),
    "yinchayangcuo": StarMeta(
        "阴差阳错", "yinchayangcuo", "Инь-Ян Ошибка", "romance", "inauspicious", "三命通会"
    ),
    "tongzisha": StarMeta(
        "童子煞", "tongzisha", "Звезда Монаха", "spiritual", "inauspicious", "中国神煞大全"
    ),
    "tianluodiwang": StarMeta(
        "天罗地网", "tianluodiwang", "Сети Небес и Земли", "punishment", "inauspicious", "渊海子平"
    ),
    "xueren": StarMeta("血刃", "xueren", "Кровавый Нож", "violence", "inauspicious", "神峰通考"),
    "dahao": StarMeta("大耗", "dahao", "Большие Потери", "wealth", "inauspicious", "三命通会"),
    "xiaohao": StarMeta("小耗", "xiaohao", "Малые Потери", "wealth", "inauspicious", "三命通会"),
    "jielukongwang": StarMeta(
        "截路空亡",
        "jielukongwang",
        "Преграждающая Пустота",
        "death_grave",
        "inauspicious",
        "三命通会",
    ),
    "shiedabai": StarMeta(
        "十恶大败",
        "shiedabai",
        "Десять Непростительных Зол",
        "calamity",
        "inauspicious",
        "三命通会",
    ),
    "feifu": StarMeta(
        "飞符", "feifu", "Летящий Талисман", "punishment", "inauspicious", "协纪辨方书"
    ),
    "pima": StarMeta("披麻", "pima", "Траурные Одежды", "death_grave", "inauspicious", "神峰通考"),
    "sangmen": StarMeta(
        "丧门", "sangmen", "Врата Похорон", "death_grave", "inauspicious", "三命通会"
    ),
    "diaoke": StarMeta(
        "吊客", "diaoke", "Скорбящий Гость", "death_grave", "inauspicious", "三命通会"
    ),
    "baihu": StarMeta("白虎", "baihu", "Белый Тигр", "violence", "inauspicious", "渊海子平"),
    "tianyi_doctor": StarMeta(
        "天医", "tianyi yi", "Небесный Врач", "longevity", "auspicious", "三命通会"
    ),
    "jieshen": StarMeta("解神", "jieshen", "Звезда Освобождения", "noble", "auspicious", "滴天髓"),
    "tianshe": StarMeta("天赦", "tianshe", "Небесное Прощение", "noble", "auspicious", "渊海子平"),
    "tianxi": StarMeta("天喜", "tianxi", "Небесная Радость", "romance", "auspicious", "三命通会"),
    "hongluan": StarMeta("红鸾", "hongluan", "Красный Феникс", "romance", "auspicious", "三命通会"),
    "guluan": StarMeta(
        "孤鸾", "guluan", "Одинокий Феникс", "loneliness", "inauspicious", "神峰通考"
    ),
    "jinshen_advance": StarMeta(
        "进神", "jinshen", "Бог Продвижения", "career", "auspicious", "三命通会"
    ),
    "tuishen": StarMeta("退神", "tuishen", "Бог Отступления", "career", "inauspicious", "三命通会"),
    "jinshen_gold": StarMeta("金神", "jinshen", "Золотой Дух", "career", "mixed", "三命通会"),
    "ride": StarMeta("日德", "ride", "Добродетель Дня", "noble", "auspicious", "三命通会"),
    "rigui": StarMeta("日贵", "rigui", "Благородный Дня", "noble", "auspicious", "三命通会"),
    "anlu": StarMeta("暗禄", "anlu", "Скрытое Богатство", "wealth", "auspicious", "三命通会"),
    "tianguan": StarMeta(
        "天官贵人", "tianguan guiren", "Небесный Чиновник", "noble", "auspicious", "中国神煞大全"
    ),
    "tianfu": StarMeta(
        "天福贵人", "tianfu guiren", "Небесное Благополучие", "noble", "auspicious", "中国神煞大全"
    ),
    "tianchu": StarMeta(
        "天厨贵人", "tianchu guiren", "Небесная Кухня", "noble", "auspicious", "三命通会"
    ),
}


# ── Group A: anchor=day_stem, target=branch (search day's stem → list of branches in chart) ──

# Star ID → {day_stem → [target branches]}
DAY_STEM_TO_BRANCH: dict[str, dict[str, tuple[str, ...]]] = {
    "tianyi": {
        "甲": ("丑", "未"),
        "乙": ("子", "申"),
        "丙": ("亥", "酉"),
        "丁": ("亥", "酉"),
        "戊": ("丑", "未"),
        "己": ("子", "申"),
        "庚": ("丑", "未"),
        "辛": ("午", "寅"),
        "壬": ("卯", "巳"),
        "癸": ("卯", "巳"),
    },
    "taiji": {
        "甲": ("子", "午"),
        "乙": ("子", "午"),
        "丙": ("卯", "酉"),
        "丁": ("卯", "酉"),
        "戊": ("辰", "戌", "丑", "未"),
        "己": ("辰", "戌", "丑", "未"),
        "庚": ("寅", "亥"),
        "辛": ("寅", "亥"),
        "壬": ("巳", "申"),
        "癸": ("巳", "申"),
    },
    "wenchang": {
        "甲": ("巳",),
        "乙": ("午",),
        "丙": ("申",),
        "丁": ("酉",),
        "戊": ("申",),
        "己": ("酉",),
        "庚": ("亥",),
        "辛": ("子",),
        "壬": ("寅",),
        "癸": ("卯",),
    },
    "fuxing": {
        "甲": ("寅", "子"),
        "乙": ("卯", "丑"),
        "丙": ("寅", "子"),
        "丁": ("亥",),
        "戊": ("申",),
        "己": ("未",),
        "庚": ("午",),
        "辛": ("巳",),
        "壬": ("辰",),
        "癸": ("卯", "丑"),
    },
    "guoyin": {
        "甲": ("戌",),
        "乙": ("亥",),
        "丙": ("丑",),
        "丁": ("寅",),
        "戊": ("丑",),
        "己": ("寅",),
        "庚": ("辰",),
        "辛": ("巳",),
        "壬": ("未",),
        "癸": ("申",),
    },
    "xuetang": {
        "甲": ("亥",),
        "乙": ("午",),
        "丙": ("寅",),
        "丁": ("酉",),
        "戊": ("寅",),
        "己": ("酉",),
        "庚": ("巳",),
        "辛": ("子",),
        "壬": ("申",),
        "癸": ("卯",),
    },
    "ciguan": {
        "甲": ("寅",),
        "乙": ("亥",),
        "丙": ("巳",),
        "丁": ("寅",),
        "戊": ("巳",),
        "己": ("寅",),
        "庚": ("申",),
        "辛": ("巳",),
        "壬": ("亥",),
        "癸": ("申",),
    },
    "lushen": {
        "甲": ("寅",),
        "乙": ("卯",),
        "丙": ("巳",),
        "丁": ("午",),
        "戊": ("巳",),
        "己": ("午",),
        "庚": ("申",),
        "辛": ("酉",),
        "壬": ("亥",),
        "癸": ("子",),
    },
    "yangren": {
        "甲": ("卯",),
        "乙": ("寅",),
        "丙": ("午",),
        "丁": ("巳",),
        "戊": ("午",),
        "己": ("巳",),
        "庚": ("酉",),
        "辛": ("申",),
        "壬": ("子",),
        "癸": ("亥",),
    },
    "feiren": {
        "甲": ("酉",),
        "乙": ("申",),
        "丙": ("子",),
        "丁": ("亥",),
        "戊": ("子",),
        "己": ("亥",),
        "庚": ("卯",),
        "辛": ("寅",),
        "壬": ("午",),
        "癸": ("巳",),
    },
    "jinyu": {
        "甲": ("辰",),
        "乙": ("巳",),
        "丙": ("未",),
        "丁": ("申",),
        "戊": ("未",),
        "己": ("申",),
        "庚": ("戌",),
        "辛": ("亥",),
        "壬": ("丑",),
        "癸": ("寅",),
    },
    "hongyan": {
        "甲": ("午",),
        "乙": ("申",),
        "丙": ("寅",),
        "丁": ("未",),
        "戊": ("辰",),
        "己": ("辰",),
        "庚": ("戌",),
        "辛": ("酉",),
        "壬": ("子",),
        "癸": ("申",),
    },
    "liuxia": {
        "甲": ("酉",),
        "乙": ("戌",),
        "丙": ("未",),
        "丁": ("申",),
        "戊": ("巳",),
        "己": ("午",),
        "庚": ("辰",),
        "辛": ("卯",),
        "壬": ("亥",),
        "癸": ("寅",),
    },
    "jielukongwang": {
        "甲": ("申", "酉"),
        "己": ("申", "酉"),
        "乙": ("午", "未"),
        "庚": ("午", "未"),
        "丙": ("辰", "巳"),
        "辛": ("辰", "巳"),
        "丁": ("寅", "卯"),
        "壬": ("寅", "卯"),
        "戊": ("戌", "亥"),
        "癸": ("戌", "亥"),
    },
    "anlu": {
        "甲": ("亥",),
        "乙": ("戌",),
        "丙": ("申",),
        "丁": ("未",),
        "戊": ("申",),
        "己": ("未",),
        "庚": ("巳",),
        "辛": ("辰",),
        "壬": ("寅",),
        "癸": ("丑",),
    },
    "tianguan": {
        "甲": ("未",),
        "乙": ("辰",),
        "丙": ("巳",),
        "丁": ("寅",),
        "戊": ("卯",),
        "己": ("丑",),
        "庚": ("亥",),
        "辛": ("酉",),
        "壬": ("戌",),
        "癸": ("午",),
    },
    "tianfu": {
        "甲": ("酉",),
        "乙": ("申",),
        "丙": ("子",),
        "丁": ("亥",),
        "戊": ("卯",),
        "己": ("寅",),
        "庚": ("午",),
        "辛": ("巳",),
        "壬": ("辰",),
        "癸": ("丑",),
    },
    "tianchu": {
        "甲": ("巳",),
        "乙": ("午",),
        "丙": ("子",),
        "丁": ("巳",),
        "戊": ("午",),
        "己": ("申",),
        "庚": ("寅",),
        "辛": ("午",),
        "壬": ("酉",),
        "癸": ("亥",),
    },
}


# ── Group B: anchor=day_branch (or year_branch), target=branch (triad-based) ──

# Triad-based: anchor branch determines triad, target is one branch in chart
DAY_BRANCH_TO_BRANCH: dict[str, dict[str, tuple[str, ...]]] = {
    "taohua": {
        "申": ("酉",),
        "子": ("酉",),
        "辰": ("酉",),
        "亥": ("子",),
        "卯": ("子",),
        "未": ("子",),
        "寅": ("卯",),
        "午": ("卯",),
        "戌": ("卯",),
        "巳": ("午",),
        "酉": ("午",),
        "丑": ("午",),
    },
    "yima": {
        "申": ("寅",),
        "子": ("寅",),
        "辰": ("寅",),
        "亥": ("巳",),
        "卯": ("巳",),
        "未": ("巳",),
        "寅": ("申",),
        "午": ("申",),
        "戌": ("申",),
        "巳": ("亥",),
        "酉": ("亥",),
        "丑": ("亥",),
    },
    "huagai": {
        "申": ("辰",),
        "子": ("辰",),
        "辰": ("辰",),
        "亥": ("未",),
        "卯": ("未",),
        "未": ("未",),
        "寅": ("戌",),
        "午": ("戌",),
        "戌": ("戌",),
        "巳": ("丑",),
        "酉": ("丑",),
        "丑": ("丑",),
    },
    "jiangxing": {
        "申": ("子",),
        "子": ("子",),
        "辰": ("子",),
        "亥": ("卯",),
        "卯": ("卯",),
        "未": ("卯",),
        "寅": ("午",),
        "午": ("午",),
        "戌": ("午",),
        "巳": ("酉",),
        "酉": ("酉",),
        "丑": ("酉",),
    },
    "jiesha": {
        "申": ("巳",),
        "子": ("巳",),
        "辰": ("巳",),
        "亥": ("申",),
        "卯": ("申",),
        "未": ("申",),
        "寅": ("亥",),
        "午": ("亥",),
        "戌": ("亥",),
        "巳": ("寅",),
        "酉": ("寅",),
        "丑": ("寅",),
    },
    "zaisha": {
        "申": ("午",),
        "子": ("午",),
        "辰": ("午",),
        "亥": ("酉",),
        "卯": ("酉",),
        "未": ("酉",),
        "寅": ("子",),
        "午": ("子",),
        "戌": ("子",),
        "巳": ("卯",),
        "酉": ("卯",),
        "丑": ("卯",),
    },
    "tiansha": {
        "申": ("未",),
        "子": ("未",),
        "辰": ("未",),
        "亥": ("戌",),
        "卯": ("戌",),
        "未": ("戌",),
        "寅": ("丑",),
        "午": ("丑",),
        "戌": ("丑",),
        "巳": ("辰",),
        "酉": ("辰",),
        "丑": ("辰",),
    },
    "wangshen": {
        "申": ("亥",),
        "子": ("亥",),
        "辰": ("亥",),
        "亥": ("寅",),
        "卯": ("寅",),
        "未": ("寅",),
        "寅": ("巳",),
        "午": ("巳",),
        "戌": ("巳",),
        "巳": ("申",),
        "酉": ("申",),
        "丑": ("申",),
    },
    "liue": {
        "申": ("卯",),
        "子": ("卯",),
        "辰": ("卯",),
        "亥": ("午",),
        "卯": ("午",),
        "未": ("午",),
        "寅": ("酉",),
        "午": ("酉",),
        "戌": ("酉",),
        "巳": ("子",),
        "酉": ("子",),
        "丑": ("子",),
    },
    "panan": {
        "申": ("丑",),
        "子": ("丑",),
        "辰": ("丑",),
        "亥": ("辰",),
        "卯": ("辰",),
        "未": ("辰",),
        "寅": ("未",),
        "午": ("未",),
        "戌": ("未",),
        "巳": ("戌",),
        "酉": ("戌",),
        "丑": ("戌",),
    },
}

# Same triad table reused with year_branch anchor for 岁驿 (suiyi).
YEAR_BRANCH_TO_BRANCH_TRIAD: dict[str, dict[str, tuple[str, ...]]] = {
    "suiyi": DAY_BRANCH_TO_BRANCH["yima"],
}


# ── Group C: anchor=month_branch, target=branch ──

MONTH_BRANCH_TO_BRANCH: dict[str, dict[str, tuple[str, ...]]] = {
    "yuesha": {
        "寅": ("丑",),
        "午": ("丑",),
        "戌": ("丑",),
        "申": ("未",),
        "子": ("未",),
        "辰": ("未",),
        "亥": ("戌",),
        "卯": ("戌",),
        "未": ("戌",),
        "巳": ("辰",),
        "酉": ("辰",),
        "丑": ("辰",),
    },
    "tongzisha": {
        "寅": ("巳", "午"),
        "卯": ("巳", "午"),
        "辰": ("巳", "午"),
        "巳": ("丑", "未"),
        "午": ("丑", "未"),
        "未": ("丑", "未"),
        "申": ("寅", "子"),
        "酉": ("寅", "子"),
        "戌": ("寅", "子"),
        "亥": ("卯", "辰"),
        "子": ("卯", "辰"),
        "丑": ("卯", "辰"),
    },
    "xueren": {
        "寅": ("丑",),
        "卯": ("未",),
        "辰": ("寅",),
        "巳": ("申",),
        "午": ("卯",),
        "未": ("酉",),
        "申": ("辰",),
        "酉": ("戌",),
        "戌": ("巳",),
        "亥": ("午",),
        "子": ("亥",),
        "丑": ("子",),
    },
    "tianyi_doctor": {
        "寅": ("丑",),
        "卯": ("寅",),
        "辰": ("卯",),
        "巳": ("辰",),
        "午": ("巳",),
        "未": ("午",),
        "申": ("未",),
        "酉": ("申",),
        "戌": ("酉",),
        "亥": ("戌",),
        "子": ("亥",),
        "丑": ("子",),
    },
    "jieshen": {
        "寅": ("申",),
        "卯": ("申",),
        "辰": ("戌",),
        "巳": ("戌",),
        "午": ("子",),
        "未": ("子",),
        "申": ("寅",),
        "酉": ("寅",),
        "戌": ("辰",),
        "亥": ("辰",),
        "子": ("午",),
        "丑": ("午",),
    },
}


# ── Group D: anchor=month_branch, target=stem ──

MONTH_BRANCH_TO_STEM: dict[str, dict[str, tuple[str, ...]]] = {
    "tiande": {
        "寅": ("丁",),
        "卯": ("申",),
        "辰": ("壬",),
        "巳": ("辛",),
        "午": ("亥",),
        "未": ("甲",),
        "申": ("癸",),
        "酉": ("寅",),
        "戌": ("丙",),
        "亥": ("乙",),
        "子": ("巳",),
        "丑": ("庚",),
    },
    "yuede": {
        "寅": ("丙",),
        "午": ("丙",),
        "戌": ("丙",),
        "申": ("壬",),
        "子": ("壬",),
        "辰": ("壬",),
        "亥": ("甲",),
        "卯": ("甲",),
        "未": ("甲",),
        "巳": ("庚",),
        "酉": ("庚",),
        "丑": ("庚",),
    },
    "tiande_he": {
        "寅": ("壬",),
        "卯": ("巳",),
        "辰": ("丁",),
        "巳": ("丙",),
        "午": ("寅",),
        "未": ("己",),
        "申": ("戊",),
        "酉": ("亥",),
        "戌": ("辛",),
        "亥": ("庚",),
        "子": ("申",),
        "丑": ("乙",),
    },
    "yuede_he": {
        "寅": ("辛",),
        "午": ("辛",),
        "戌": ("辛",),
        "申": ("丁",),
        "子": ("丁",),
        "辰": ("丁",),
        "亥": ("己",),
        "卯": ("己",),
        "未": ("己",),
        "巳": ("乙",),
        "酉": ("乙",),
        "丑": ("乙",),
    },
}


# Note: 天德 / 天德合 search for either stem OR branch in chart (mixed targets).
# Tables above store the canonical "stem" form; branch-form 天德 entries
# (卯→申, 午→亥, 酉→寅, 子→巳) are flagged here so the detector can also look
# in branches when the table value happens to be a branch character.
TIANDE_BRANCH_FORM_MONTHS: frozenset[str] = frozenset({"卯", "午", "酉", "子"})


# ── Group E: anchor=year_branch, target=branch ──

YEAR_BRANCH_TO_BRANCH: dict[str, dict[str, tuple[str, ...]]] = {
    "guchen": {
        "亥": ("寅",),
        "子": ("寅",),
        "丑": ("寅",),
        "寅": ("巳",),
        "卯": ("巳",),
        "辰": ("巳",),
        "巳": ("申",),
        "午": ("申",),
        "未": ("申",),
        "申": ("亥",),
        "酉": ("亥",),
        "戌": ("亥",),
    },
    "guasu": {
        "亥": ("戌",),
        "子": ("戌",),
        "丑": ("戌",),
        "寅": ("丑",),
        "卯": ("丑",),
        "辰": ("丑",),
        "巳": ("辰",),
        "午": ("辰",),
        "未": ("辰",),
        "申": ("未",),
        "酉": ("未",),
        "戌": ("未",),
    },
    "dahao": {
        "子": ("午",),
        "丑": ("未",),
        "寅": ("申",),
        "卯": ("酉",),
        "辰": ("戌",),
        "巳": ("亥",),
        "午": ("子",),
        "未": ("丑",),
        "申": ("寅",),
        "酉": ("卯",),
        "戌": ("辰",),
        "亥": ("巳",),
    },
    "xiaohao": {
        "子": ("巳",),
        "丑": ("午",),
        "寅": ("未",),
        "卯": ("申",),
        "辰": ("酉",),
        "巳": ("戌",),
        "午": ("亥",),
        "未": ("子",),
        "申": ("丑",),
        "酉": ("寅",),
        "戌": ("卯",),
        "亥": ("辰",),
    },
    "feifu": {
        "子": ("巳",),
        "丑": ("午",),
        "寅": ("未",),
        "卯": ("申",),
        "辰": ("酉",),
        "巳": ("戌",),
        "午": ("亥",),
        "未": ("子",),
        "申": ("丑",),
        "酉": ("寅",),
        "戌": ("卯",),
        "亥": ("辰",),
    },
    "pima": {
        "子": ("辰",),
        "丑": ("巳",),
        "寅": ("午",),
        "卯": ("未",),
        "辰": ("申",),
        "巳": ("酉",),
        "午": ("戌",),
        "未": ("亥",),
        "申": ("子",),
        "酉": ("丑",),
        "戌": ("寅",),
        "亥": ("卯",),
    },
    "sangmen": {
        "子": ("寅",),
        "丑": ("卯",),
        "寅": ("辰",),
        "卯": ("巳",),
        "辰": ("午",),
        "巳": ("未",),
        "午": ("申",),
        "未": ("酉",),
        "申": ("戌",),
        "酉": ("亥",),
        "戌": ("子",),
        "亥": ("丑",),
    },
    "diaoke": {
        "子": ("戌",),
        "丑": ("亥",),
        "寅": ("子",),
        "卯": ("丑",),
        "辰": ("寅",),
        "巳": ("卯",),
        "午": ("辰",),
        "未": ("巳",),
        "申": ("午",),
        "酉": ("未",),
        "戌": ("申",),
        "亥": ("酉",),
    },
    "baihu": {
        "子": ("申",),
        "丑": ("酉",),
        "寅": ("戌",),
        "卯": ("亥",),
        "辰": ("子",),
        "巳": ("丑",),
        "午": ("寅",),
        "未": ("卯",),
        "申": ("辰",),
        "酉": ("巳",),
        "戌": ("午",),
        "亥": ("未",),
    },
    "tianxi": {
        "子": ("酉",),
        "丑": ("申",),
        "寅": ("未",),
        "卯": ("午",),
        "辰": ("巳",),
        "巳": ("辰",),
        "午": ("卯",),
        "未": ("寅",),
        "申": ("丑",),
        "酉": ("子",),
        "戌": ("亥",),
        "亥": ("戌",),
    },
    "hongluan": {
        "子": ("卯",),
        "丑": ("寅",),
        "寅": ("丑",),
        "卯": ("子",),
        "辰": ("亥",),
        "巳": ("戌",),
        "午": ("酉",),
        "未": ("申",),
        "申": ("未",),
        "酉": ("午",),
        "戌": ("巳",),
        "亥": ("辰",),
    },
}


# ── Group F: self-pillars (the day-pillar string itself IS the star) ──

SELF_PILLAR_STARS: dict[str, tuple[str, ...]] = {
    "kuigang": ("庚辰", "庚戌", "壬辰", "戊戌"),
    "yinchayangcuo": (
        "丙子",
        "丁丑",
        "戊寅",
        "辛卯",
        "壬辰",
        "癸巳",
        "丙午",
        "丁未",
        "戊申",
        "辛酉",
        "壬戌",
        "癸亥",
    ),
    "shiedabai": (
        "甲辰",
        "乙巳",
        "丙申",
        "丁亥",
        "戊戌",
        "己丑",
        "庚辰",
        "辛巳",
        "壬申",
        "癸亥",
    ),
    "guluan": ("乙巳", "丁巳", "辛亥", "戊申", "甲寅", "戊午", "壬子", "丙午"),
    "jinshen_advance": ("甲子", "甲午", "己卯", "己酉"),
    "tuishen": ("丁丑", "丁未", "壬辰", "壬戌"),
    "jinshen_gold": ("乙丑", "己巳", "癸酉"),
    "ride": ("甲寅", "丙辰", "戊辰", "庚辰", "壬戌"),
    "rigui": ("丁酉", "丁亥", "癸巳", "癸卯"),
}


# ── Group G: special handlers ──

# 天罗地网 — pair of branches must coexist anywhere in chart
TIANLUODIWANG_PAIRS: tuple[frozenset[str], ...] = (
    frozenset({"戌", "亥"}),
    frozenset({"辰", "巳"}),
)

# 天赦 — by season of month branch, look for specific day_pillar
SEASON_OF_MONTH: dict[str, str] = {
    "寅": "spring",
    "卯": "spring",
    "辰": "spring",
    "巳": "summer",
    "午": "summer",
    "未": "summer",
    "申": "autumn",
    "酉": "autumn",
    "戌": "autumn",
    "亥": "winter",
    "子": "winter",
    "丑": "winter",
}
TIANSHE_BY_SEASON: dict[str, str] = {
    "spring": "戊寅",
    "summer": "甲午",
    "autumn": "戊申",
    "winter": "甲子",
}
