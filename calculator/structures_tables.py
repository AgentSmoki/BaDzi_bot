"""Reference tables for Bazi 格局 (Special Structures) detection.

Sourced from doc/research/structures_v2_perplexity_deep.md (Perplexity sonar-deep-research,
verified against 三命通会, 渊海子平, 神峰通考, 子平真詮 canonical hidden-stem and
five-element tables).
"""

from __future__ import annotations

from dataclasses import dataclass

# ── Structure metadata ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class StructureMeta:
    name_zh: str
    name_pinyin: str
    name_ru: str
    category: str
    useful_god: str
    harmful_god: str
    determinism: str
    source: str


META: dict[str, StructureMeta] = {
    # 8 正格 (Regular)
    "zheng_guan": StructureMeta(
        "正官格",
        "zheng guan ge",
        "Прямой Чиновник",
        "regular",
        "Чиновник + Богатство",
        "Едящий Бог + Раня Чиновника",
        "high",
        "三命通会",
    ),
    "qi_sha": StructureMeta(
        "七杀格",
        "qi sha ge",
        "Семь Убийств",
        "regular",
        "7-Убийств + Богатство",
        "Едящий Бог + Раня Чиновника",
        "high",
        "三命通会",
    ),
    "zheng_cai": StructureMeta(
        "正财格",
        "zheng cai ge",
        "Прямое Богатство",
        "regular",
        "Богатство + Едящий Бог",
        "Печать + Грабёж",
        "high",
        "渊海子平",
    ),
    "pian_cai": StructureMeta(
        "偏财格",
        "pian cai ge",
        "Косвенное Богатство",
        "regular",
        "Богатство + Раня Чиновника",
        "Печать + Грабёж",
        "high",
        "渊海子平",
    ),
    "zheng_yin": StructureMeta(
        "正印格",
        "zheng yin ge",
        "Прямая Печать",
        "regular",
        "Печать + Друг",
        "Богатство (贪财坏印)",
        "high",
        "神峰通考",
    ),
    "pian_yin": StructureMeta(
        "偏印格",
        "pian yin ge",
        "Косвенная Печать",
        "regular",
        "Печать + Грабёж",
        "Едящий Бог (枭神夺食)",
        "high",
        "三命通会",
    ),
    "shi_shen": StructureMeta(
        "食神格",
        "shi shen ge",
        "Едящий Бог",
        "regular",
        "Едящий Бог + Богатство",
        "Прямой Чиновник + Косв. Печать",
        "high",
        "子平真詮",
    ),
    "shang_guan": StructureMeta(
        "伤官格",
        "shang guan ge",
        "Раня Чиновника",
        "regular",
        "Едящий Бог или Печать",
        "Прямой Чиновник",
        "high",
        "子平真詮",
    ),
    # 月令 special
    "jian_lu": StructureMeta(
        "建禄格",
        "jian lu ge",
        "Установленное Жалование",
        "month_special",
        "Едящий Бог + Богатство + Чиновник",
        "Косвенная Печать",
        "high",
        "子平真詮",
    ),
    "yue_ren": StructureMeta(
        "月刃格",
        "yue ren ge",
        "Месячный Клинок",
        "month_special",
        "Едящий Бог + Чиновник + Богатство",
        "Косв. Печать + Грабёж",
        "high",
        "三命通会",
    ),
    # 一气格 (Mono-element)
    "qu_zhi": StructureMeta(
        "曲直格",
        "qu zhi ge",
        "Прямота-Гибкость (Дерево)",
        "monoelement",
        "Дерево + Огонь",
        "Металл + Земля",
        "medium",
        "三命通会",
    ),
    "yan_shang": StructureMeta(
        "炎上格",
        "yan shang ge",
        "Пылающее Восхождение (Огонь)",
        "monoelement",
        "Огонь + Земля",
        "Вода + Металл",
        "medium",
        "三命通会",
    ),
    "jia_se": StructureMeta(
        "稼穑格",
        "jia se ge",
        "Посев и Жатва (Земля)",
        "monoelement",
        "Земля + Огонь",
        "Дерево",
        "medium",
        "三命通会",
    ),
    "cong_ge_metal": StructureMeta(
        "从革格",
        "cong ge ge",
        "Следование Изменениям (Металл)",
        "monoelement",
        "Металл + Вода",
        "Огонь + Дерево",
        "medium",
        "三命通会",
    ),
    "run_xia": StructureMeta(
        "润下格",
        "run xia ge",
        "Текущая Вода",
        "monoelement",
        "Вода + Металл + Огонь",
        "Земля + Дерево",
        "medium",
        "三命通会",
    ),
    # 化气格 (Transformation)
    "hua_tu": StructureMeta(
        "化土格",
        "hua tu ge",
        "Трансформация в Землю (甲己)",
        "transformation",
        "Боги Земли",
        "Боги Дерева",
        "low",
        "三命通会",
    ),
    "hua_jin": StructureMeta(
        "化金格",
        "hua jin ge",
        "Трансформация в Металл (乙庚)",
        "transformation",
        "Боги Металла",
        "Боги Дерева",
        "low",
        "三命通会",
    ),
    "hua_shui": StructureMeta(
        "化水格",
        "hua shui ge",
        "Трансформация в Воду (丙辛)",
        "transformation",
        "Боги Воды",
        "Боги Огня",
        "low",
        "三命通会",
    ),
    "hua_mu": StructureMeta(
        "化木格",
        "hua mu ge",
        "Трансформация в Дерево (丁壬)",
        "transformation",
        "Боги Дерева",
        "Боги Огня",
        "low",
        "三命通会",
    ),
    "hua_huo": StructureMeta(
        "化火格",
        "hua huo ge",
        "Трансформация в Огонь (戊癸)",
        "transformation",
        "Боги Огня",
        "Боги Воды",
        "low",
        "三命通会",
    ),
    # 从格 (Following)
    "cong_cai": StructureMeta(
        "从财格",
        "cong cai ge",
        "Следование за Богатством",
        "following",
        "Богатство + Едящий/Раня",
        "Печать + Грабёж",
        "medium",
        "渊海子平",
    ),
    "cong_guan_sha": StructureMeta(
        "从官杀格",
        "cong guan sha ge",
        "Следование за Чиновником/7-Убийств",
        "following",
        "Чиновник + Богатство",
        "Едящий/Раня + Печать",
        "medium",
        "渊海子平",
    ),
    "cong_er": StructureMeta(
        "从儿格",
        "cong er ge",
        "Следование за Детьми (Выходом)",
        "following",
        "Едящий/Раня + Богатство",
        "Печать + Чиновник",
        "medium",
        "渊海子平",
    ),
    "cong_shi": StructureMeta(
        "从势格",
        "cong shi ge",
        "Следование за Импульсом",
        "following",
        "Доминантная конфигурация",
        "Противоположный элемент",
        "medium",
        "渊海子平",
    ),
    "cong_qiang": StructureMeta(
        "从强格",
        "cong qiang ge",
        "Следование за Силой",
        "following",
        "Тот же элемент + Выход",
        "Контролирующий элемент",
        "low",
        "渊海子平",
    ),
}


