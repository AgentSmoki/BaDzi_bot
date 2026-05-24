# База/edoha/ — Цифровая копия Мастера ЭдоХа

Содержимое этой папки — **derived view** на 7742 узла из KuzuDB проекта
[`/Users/admin/Documents/Razarabotka/EdoHa`](/Users/admin/Documents/Razarabotka/EdoHa) (Digital Twin Мастера, собранный
через 5-слойную LLM-обработку 298 YouTube-транскриптов + 4 PDF + 20
курсовых материалов).

## Структура

- `highlights/` — **524 .md файла** с квинтэссенцией (manifestos +
  quotes + top-facts) для git-видимости и ручного ревью. Это
  ~7% от полной базы; вся полная база живёт в KuzuDB `knowledge/kuzu_db/`
  с `school='edoha'`.

## Полный импорт vs highlights

| Шаг | Скрипт | Что | Куда |
|---|---|---|---|
| 1 | `scripts/edoha_export_json.py` | Читает EdoHa kuzu (v0.11) → JSONL | `/tmp/edoha_export/` |
| 2 | `scripts/import_edoha_kuzu.py` | JSONL → BaDzi kuzu (v0.10) — **все 7742 узла** | `knowledge/kuzu_db/` |
| 3 (опц.) | `scripts/export_edoha_to_md.py` | JSONL → .md highlights | `База/edoha/highlights/` |

Шаги 1 и 2 — обязательны (это и есть production import). Шаг 3 — только
для git/ревью, retrieval работает поверх KuzuDB напрямую.

## Регенерация

```bash
# Phase 1 (через EdoHa venv — kuzu 0.11.3)
/Users/admin/Documents/Razarabotka/EdoHa/.venv/bin/python \
    scripts/edoha_export_json.py

# Phase 2 (через BaDzi venv — kuzu 0.10)
.venv/bin/python scripts/import_edoha_kuzu.py
# → 7742 nodes, 7850 edges, ~7 минут на M-Series Mac

# Phase 3 опционально (любой venv)
.venv/bin/python scripts/export_edoha_to_md.py
# → 524 .md в highlights/
```

## Распределение по школам после импорта

| School | Count | Источник |
|---|---|---|
| classic | 14 | Anastasia v2 prompt chunks (методика Цзы Пин) |
| **edoha** | **7742** | **Digital Twin Мастера** |
| universal | 32 | L1-L4 базовая теория Ба Цзы |
| modern | 0 | (не добавлено пока) |

## Типы EdoHa узлов

| Тип | Count | Level | Authority | Покрытие в highlights/ |
|---|---|---|---|---|
| Manifesto | 212 | L8 | 10 | **все** (manifesto/) |
| Quote | 112 | L8 | 10 | **все** (quote/) |
| Fact | 788 | L8 | 9 | top-200 (fact/) |
| MentalModel | 808 | L7 | 9 | — (только в kuzu) |
| CausalBelief | 1595 | L7 | 8 | — (только в kuzu) |
| Document | 537 | L7 | 9 | — (только в kuzu, ~3000-токенные chunks) |
| Relation | 539 | L6 | 8 | — (только в kuzu) |
| StyleMarker | 3151 | L6 | 7 | — (только в kuzu) |

## ID convention

Все EdoHa узлы имеют префикс `edoha:<type>:<original_pk>` чтобы избегать
коллизий с classic/universal узлами:
- `edoha:manifesto:man_79e612e5124d`
- `edoha:fact:fact_27279778f30c`
- `edoha:doc:s259_..._ch001`

При желании удалить **все** EdoHa узлы из BaDzi kuzu:
```cypher
MATCH (n:Node) WHERE n.school = 'edoha' DETACH DELETE n
```
Это вернёт граф к pre-EdoHa состоянию (46 nodes / 617 edges). classic/
universal/concept-stub узлы не затрагиваются.
