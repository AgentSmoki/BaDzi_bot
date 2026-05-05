#!/usr/bin/env python3
"""One-off research script for Bazi 格局 (special structures).

Differences from generic Dev_Architect/research_tool:
  - Bazi-specific system prompt (canonical sources, no Python-code mandate).
  - Extended deep timeout (300s) and detailed exception logging.
  - Saves output to doc/research/structures_v2_perplexity_deep.md.

Usage:
    python3 scripts/research_bazi_structures.py
"""

from __future__ import annotations

import asyncio
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import cast

import httpx

# Load API key from sibling research_tool .env (single source of truth).
RESEARCH_TOOL_ENV = Path("/Users/admin/Documents/Razarabotka/Dev_Architect/research_tool/.env")
OPENROUTER_API_KEY = ""
if RESEARCH_TOOL_ENV.exists():
    for line in RESEARCH_TOOL_ENV.read_text().splitlines():
        if line.startswith("OPENROUTER_API_KEY="):
            OPENROUTER_API_KEY = line.split("=", 1)[1].strip()
            break

OUTPUT_PATH = Path(
    "/Users/admin/Documents/Razarabotka/BaDzi_bot/doc/research/structures_v2_perplexity_deep.md"
)
MODEL = "perplexity/sonar-deep-research"
TIMEOUT_SECONDS = 600.0  # Generous: deep research can take 5+ minutes.

SYSTEM_PROMPT = """
Ты — эксперт-исследователь классической китайской метафизики Бацзы (八字 / 子平命理).
Свободно владеешь каноническими текстами:
  - 三命通会 (Sān Mìng Tōng Huì), Wan Min-ying, Ming dynasty
  - 渊海子平 (Yuān Hǎi Zǐ Píng), Xu Sheng, Song dynasty
  - 神峰通考 (Shén Fēng Tōng Kǎo), Zhang Shen-feng
  - 子平真詮 (Zǐ Píng Zhēn Quán), Shen Xiao-zhan
  - 协纪辨方书 (Xié Jì Biàn Fāng Shū), Qing imperial almanac
  - 滴天髓 (Dī Tiān Suǐ), Liu Bowen / Ren Tiequan commentaries
  - 命理探源 (Mìng Lǐ Tàn Yuán), Yuan Shu-shan
И современными мастерами: 梁湘潤 (Liang Xiangrun), 鍾義明 (Zhong Yiming),
王亭之 (Wang Tingzhi), 何建忠 (He Jianzhong).

ЗАДАЧА: Составить детерминированный машинный справочник правил для Python-калькулятора.
Каждое правило — это арифметика над уже вычисленными полями карты:
  - day_master (1 ствол)
  - 4 stems / 4 branches
  - hidden_stems_of_each_branch (3 школы)
  - ten_gods (отображение всех стволов карты в 10 Богов от ДМ)
  - element_balance (% каждого из 5 элементов 木火土金水)
  - 60-cycle position of day pillar

ЖЁСТКИЕ ПРАВИЛА ОТВЕТА:
1. НЕ давать Python-код в ответе. Только правила, таблицы, формулы.
2. НЕ ссылаться на несуществующие/малоизвестные PyPI библиотеки.
3. НЕ использовать формулировки "опыт мастера решит", "субъективно".
   Если правило фундаментально требует суждения — явно отметь это
   в "уровень детерминированности: low" и пометь структуру как deferred.
4. Источники: обязательно цитировать конкретный канон (название иероглифами +
   глава если возможно). Modern western источники (cantian.ai, deeporacle.ai,
   Wikipedia) — только secondary, и только если совпадают с каноном.

ФОРМАТ ОТВЕТА:
1. Сводная CSV-таблица всех структур с колонками:
   id, name_zh, name_pinyin, name_ru, category, priority_check_order,
   detect_rule (текст-формула), break_rule, useful_god, harmful_god,
   determinism_level (high/medium/low), source_book, confidence (canonical/common/rare).

2. Развёрнутые карточки на каждую структуру с пошаговой формулой детекции
   (каждый шаг — арифметическое условие с конкретными иероглифами/индексами).
""".strip()