# ── Element / stem / branch maps ──────────────────────────────────────────────

STEM_ELEMENT: dict[str, str] = {
    "甲": "木",
    "乙": "木",
    "丙": "火",
    "丁": "火",
    "戊": "土",
    "己": "土",
    "庚": "金",
    "辛": "金",
    "壬": "水",
    "癸": "水",
}

STEM_POLARITY: dict[str, str] = {  # Yang/Yin
    "甲": "yang",
    "乙": "yin",
    "丙": "yang",
    "丁": "yin",
    "戊": "yang",
    "己": "yin",
    "庚": "yang",
    "辛": "yin",
    "壬": "yang",
    "癸": "yin",
}

# Dominant element of each branch (by main qi)
BRANCH_ELEMENT: dict[str, str] = {
    "子": "水",
    "丑": "土",
    "寅": "木",
    "卯": "木",
    "辰": "土",
    "巳": "火",
    "午": "火",
    "未": "土",
    "申": "金",
    "酉": "金",
    "戌": "土",
    "亥": "水",
}


# ── Hidden stems by month branch (canonical 三命通会 table, 主气 first) ─────

HIDDEN_STEMS: dict[str, tuple[str, ...]] = {
    "寅": ("甲", "丙", "戊"),  # 主, 中, 余
    "卯": ("乙",),
    "辰": ("戊", "乙", "癸"),
    "巳": ("丙", "戊", "庚"),
    "午": ("丁", "己"),
    "未": ("己", "丁", "乙"),
    "申": ("庚", "壬", "戊"),
    "酉": ("辛",),
    "戌": ("戊", "辛", "丁"),
    "亥": ("壬", "甲"),
    "子": ("癸",),
    "丑": ("己", "癸", "辛"),
}


# ── Lu (临官) and Yang Blade (帝旺) positions ────────────────────────────────

LU_POSITION: dict[str, str] = {
    "甲": "寅",
    "乙": "卯",
    "丙": "巳",
    "丁": "午",
    "戊": "巳",
    "己": "午",
    "庚": "申",
    "辛": "酉",
    "壬": "亥",
    "癸": "子",
}

# Only Yang stems form 月刃 (Blade) — Yin stems form 建禄 instead
YANG_BLADE_POSITION: dict[str, str] = {
    "甲": "卯",
    "丙": "午",
    "戊": "午",
    "庚": "酉",
    "壬": "子",
}


# ── 五合 stem combinations (canonical) ───────────────────────────────────────

STEM_COMBINATIONS: dict[frozenset[str], str] = {
    frozenset({"甲", "己"}): "土",
    frozenset({"乙", "庚"}): "金",
    frozenset({"丙", "辛"}): "水",
    frozenset({"丁", "壬"}): "木",
    frozenset({"戊", "癸"}): "火",
}

# Element id → structure id for 化格
TRANSFORMATION_STRUCTURE: dict[str, str] = {
    "土": "hua_tu",
    "金": "hua_jin",
    "水": "hua_shui",
    "木": "hua_mu",
    "火": "hua_huo",
}

# Months that support each transformation (where Main Qi element matches)
TRANSFORMATION_SUPPORT_MONTHS: dict[str, frozenset[str]] = {
    "木": frozenset({"寅", "卯"}),
    "火": frozenset({"巳", "午"}),
    "土": frozenset({"辰", "戌", "丑", "未"}),
    "金": frozenset({"申", "酉"}),
    "水": frozenset({"亥", "子"}),
}


# ── Mono-element triads / directionals ───────────────────────────────────────

MONO_TRIADS: dict[str, frozenset[str]] = {
    "木": frozenset({"亥", "卯", "未"}),
    "火": frozenset({"寅", "午", "戌"}),
    "金": frozenset({"巳", "酉", "丑"}),
    "水": frozenset({"申", "子", "辰"}),
}

MONO_DIRECTIONALS: dict[str, frozenset[str]] = {
    "木": frozenset({"寅", "卯", "辰"}),
    "火": frozenset({"巳", "午", "未"}),
    "金": frozenset({"申", "酉", "戌"}),
    "水": frozenset({"亥", "子", "丑"}),
}

EARTH_FOUR_STORAGE: frozenset[str] = frozenset({"辰", "戌", "丑", "未"})

# Element id → structure id for 一气格
MONOELEMENT_STRUCTURE: dict[str, str] = {
    "木": "qu_zhi",
    "火": "yan_shang",
    "土": "jia_se",
    "金": "cong_ge_metal",
    "水": "run_xia",
}


# ── 5-element interaction graph ──────────────────────────────────────────────

# E generates X (生): 木→火→土→金→水→木
ELEMENT_GENERATES: dict[str, str] = {
    "木": "火",
    "火": "土",
    "土": "金",
    "金": "水",
    "水": "木",
}

# E controls X (克): 木→土, 火→金, 土→水, 金→木, 水→火
ELEMENT_CONTROLS: dict[str, str] = {
    "木": "土",
    "火": "金",
    "土": "水",
    "金": "木",
    "水": "火",
}

# Which element controls E (E is controlled by) — 7-Killings/Officer source for DM
ELEMENT_CONTROLLED_BY: dict[str, str] = {
    "土": "木",
    "金": "火",
    "水": "土",
    "木": "金",
    "火": "水",
}

# Which element generates E (E is generated by) — Resource (印) source for DM
ELEMENT_GENERATED_BY: dict[str, str] = {v: k for k, v in ELEMENT_GENERATES.items()}