USER_PROMPT = """
Составь полный детерминированный справочник 格局 (Special Structures) системы Бацзы для
Python-калькулятора. Минимальный объём: 25-40 структур. Покрой эти группы:

# 1. 正格 (8 регулярных структур)
正官格, 七杀格, 正财格, 偏财格, 正印格, 偏印格, 食神格, 伤官格.
Для каждой:
  - Какой скрытый ствол 月支 (по приоритету 主气 / 中气 / 余气) даёт структуру.
  - Точная таблица: для каждого из 12 ветвей-месяцев и каждого из 10 Дневных Мастеров —
    какая структура получается через 主气 (если 主气 не透出, то fallback на 中气, потом 余气).
  - Условие 透出 (transparency): главный ствол должен быть в 年干/月干/时干.
  - 破格 — что ломает структуру (например, для 正官格 сильное 比劫 без 财).
  - 用神/忌神.

# 2. 月令 особые структуры
建禄格 — 月支 = 临官 ДМ. Точная таблица: 甲→寅, 乙→卯, 丙/戊→巳, 丁/己→午,
  庚→申, 辛→酉, 壬→亥, 癸→子.
月刃格 (羊刃在月支) — 月支 = 帝旺 ДМ, только Ян-стволы:
  甲→卯, 丙→午, 戊→午, 庚→酉, 壬→子.
Условия破格 для каждой.

# 3. 一气格 (5 моно-элементных)
曲直 (Wood, ДМ 甲/乙), 炎上 (Fire, ДМ 丙/丁), 稼穑 (Earth, ДМ 戊/己),
从革 (Metal, ДМ 庚/辛), 润下 (Water, ДМ 壬/癸).
Для каждой: точные условия чистоты (например: «3 из 4 ветвей в 三合 木局
亥卯未 ИЛИ 方局 寅卯辰», «не более 1 ветви противоположного элемента»,
«ствол времени не должен иметь корня 七杀»).

# 4. 化格 (5 трансформаций) — БУДЬ ТОЧЕН с 五合
КЛАССИЧЕСКАЯ ТАБЛИЦА 五合 (это известные канонические значения, проверь):
  甲己 → 土
  乙庚 → 金
  丙辛 → 水
  丁壬 → 木
  戊癸 → 火
Для каждой 化格 (化木/化火/化土/化金/化水):
  - Какие два соседних столпа должны иметь нужную пару стволов.
  - Какой сезон (月支) поддерживает трансформацию.
  - Что её破格 (например, появление контролирующего элемента).
  - 真化 vs 假化 — отличия.

# 5. 从格 (5 структур следования)
从财, 从官杀, 从儿 (食伤), 从势 (комбо财官食), 从强/旺.
Для каждой:
  - Точный порог слабости/силы ДМ через element_balance ДМ-элемента
    или через формулу «у ДМ нет корня + не более 1 поддержки».
  - Какие 10 Богов должны доминировать.
  - Запрещённые элементы.
  - 用神/忌神.

# 6. Эзотерические (упомяни обязательно, опиши кратко 5-10 шт)
拱禄 (Embracing Lu), 飞天禄马 (Flying Lu Ma), 倒冲 (Reverse Clash),
邀禄 (Inviting Lu), 两神成象 (Two-God Image), 子辰双美格,
夹拱 (Sandwich), 井栏叉, 壬骑龙背, 六阴朝阳.

# Приоритет проверки структур (важно для алгоритма)
Опиши каноническую последовательность:
  1) Особые редкие (魁罡 уже детектируется как Шэнь Ша; 飞天 etc.)
  2) 化格
  3) 从格
  4) 一气格
  5) 月令-special (建禄/月刃)
  6) 正格 (8 главных)

# Приоритет 正格 при множественных透出
Если в 月支 透出 одновременно 2-3 скрытых ствола — какой выигрывает?
Каноническая иерархия: 主气 > 中气 > 余气. И что если 余气 透出, а 主气 нет —
структура от 余气 действительна или нет?

# Дай также CSV-таблицу 月支 → (主气, 中气, 余气) для всех 12 ветвей,
строго по канону 三命通会 (это известная классическая таблица).

ПОВТОРЯЮ: НЕ давай Python код. Только данные. Карточки + CSV-таблица.
""".strip()


async def call_perplexity_deep() -> str:
    """Single deep-research call with detailed error logging."""
    if not OPENROUTER_API_KEY:
        return "ERROR: OPENROUTER_API_KEY not loaded from .env"

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "HTTP-Referer": "https://badzi-bot.local",
                    "X-Title": "BaDzi Structures Research",
                },
                json={
                    "model": MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": USER_PROMPT},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 16384,
                },
            )

        if resp.status_code != 200:
            return (
                f"ERROR: HTTP {resp.status_code}\n"
                f"Response body:\n{resp.text[:2000]}\n"
                f"Headers: {dict(resp.headers)}"
            )

        data = resp.json()
        if "choices" not in data or not data["choices"]:
            return f"ERROR: missing 'choices' in response\nFull response:\n{data}"

        msg = data["choices"][0].get("message", {})
        content = msg.get("content", "")
        if not content:
            return (
                f"ERROR: empty content\nFull message:\n{msg}\nFull data keys: {list(data.keys())}"
            )

        # Annotations / citations
        sources_md = ""
        annotations = msg.get("annotations", [])
        if annotations:
            urls = [
                a.get("url_citation", {}) for a in annotations if a.get("type") == "url_citation"
            ]
            lines = [
                f"- [{u.get('title', u.get('url', ''))}]({u.get('url', '')})"
                for u in urls
                if u.get("url")
            ]
            if lines:
                sources_md = "\n\n## Источники (live citations)\n" + "\n".join(lines)

        usage = data.get("usage", {})
        meta = (
            f"\n\n---\n\n"
            f"**Model:** {MODEL}\n"
            f"**Tokens:** in={usage.get('prompt_tokens', '?')}, "
            f"out={usage.get('completion_tokens', '?')}, "
            f"total={usage.get('total_tokens', '?')}\n"
        )
        return cast(str, content) + sources_md + meta

    except httpx.ReadTimeout:
        return f"ERROR: ReadTimeout after {TIMEOUT_SECONDS}s. Deep research did not complete."
    except httpx.HTTPError as exc:
        return f"ERROR: httpx {type(exc).__name__}: {exc}\n{traceback.format_exc()}"
    except Exception as exc:
        return f"ERROR: {type(exc).__name__}: {exc}\n{traceback.format_exc()}"


async def main() -> int:
    started = datetime.now()
    print(f"Started: {started:%Y-%m-%d %H:%M:%S}", file=sys.stderr)
    print(f"Model: {MODEL}, timeout: {TIMEOUT_SECONDS}s", file=sys.stderr)

    body = await call_perplexity_deep()
    finished = datetime.now()
    duration = (finished - started).total_seconds()

    header = (
        f"# Bazi 格局 Research v2 — Perplexity sonar-deep-research\n\n"
        f"**Started:** {started:%Y-%m-%d %H:%M:%S}  \n"
        f"**Finished:** {finished:%Y-%m-%d %H:%M:%S}  \n"
        f"**Duration:** {duration:.1f}s  \n"
        f"**Model:** {MODEL}\n\n"
        f"---\n\n"
    )
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(header + body, encoding="utf-8")

    print(
        f"Finished in {duration:.1f}s. Output: {OUTPUT_PATH} ({OUTPUT_PATH.stat().st_size} bytes)",
        file=sys.stderr,
    )
    return 0 if not body.startswith("ERROR") else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
