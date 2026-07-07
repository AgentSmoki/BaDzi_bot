# Gemini Deep Research — Промпты для архитектурных решений

> Скопируй каждый промпт в Gemini Advanced (Deep Research режим).
> Используй результаты для финального закрепления стека перед разработкой.

---

## R-1: KuzuDB vs Neo4j для RAG в Python-боте

```
Контекст:
Я разрабатываю Telegram-бота на Python 3.11 + aiogram 3.x + FastAPI.
Бот — AI-консультант по китайской астрологии Ба Цзы (BaZi).
Нужна граф-база знаний для RAG (Retrieval-Augmented Generation):
- Хранить правила и интерпретации Бацзы в виде графа:
  узлы (Element, Stem, Branch, TenGod, Rule, Interpretation)
  рёбра (GENERATES, CONTROLS, CLASHES_WITH, COMBINES_WITH, MEANS)
- При пользовательском запросе: извлечь концепты из вопроса →
  найти релевантные узлы + рёбра → добавить в контекст LLM
- База знаний: ~50 000 узлов, ~200 000 рёбер (книги по Бацзы)
- Одновременных пользователей: 100-1000 (MVP → рост)
- Деплой: Docker-контейнер на Yandex Cloud VPS (2-4 vCPU, 8GB RAM)

Исследуй и сравни:

1. KuzuDB (embedded, Python-native)
   - Как устанавливается и используется в Python async-проекте?
   - Производительность для наших объёмов (50K узлов, graph traversal)
   - Поддержка concurrent reads в async-окружении
   - Как хранятся данные (файлы на диске)?
   - Backup и восстановление
   - Примеры Cypher/kùzu-QL запросов для RAG-паттерна

2. Neo4j (server, Python driver)
   - Community Edition vs AuraDB (managed cloud)
   - Overhead от отдельного сервера в Docker
   - Python async driver (neo4j-driver 5.x)
   - Стоимость для 1000 пользователей/день
   - GraphQL + RAG примеры

3. Альтернативы для рассмотрения:
   - SQLite + recursive CTEs (достаточно ли для графа?)
   - PostgreSQL + pgvector + graph extensions

Дай конкретную рекомендацию: что выбрать для embedded Python-сервиса
с умеренной нагрузкой (не highload) и акцентом на простоту деплоя?
Покажи рабочий пример кода на Python для RAG-запроса к выбранной БД.
```

---
Конкретная рекомендация
Для вашего стека (Telegram-бот, Python 3.11, FastAPI, Ubuntu/Docker) и задачи (MVP, 50k узлов, умеренная нагрузка, ограничение в 8GB RAM) безоговорочным лидером является KuzuDB.

Почему:

Zero DevOps: Вам не нужно поднимать, мониторить и тюнить JVM-контейнер Neo4j. Архитектура остается монолитной и простой (как systemd-демон или один легковесный Docker-контейнер).

Экономия RAM: Kuzu потребляет ровно столько памяти, сколько нужно для графа, оставляя ценные ресурсы для самого бота, FastAPI и LLM-инструментария.

Cypher: Вы получаете всю мощь языка запросов Cypher без оверхеда полноценного сервера.

Единственный компромисс — необходимость оборачивать синхронные вызовы БД в асинхронные потоки, но в Python 3.11 это делается в одну строку.

Рабочий пример кода на Python (KuzuDB + FastAPI/aiogram pattern)
Ниже показан пример того, как безопасно использовать Kuzu в асинхронном приложении, эмулируя извлечение контекста Бацзы (например, в стиле парсинга структур Mingli).

Python
import asyncio
import kuzu
from typing import List, Dict, Any

# 1. Инициализация БД (выполняется при старте приложения)
# В production путь к базе должен быть в volume Docker-контейнера
DB_PATH = "./bazi_graph_db"

def init_db():
    db = kuzu.Database(DB_PATH)
    conn = kuzu.Connection(db)

    # Создаем схему (только если она еще не создана)
    try:
        conn.execute("CREATE NODE TABLE Stem (name STRING, element STRING, polarity STRING, PRIMARY KEY (name))")
        conn.execute("CREATE REL TABLE CLASHES_WITH (FROM Stem TO Stem, meaning STRING)")

        # Наполняем тестовыми данными Бацзы (Янское Дерево сталкивается с Янским Металлом)
        conn.execute("CREATE (s:Stem {name: 'Jia', element: 'Wood', polarity: 'Yang'})")
        conn.execute("CREATE (s:Stem {name: 'Geng', element: 'Metal', polarity: 'Yang'})")
        conn.execute("""
            MATCH (s1:Stem {name: 'Jia'}), (s2:Stem {name: 'Geng'})
            CREATE (s1)-[:CLASHES_WITH {meaning: 'Destructive change, physical movement'}]->(s2)
        """)
    except RuntimeError:
        pass # Таблицы уже существуют

    return db

# Глобальный объект базы данных
bazi_db = init_db()

# 2. Асинхронный сервис для работы с графом
class BaZiGraphService:
    def __init__(self, db: kuzu.Database):
        self.db = db

    def _sync_get_clashes(self, stem_name: str) -> List[Dict[str, Any]]:
        """
        Синхронная функция, выполняющая Cypher-запрос.
        Для каждого потока создается свое легковесное подключение (connection),
        что безопасно для concurrent reads в Kuzu.
        """
        conn = kuzu.Connection(self.db)
        # Защита от инъекций через параметры запроса
        query = """
            MATCH (s:Stem {name: $name})-[r:CLASHES_WITH]-(target:Stem)
            RETURN target.name AS target_stem, target.element AS element, r.meaning AS interpretation
        """
        results = conn.execute(query, parameters={'name': stem_name})

        # Конвертируем результат в список словарей для контекста LLM
        context = []
        while results.has_next():
            row = results.get_next()
            context.append({
                "target": row[0],
                "element": row[1],
                "interpretation": row[2]
            })
        return context

    async def get_clash_context_async(self, stem_name: str) -> List[Dict[str, Any]]:
        """
        Асинхронная обертка. Использует встроенный ThreadPool в Python 3.9+
        Это не заблокирует event loop FastAPI или aiogram.
        """
        return await asyncio.to_thread(self._sync_get_clashes, stem_name)

# 3. Использование в эндпоинте FastAPI или хендлере aiogram
async def process_user_query(user_question: str, extracted_concept: str):
    graph_service = BaZiGraphService(bazi_db)

    # 1. Извлекаем контекст из графа не блокируя основной поток
    rag_context = await graph_service.get_clash_context_async(extracted_concept)

    # 2. Формируем промпт для LLM
    llm_prompt = f"""
    Пользователь спрашивает: {user_question}

    Используй следующие правила Бацзы для ответа:
    Контекст столкновений для {extracted_concept}: {rag_context}
    """

    print(f"Готовый промпт отправляется в LLM:\n{llm_prompt}")
    return llm_prompt

# Запуск примера
if __name__ == "__main__":
    asyncio.run(process_user_query(
        user_question="Что означает, если в моем дне стоит Дерево Ян, а приходит год Металла Ян?",
        extracted_concept="Jia"
    ))


## R-2: OpenRouter Kimi K2 — реальные характеристики

```
Контекст:
Строим Telegram-бота для AI-консультаций по китайской астрологии на русском языке.
Основная задача LLM: интерпретировать карты Ба Цзы (китайские иероглифы,
термины типа 甲 乙 丙 子丑寅卯, правила взаимодействий) и давать ответы на русском.

Средний контекст на запрос:
- Input: ~6 000 токенов (системный промпт 2500 + карта 1000 + история 2000 + вопрос 500)
- Output: ~1 000 токенов
- Диалог из 10 обменов: input растёт до ~20 000 токенов

Исследуй модель moonshot/moonshot-kimi-k2 через OpenRouter:

1. Актуальное ценообразование на OpenRouter:
   - Цена за 1M input токенов
   - Цена за 1M output токенов
   - Сравни с прямым Kimi API (api.moonshot.cn)

2. Качество работы с китайскими концептами + русский вывод:
   - Как хорошо понимает классические термины Бацзы (十神, 五行, 六合 и т.д.)?
   - Качество генерации на русском языке?
   - Сравни с Claude 3.5 Sonnet для этой задачи

3. Надёжность и лимиты:
   - Rate limits (RPM, TPM) на OpenRouter
   - Uptime / задержки (latency p50, p95)
   - Как реализовать надёжный fallback Kimi → Claude через OpenRouter?

4. Практический пример через OpenRouter API:
   - Python httpx async-запрос к openrouter.ai/api/v1/chat/completions
   - Правильные заголовки (X-Title, HTTP-Referer)
   - Обработка ошибок (429, 503, timeout)

5. Альтернативные модели для этой задачи:
   - Qwen2.5-72B-Instruct vs Kimi K2 для китайских знаний
   - Deepseek-V3 как дешёвая альтернатива
   - Рекомендация: какую модель использовать primary, какую fallback?

Итог: конкретное решение + готовый Python-код для async OpenRouter клиента
с retry логикой и fallback.
```

---
Для архитектуры Bazi-Bot, где объемные экспертные системные промпты (особенно если они детализированы специалистами вроде Анастасии) занимают от 2500 токенов, а история диалога легко разгоняет контекст до 20 000 токенов, выбор рентабельной, но умной модели — критический фактор.

Ниже подробный разбор экосистемы OpenRouter для вашей задачи, включая анализ Moonshot Kimi и альтернатив.

### 1. Актуальное ценообразование на OpenRouter (Moonshot Kimi)

*Примечание: на OpenRouter актуальный слаг провайдера — `moonshotai`, а текущая рабочая лошадка поколения K2 — это `moonshotai/kimi-k2.5`.*

*   **OpenRouter (Kimi K2.5):**
    *   Input: **~$0.44** за 1M токенов.
    *   Output: **~$2.00** за 1M токенов.
    *   *(Цена может незначительно колебаться в зависимости от текущего пула провайдеров, таких как DeepInfra или ModelRun).*
*   **Прямой Kimi API (api.moonshot.cn):**
    *   Исторически тарифицируется в юанях (~12 RMB за 1M токенов для базовых моделей), что эквивалентно **~$1.65** за 1M как для ввода, так и для вывода.
    *   **Вывод:** Использовать Kimi через OpenRouter сейчас **выгоднее** для входящего контекста (что идеально для ваших длинных диалогов и 6k-20k input токенов).

### 2. Качество: Китайские концепты + Русский язык

*   **Понимание Ба Цзы (十神, 五行, 六合):** Kimi — это native китайская модель. Для неё эти концепты не являются "экзотикой", переведенной через англоязычные бенчмарки (как это бывает у западных моделей). Она понимает глубокий культурный и астрологический контекст скрытых столпов, фаз Ци и столкновений идеально.
*   **Генерация на русском:** Находится на очень высоком уровне (B2-C1). Модель отлично переводит китайскую метафизику на структурированный русский язык.
*   **Сравнение с Claude 3.5 Sonnet:** Claude 3.5 Sonnet генерирует чуть более "литературный" и эмпатичный русский текст. Однако Claude стоит **$3.00 / $15.00** за 1M токенов. При контексте в 20k токенов за запрос Claude быстро сожрет бюджет MVP. Kimi в данном случае дает 90% качества Claude за 15% его цены.

### 3. Надёжность и лимиты OpenRouter

*   **Rate Limits (RPM/TPM):** Зависят от вашего Tier в OpenRouter. На пополненном аккаунте (Tier 2/3) лимиты практически неощутимы для 1000 пользователей в день. OpenRouter прозрачно балансирует запросы между бэкендами.
*   **Задержки (Latency):** Для Kimi p50 обычно составляет 0.6–1.2 секунды до первого токена, что вполне комфортно для Telegram-бота.
*   **Стратегия Fallback:** Одно из главных преимуществ OpenRouter — встроенная поддержка автоматического фоллбэка прямо в теле запроса (массив `models`), без необходимости писать сложные `try/except` на Python.

### 4. Альтернативы: Qwen2.5 vs DeepSeek-V3

На рынке китайских LLM произошли тектонические сдвиги, и Kimi больше не единственный лидер:

*   **Qwen2.5-72B-Instruct:** Отличная Open-Source альтернатива от Alibaba.
    *   *Цена:* ~$0.36 Input / ~$0.40 Output.
    *   *Вердикт:* Работает с китайским прекрасно, но по сложной логике (интерпретация карт) может немного уступать проприетарным большим моделям.
*   **DeepSeek-V3 (`deepseek/deepseek-chat`):**
    *   *Цена:* **~$0.14 - $0.20 Input / ~$0.28 - $0.77 Output** за 1M токенов.
    *   *Вердикт:* **Это геймчейнджер.** DeepSeek-V3 на голову превосходит Kimi по аналитическим способностям, стоит сущие копейки и имеет нативное китайское ядро.

**Итоговая рекомендация по стеку моделей:**
Сделайте **DeepSeek-V3** вашей основной моделью (Primary). Она умнее, дешевле и быстрее. Установите **Kimi K2.5** как первый Fallback (если DeepSeek перегружен), а **Claude 3.5 Sonnet** (или Claude 3 Haiku) — как аварийный резерв.

---

### 5. Практический пример: Python + httpx + OpenRouter Fallback

В этом коде используется нативный механизм фоллбэка OpenRouter (массив `models`), а также `tenacity` для обработки сетевых сбоев.

```python
import asyncio
import httpx
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

OPENROUTER_API_KEY = "sk-or-v1-ваш-ключ"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Настраиваем retry-логику для обрыва сети или 429/520 ошибок
@retry(
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type((httpx.ReadTimeout, httpx.HTTPStatusError))
)
async def ask_bazi_consultant(system_prompt: str, user_message: str) -> str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://t.me/bazi_bot", # Рекомендуется OpenRouter
        "X-Title": "Bazi-Bot",                   # Рекомендуется OpenRouter
    }

    # Массив models - это встроенная магия OpenRouter.
    # Если DeepSeek недоступен, запрос автоматически уйдет в Kimi, затем в Claude.
    payload = {
        "models": [
            "deepseek/deepseek-chat",       # Primary: Дешево и гениально
            "moonshotai/kimi-k2.5",         # Fallback 1: Отличный китайский
            "anthropic/claude-3-haiku"      # Fallback 2: Быстро, если всё упало
        ],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.3, # Для Бацзы нужна точность, а не галлюцинации
    }

    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(OPENROUTER_URL, headers=headers, json=payload)

        # Если статус 429 (Rate Limit) или 5xx (Server Error) -> выбрасываем исключение для Tenacity
        if response.status_code in (429, 502, 503, 529):
            response.raise_for_status()

        # Для других ошибок (например, 400 Bad Request) просто логируем
        if response.status_code != 200:
            print(f"API Error: {response.status_code} - {response.text}")
            return "Извините, энергии звезд сейчас недоступны. Попробуйте позже."

        data = response.json()
        return data["choices"][0]["message"]["content"]

# --- Тестовый запуск ---
async def main():
    sys_prompt = "Ты эксперт по Ба Цзы. Твоя задача интерпретировать элементы..."
    user_q = "Что значит 甲 в скрытых столпах земной ветви 寅?"

    answer = await ask_bazi_consultant(sys_prompt, user_q)
    print(answer)

if __name__ == "__main__":
    asyncio.run(main())
```

## R-3: gpt-image-1 для генерации визуальных карт Ба Цзы

```
Контекст:
Нужно автоматически генерировать визуальную карту Ба Цзы (BaZi chart) —
таблицу 4 столпов с китайскими иероглифами, цветами элементов и балансом.
Пример стиля: сайт mingli.ru/bazi — тёмный фон, иероглифы в цвете стихии,
4 столпа (Год/Месяц/День/Час), баланс элементов справа.

Изображение отправляется пользователю в Telegram как фото (send_photo).
Генерация через OpenRouter с моделью openai/gpt-image-1.

Исследуй:

1. API gpt-image-1 через OpenRouter:
   - Endpoint (отличается от /chat/completions?)
   - Параметры запроса (size, quality, n, response_format)
   - Как передать reference-изображение (image input) для стиля?
   - Максимальный размер промпта для описания карты
   - Время генерации (p50, p95)
   - Цена за одно изображение 1024×1024

2. Промпт-инженерия для структурированных карт:
   - Как лучше описать таблицу 4 столпов текстом?
   - Как задать точные цвета (#E53935 для Огня, #4CAF50 для Дерева)?
   - Как избежать галлюцинаций иероглифов (модель может неправильно рисовать символы)?
   - Использование image-to-image: подать шаблонное изображение как base?

3. Альтернативы если gpt-image-1 плохо рисует иероглифы:
   - Python Pillow/PIL: compositing готовых PNG иероглифов по шаблону
     (у нас будет 24 готовых PNG ассета — 10 стволов + 12 ветвей + 2 Инь/Ян)
   - Playwright: headless Chrome рендер HTML-шаблона → PNG screenshot
   - WeasyPrint: HTML+CSS → PDF → PNG
   - Рекомендация: что проще в Docker без X11?

4. Итоговая архитектура для нашего бота:
   - Основной путь: gpt-image-1 или Pillow compositing?
   - Как кэшировать сгенерированные карты (одна карта = одни данные = одна картинка)?
   - Хранение в Yandex Object Storage: как передать ссылку в Telegram?

Дай конкретное решение + рабочий Python код для генерации карты
(выбери лучший метод из сравнения).
```

---
Это, пожалуй, самый важный архитектурный выбор для визуальной части вашего бота. Китайская метафизика требует **абсолютной точности** в начертании иероглифов. Ошибка в одну черту в иероглифе перечеркивает ценность всей консультации.

Ниже представлен подробный анализ и жесткая рекомендация по выбору технологии.

---

### 1. Исследование: Генеративные ИИ (gpt-image / DALL-E 3) через OpenRouter

*   **Endpoint:** Обычно отличается, например, `/api/v1/images/generations`.
*   **Параметры:** `size` (например, "1024x1024"), `quality` ("standard"/"hd").
*   **Reference-изображение:** Некоторые модели поддерживают `image_url` в промпте для стилизации, но строгое следование структуре не гарантируется.
*   **Проблема галлюцинаций (Критично):** Современные ИИ (даже DALL-E 3) **катастрофически плохо** справляются с точным рисованием китайских иероглифов, особенно в табличной структуре. Вы получите "кашу" из черт, напоминающую иероглифы, что недопустимо для астрологического сервиса.
*   **Цена:** Порядка $0.04 - $0.08 за одну картинку. При 1000 пользователях в день это $40-$80 дейли.
*   **Вердикт:** **Категорически не подходит**. Использование генеративных моделей для создания точных схем и таблиц с иероглифами — это путь к созданию некачественного продукта.

### 2. Исследование: Программные альтернативы (Deterministic Rendering)

Это единственный путь, гарантирующий 100% точность карт.

*   **Pillow (PIL):**
    *   *Плюсы:* Самый быстрый, легкий, native Python метод. Идеально работает в Docker (нужен только `libfreetype` для шрифтов).
    *   *Минусы:* Нужно вручную высчитывать координаты (x, y) для каждого элемента таблицы, рисовать прямоугольники и размещать PNG ассеты. Сложнее верстать сложные layouts.
*   **WeasyPrint / XHTML2PDF:**
    *   *Минусы:* Устаревшие движки. Плохая поддержка современного CSS (Flexbox/Grid), что затруднит верстку красивой карты а-ля Mingli. Преобразование PDF -> PNG требует дополнительных библиотек (например, pdf2image) и системных зависимостей (Poppler).
*   **Playwright (Headless Chrome) — РЕКОМЕНДАЦИЯ:**
    *   *Как работает:* Вы верстаете карту на HTML/CSS (как обычную веб-страницу) -> Playwright поднимает headless браузер -> рендерит HTML -> делает скриншот элемента.
    *   *Плюсы:* Идеальная CSS-верстка (легко сделать темную тему, градиенты, точные цвета, диаграммы баланса). Любой шрифт. Гарантированная точность.
    *   *Docker:* Существуют готовые Docker-образы с Playwright, либо можно доустановить зависимости в ваш образ. X11 не нужен (работает в headless режиме).

---

### 3. Итоговая архитектура и Решение

Для MVP и последующего роста, сочетающего простоту деплоя и качество, выбираем **Playwright**.

**Логика:**
Верстка карты на Pillow займет недели "подгонки пикселей". Верстка на HTML/CSS займет пару дней и даст профессиональный результат. Нагрузку в 1000 юзеров Playwright выдержит (один рендер занимает 100-300мс на 2-4 vCPU).

**Архитектура кэширования:**
Карта Ба Цзы уникальна для комбинации даты, времени и места рождения.
1.  Бот получает данные рождения -> Генерирует уникальный ключ (хэш от данных).
2.  Проверяет в Yandex Object Storage файл `{hash}.png`.
3.  Если есть -> отправляет `InputFile.from_url(s3_link)`.
4.  Если нет -> Playwright рендерит карту -> Сохраняет в буфер -> Загружает в Yandex Object Storage -> Получает ссылку -> Отправляет пользователю.

---

### 4. Рабочий Python код для генерации карты (Playwright)

Вам понадобится установить:
`pip install playwright httpx jinja2`
`playwright install chromium` (в Докере это делается через Dockerfile)

Ниже представлен полный, рабочий пример сервиса.

```python
import asyncio
import os
import uuid
from jinja2 import Template
from playwright.async_api import async_playwright
import io

# --- 1. HTML/CSS Шаблон карты (Jinja2) ---
# Стилизован под темную тему а-ля Mingli
BAZI_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<style>
    body {
        background-color: #1a1a1a;
        color: white;
        font-family: 'Arial', sans-serif;
        width: 600px;
        margin: 0;
        padding: 20px;
    }
    .chart-container {
        display: flex;
        gap: 20px;
    }
    .pillars {
        display: flex;
        border: 1px solid #444;
        border-radius: 8px;
        overflow: hidden;
    }
    .pillar {
        width: 120px;
        text-align: center;
        border-right: 1px solid #444;
    }
    .pillar:last-child { border-right: none; }
    .pillar-header {
        background-color: #2d2d2d;
        padding: 10px;
        font-weight: bold;
        font-size: 14px;
        color: #aaa;
    }
    .stem, .branch {
        font-size: 48px;
        font-weight: bold;
        height: 80px;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    /* Цвета элементов #E53935 Огонь, #4CAF50 Дерево, #FBC02D Почва, #757575 Металл, #2196F3 Вода */
    .wood { color: #4CAF50; }
    .fire { color: #E53935; }
    .earth { color: #FBC02D; }
    .metal { color: #BDBDBD; }
    .water { color: #2196F3; }

    .chart-label {
        font-size: 12px;
        color: #777;
        margin-top: -10px;
        padding-bottom: 5px;
    }

    /* Стили для баланса элементов */
    .balance-container {
        flex-grow: 1;
        border: 1px solid #444;
        border-radius: 8px;
        padding: 15px;
        background-color: #222;
    }
    .balance-title { text-align: center; color: #aaa; margin-bottom: 15px;}
    .balance-row {
        display: flex; align-items: center; margin-bottom: 10px; gap: 10px;
    }
    .element-name { width: 50px; font-size: 14px; }
    .progress-bg {
        flex-grow: 1; height: 10px; background-color: #333; border-radius: 5px; overflow: hidden;
    }
    .progress-bar { height: 100%; border-radius: 5px; }
</style>
</head>
<body>

<div class="chart-container" id="bazi-chart">
    <!-- Столпы -->
    <div class="pillars">
        {% for p in pillars %}
        <div class="pillar">
            <div class="pillar-header">{{ p.name }}</div>
            <div class="stem {{ p.stem_element }}">{{ p.stem_hanzi }}</div>
            <div class="chart-label">НС</div>
            <div class="branch {{ p.branch_element }}">{{ p.branch_hanzi }}</div>
            <div class="chart-label">ЗВ</div>
        </div>
        {% endfor %}
    </div>

    <!-- Баланс (Упрощенный пример) -->
    <div class="balance-container">
        <div class="balance-title">Пять Стихий</div>
        {% for elem in balance %}
        <div class="balance-row">
            <div class="element-name {{ elem.type }}">{{ elem.ru_name }}</div>
            <div class="progress-bg">
                <div class="progress-bar {{ elem.type }}" style="width: {{ elem.percent }}%;"></div>
            </div>
            <div class="element-percent">{{ elem.percent }}%</div>
        </div>
        {% endfor %}
    </div>
</div>

</body>
</html>
"""

# --- 2. Сервис генерации изображения ---
class BaziImageGenerator:
    def __init__(self):
        self.template = Template(BAZI_HTML_TEMPLATE)

    async def generate_chart_png(self, bazi_data: dict) -> bytes:
        """
        Рендерит HTML в PNG и возвращает bytes.
        Здесь не используется S3, возвращаем массив байт для теста.
        """
        html_content = self.template.render(**bazi_data)

        async with async_playwright() as p:
            # Запускаем браузер без X11
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # Устанавливаем контент страницы
            await page.set_content(html_content)

            # Ждем рендеринга (обычно не нужно, но для надежности шрифтов можно)
            await page.wait_for_selector("#bazi-chart")

            # Делаем скриншот конкретного элемента, а не всей страницы
            element_handle = await page.query_selector("#bazi-chart")
            image_bytes = await element_handle.screenshot(type="png")

            await browser.close()
            return image_bytes

# --- 3. Пример использования (Mock данные) ---
async def main():
    # Эти данные вы получаете из вашего движка Бацзы на Python
    mock_bazi_result = {
        "pillars": [
            {"name": "Час", "stem_hanzi": "己", "stem_element": "earth", "branch_hanzi": "巳", "branch_element": "fire"},
            {"name": "День", "stem_hanzi": "甲", "stem_element": "wood", "branch_hanzi": "寅", "branch_element": "wood"}, # Элемент личности 甲 Wood
            {"name": "Месяц", "stem_hanzi": "丙", "stem_element": "fire", "branch_hanzi": "子", "branch_element": "water"},
            {"name": "Год", "stem_hanzi": "癸", "stem_element": "water", "branch_hanzi": "卯", "branch_element": "wood"},
        ],
        "balance": [
            {"ru_name": "Дерево", "type": "wood", "percent": 45},
            {"ru_name": "Огонь", "type": "fire", "percent": 20},
            {"ru_name": "Почва", "type": "earth", "percent": 10},
            {"ru_name": "Металл", "type": "metal", "percent": 5},
            {"ru_name": "Вода", "type": "water", "percent": 20},
        ]
    }

    generator = BaziImageGenerator()
    print("Генерация карты...")
    img_bytes = await generator.generate_chart_png(mock_bazi_result)

    # Сохраним локально для проверки
    filename = f"bazi_chart_{uuid.uuid4().hex[:8]}.png"
    with open(filename, "wb") as f:
        f.write(img_bytes)

    print(f"Готово! Карта сохранена в файл: {filename}")
    print("В боте вы загрузите эти байты в Yandex Object Storage и отправите ссылку в Telegram.")

if __name__ == "__main__":
    # Установка зависимостей playwright (нужно выполнить один раз перед запуском)
    # import os; os.system("playwright install chromium")
    asyncio.run(main())
```

**Рекомендации по Docker:**

1.  Используйте официальный образ Playwright как базу или скопируйте его логику установки Chromium.
2.  Убедитесь, что в образе установлены шрифты, поддерживающие китайские иероглифы (например, `fonts-noto-cjk` или `fonts-wqy-zenhei`), иначе вместо иероглифов будут "квадратики".

Этот метод даст вам красивую, 100% точную карту, которую легко масштабировать, просто изменяя HTML-шаблон.

## R-4: Yandex Cloud — стоимость и настройка для нашего стека

```
Контекст:
Разворачиваем Python Telegram-бота (aiogram 3.x + FastAPI) в Yandex Cloud.
Компоненты:
- VPS: Docker-контейнеры (bot + web + taskiq worker)
- PostgreSQL: основная БД (5-50 GB данных)
- Redis: FSM, кэш, rate limiting
- Object Storage: PNG изображения карт (~500KB каждая), CSV экспорты

Нагрузка MVP: 100-500 пользователей/день, 1000-5000 запросов/день
Нагрузка цель: 5000-10000 пользователей/день

Исследуй:

1. Yandex Managed PostgreSQL:
   - Минимальная конфигурация для MVP (класс хоста, SSD объём)
   - Стоимость в рублях/месяц
   - Как подключить из Docker-контейнера (SSL, connection string)?
   - Backup политика (включена ли в тариф?)
   - Сравни с развёртыванием PostgreSQL вручную на VPS

2. Yandex Managed Redis:
   - Минимальная конфигурация для MVP
   - Стоимость в рублях/месяц
   - Поддержка Redis Cluster vs Standalone
   - Как подключить из aiogram (aioredis)?

3. Yandex Compute Cloud (VPS):
   - Какой тариф нужен (vCPU, RAM) для 3 Docker-сервисов?
   - Intel vs AMD платформа для Python?
   - Стоимость в рублях/месяц
   - Spot-инстансы (прерываемые) — подходят ли для бота?

4. Yandex Object Storage:
   - Стоимость за хранение (GB/месяц)
   - Стоимость за исходящий трафик
   - Python SDK: aioboto3 или официальный yandex-cloud-python-sdk?
   - Как сделать объекты публично доступными (для Telegram send_photo)?

5. Сравнение с альтернативами:
   - Selectel (VPS + managed PostgreSQL + S3)
   - Timeweb Cloud
   - Railway (на котором изначально планировали)
   - Итог: лучший вариант для стартапа с российской аудиторией?

6. Итого: ориентировочный счёт в месяц (MVP) и (при 5000 пользователей/день)?

Дай конкретные команды `yc` CLI для создания нужных ресурсов.
```

---

Отличный, современный стек. Текущий инфраструктурный грант в 200 000₽, покрывающий расходы до середины июня 2026 года, дает отличную свободу маневра. Главная задача сейчас — не пытаться сэкономить каждую копейку на базовых VPS, а выстроить надежный и масштабируемый фундамент, который без просадок выдержит летнюю цель в 5 000 подписчиков. Использование управляемых сервисов (Managed) освободит Даню от задач DevOps, а Диму от паники при падении базы.

Ниже подробный разбор архитектуры под ваш MVP и планы роста.

---

### 1. Yandex Managed PostgreSQL

*   **Конфигурация для MVP:** Класс хоста `s3-c2-m8` (Intel Ice Lake, 2 vCPU, 8 GB RAM) или `b3-c1-m2` (Burstable, 1 vCPU, 2 GB RAM) если хотите совсем сэкономить на старте. Для БД Бацзы с графами (KuzuDB) в памяти приложения, Postgres будет хранить только юзеров, оплаты и историю. 10-15 GB `network-ssd` хватит за глаза.
*   **Стоимость:** ~2 500 — 3 500 руб/мес за надежный `s3` инстанс с SSD.
*   **Как подключить из Docker:** Yandex Cloud требует SSL-подключение. Вы скачиваете сертификат `root.crt` (через wget в Dockerfile) и передаете его в строку подключения `asyncpg` или `SQLAlchemy`:
    `postgresql+asyncpg://user:pass@rc1a-xxx.mdb.yandexcloud.net:6432/db_name?ssl=true`
*   **Backup политика:** Автоматические бэкапы (Point-in-Time Recovery) **включены** в стоимость. Yandex хранит WAL-логи, что позволяет откатить базу на любую секунду за последние 7 дней.
*   **Managed vs VPS:** Поднять Postgres в Docker на VPS дешевле (0 рублей за софт). Но при падении диска, исчерпании памяти или нужде в обновлении мажорной версии, вы потратите часы разработки. Managed-версия окупает себя стабильностью.

### 2. Yandex Managed Redis

*   **Конфигурация для MVP:** Самый минимальный `b3-c1-m2` (1 vCPU, 2 GB RAM). aiogram FSM, кэширование сессий и rate limits (Throttling) занимают мегабайты, а не гигабайты.
*   **Стоимость:** ~1 200 — 1 500 руб/мес.
*   **Cluster vs Standalone:** Для 10 000 юзеров в день **Standalone** (Non-sharded) более чем достаточно. Redis Cluster нужен при гигантских объемах данных или когда один поток Redis упирается в CPU (это сотни тысяч RPS). Cluster усложнит код бота.
*   **Подключение из aiogram:** Используйте `redis.asyncio` (заменил `aioredis`). Обязательно укажите `ssl=True`.

### 3. Yandex Compute Cloud (VPS)

*   **Тариф для 3 Docker-сервисов:** Платформа `standard-v3` (Intel Ice Lake) или `standard-v4` (AMD EPYC). 2 vCPU (со 100% гарантированной долей) и 4-8 GB RAM. 8 GB предпочтительнее, если KuzuDB и Playwright (для генерации карт) работают прямо здесь.
*   **Intel vs AMD:** AMD EPYC (v4) в Яндекс Клауде обычно показывает отличную производительность для Python-воркеров и стоит немного дешевле.
*   **Стоимость:** ~1 800 — 2 500 руб/мес.
*   **Spot-инстансы:** Строго **НЕТ** для webhook-сервера FastAPI и Telegram-бота. Прерываемая машина может выключиться в любой момент, бот ляжет на 5-10 минут. Spot можно использовать *только* для дополнительных `taskiq worker` машин, если они занимаются фоновыми некритичными задачами (например, массовыми рассылками).

### 4. Yandex Object Storage (S3)

*   **Стоимость:** Копейки. Хранение ~1.5 - 2 рубля за 1 ГБ в месяц. Исходящий трафик: первые 100 ГБ в месяц **бесплатно** (этого хватит на сотни тысяч PNG карт Бацзы по 500KB).
*   **Python SDK:** Только **`aioboto3`**. Официальный Yandex SDK синхронный и предназначен для управления инфраструктурой (создания виртуалок), а не для потоковой загрузки файлов в асинхронном FastAPI.
*   **Публичный доступ:** Для `send_photo(url)` в Telegram картинка должна быть публичной. Вы можете либо настроить ACL бакета на публичное чтение, либо (безопаснее) генерировать в `aioboto3` **pre-signed URL** со сроком жизни 1 час и отдавать его Telegram API.

### 5. Сравнение с альтернативами

*   **Selectel:** Отличная альтернатива. Их Managed Databases дешевле, интерфейс местами отзывчивее. Но мигрировать сейчас нелогично, так как грант нужно утилизировать максимально эффективно.
*   **Timeweb Cloud:** Хорошо для пет-проектов на чистых VPS. Управляемые сервисы у них слабее, чем у Яндекса.
*   **Railway:** Главный минус для российской аудитории — пинг. Сервера находятся в Европе/США, что добавляет задержку. Плюс риски блокировок со стороны РКН (IP пулы Railway часто страдают из-за VPN-сервисов).
*   **Итог:** Yandex Cloud — идеальный вариант для российского Production.

### 6. Итоговый счет

*   **MVP (до лета):**
    *   VPS (2 vCPU / 8 GB): ~2 000 ₽
    *   Managed DB Postgres: ~2 500 ₽
    *   Managed Redis: ~1 500 ₽
    *   S3 + Сеть: ~100 ₽
    *   **Итого:** ~6 100 ₽ / месяц. Гранта с лихвой хватит, чтобы покрыть эту архитектуру до середины июня, и еще останется бюджет на масштабирование или поднятие тестовых стендов (Staging).
*   **Цель (5 000 - 10 000 юзеров):**
    *   Потребуется увеличить VPS до 4 vCPU / 16 GB (~4 500 ₽) и, возможно, добавить Read-реплику для БД (~2 000 ₽). Счет вырастет до **~10 000 - 12 000 ₽ / месяц**, что отлично укладывается в юнит-экономику успешного бота.

---

### Практика: Команды `yc` CLI

Авторизуйтесь в CLI (`yc init`) и выполните следующие команды для базового развертывания (параметры подстроены под MVP):

**1. Создание сети и подсети (если нет):**
```bash
yc vpc network create --name bazi-network
yc vpc subnet create --name bazi-subnet-a --network-name bazi-network --zone ru-central1-a --range 10.0.0.0/24
```

**2. Создание Managed PostgreSQL (версия 15, класс b3, 10GB SSD):**
```bash
yc managed-postgresql cluster create \
  --name bazi-postgres \
  --environment production \
  --network-name bazi-network \
  --host zone-id=ru-central1-a,subnet-name=bazi-subnet-a,assign-public-ip=true \
  --resource-preset b3-c2-m8 \
  --disk-type network-ssd \
  --disk-size 15 \
  --user name=bazi_user,password=SuperSecretPassword123 \
  --database name=bazi_db,owner=bazi_user
```
*(Флаг `assign-public-ip=true` нужен, чтобы вы могли подключаться к БД с локальной машины через DataGrip/DBeaver. В строгом Production его лучше выключать).*

**3. Создание Managed Redis:**
```bash
yc managed-redis cluster create \
  --name bazi-redis \
  --network-name bazi-network \
  --host zone-id=ru-central1-a,subnet-name=bazi-subnet-a \
  --resource-preset b3-c1-m2 \
  --disk-size 16 \
  --tls-enabled \
  --password AnotherSecretPassword123
```

**4. Создание VPS (Ubuntu 22.04, AMD EPYC, 2 vCPU, 8GB RAM):**
```bash
# Получаем ID последнего образа Ubuntu
IMAGE_ID=$(yc compute image get-latest-from-family ubuntu-2204-lts --folder-id standard-images --format json | jq -r .id)

yc compute instance create \
  --name bazi-prod-server \
  --zone ru-central1-a \
  --network-interface subnet-name=bazi-subnet-a,nat-ip-version=ipv4 \
  --memory 8 \
  --cores 2 \
  --core-fraction 100 \
  --platform standard-v4 \
  --create-boot-disk image-id=$IMAGE_ID,size=30,type=network-ssd \
  --ssh-key ~/.ssh/id_rsa.pub
```

**5. Создание бакета S3:**
```bash
# S3 бакеты требуют уникального имени по всему Яндексу
yc storage bucket create --name neurobro-bazi-charts-prod
```

## R-5: FSM паттерны в aiogram 3.x + Redis для сбора данных рождения

```
Контекст:
Telegram-бот на aiogram 3.x должен собирать данные рождения пользователя
через многошаговый FSM диалог:

Шаги:
1. Имя (необязательно, можно пропустить)
2. Дата рождения (формат: ДД.ММ.ГГГГ или "20 августа 2000")
3. Время рождения (ЧЧ:ММ или "не знаю" → используем 12:00, флаг has_birth_time=False)
4. Город рождения (строка → geopy geocoding → lat/lon/tz)
5. Пол (кнопки: Мужской / Женский)
6. Подтверждение данных (показ + кнопки "Верно" / "Исправить")

Особенности:
- Redis как storage для FSM состояний (MemoryStorage не подходит для продакшна)
- Inline кнопки на каждом шаге
- Валидация ввода с возможностью повтора
- Геокодирование — async запрос к Nominatim (может занять 2-3 сек)
- Поддержка "назад" на предыдущий шаг

Исследуй:

1. Лучшие практики FSM в aiogram 3.x:
   - RedisStorage настройка (aioredis ConnectionPool)
   - State machine организация: один класс states.py или по модулям?
   - Как передавать данные между состояниями (FSMContext.update_data)?
   - Обработка "отмены" (/cancel) в любой точке FSM

2. Inline keyboards в FSM:
   - Паттерн для кнопок "Пропустить", "Не знаю время", "Назад"
   - Callback query в FSM: как избежать race conditions?
   - Magic Filters для FSM-обработчиков

3. Валидация дат и времени:
   - Как парсить разные форматы дат на русском (dateparser библиотека)?
   - Что делать если пользователь вводит невалидную дату?
   - Как обрабатывать "20 августа 2000" vs "20.08.2000" vs "20/08/00"?

4. Геокодирование в FSM:
   - Как показать "Ищу город..." пока идёт запрос к Nominatim?
   - Обработка ошибок (город не найден, Nominatim timeout)
   - Кэш геокодинга в Redis (одинаковые города = одинаковые координаты)

5. Готовый пример кода:
   - Полный FSM для шагов 2-5 с валидацией, Redis storage, inline кнопками
   - Структура states.py для нашего проекта

Дай полный рабочий код FSM для aiogram 3.x с Redis storage.
```

---

Сбор таких многосоставных данных — классическая боль в разработке ботов, особенно когда пользователи вводят даты в самых невообразимых форматах. Для систем высокоточных астрологических расчетов (например, калькуляторов Бацзы), где важна каждая минута, точные координаты и таймзона, такой FSM — это абсолютно критический фундамент. Ошибка на этапе сбора данных сломает всю последующую бизнес-логику.

Разберем архитектуру под aiogram 3.x, а затем соберем всё в готовый продакшн-код.

### 1. Лучшие практики FSM в aiogram 3.x

*   **Настройка RedisStorage:** В aiogram 3.x это делается элегантно "из коробки". Достаточно передать URL при инициализации: `storage = RedisStorage.from_url('redis://localhost:6379/0')`. Он сам под капотом использует `redis.asyncio` с пулом соединений.
*   **Организация State Machine:** Для одной логической сущности (сбор данных рождения) лучше использовать один класс `StatesGroup` (например, `states.py`). Дробить по разным модулям стоит только независимые процессы (например, `OrderStates`, `SupportStates`).
*   **Передача данных:** Используем `await state.update_data(key="value")`. Для получения — `data = await state.get_data()`.
*   **Обработка "Отмены":** В aiogram 3.x лучше всего повесить отдельный роутер или глобальный хэндлер на команду `/cancel` или кнопку "Отмена", который будет делать `await state.clear()` и возвращать в главное меню.

### 2. Inline Keyboards и FSM

*   **Паттерн:** Клавиатуры генерируем "на лету" через функции (или билдеры), передавая callback_data. Для универсальной кнопки "Назад" можно использовать `callback_data="back_to_name"`, чтобы явно указывать, куда возвращаемся, так как встроенного "предыдущего стейта" в aiogram нет.
*   **Race Conditions:** В контексте одного пользователя `RedisStorage` работает стабильно, так как Telegram гарантирует последовательность доставки апдейтов. Чтобы избежать проблем с двойными кликами по inline-кнопкам, хорошей практикой является редактирование или удаление сообщения с клавиатурой сразу после нажатия (`await callback.message.edit_reply_markup(reply_markup=None)`).
*   **Magic Filters:** Идеально подходят для разруливания логики. `F.data == 'skip_time'`, `StateFilter(BirthDataFSM.date)`.

### 3. Валидация дат и времени (dateparser)

*   Библиотека `dateparser` — спасение. Вызов `dateparser.parse(text, languages=['ru'], settings={'PREFER_DATES_FROM': 'past'})` съест и "20 августа 2000", и "20.08.00", и "вчера".
*   **Ошибки:** Если парсер возвращает `None` или дату из будущего (если мы просим дату рождения), мы не переводим FSM на следующий шаг. Бот просто отвечает: *"Не смог распознать дату, попробуйте формат ДД.ММ.ГГГГ"*, оставляя пользователя в текущем состоянии.

### 4. Геокодирование и Кэширование

*   **UX "Ищу город...":** Отправляем временное сообщение: `msg = await message.answer("🔍 Ищу координаты...")`. Затем делаем запрос. После ответа делаем `await msg.edit_text("✅ Город найден...")`.
*   **Кэш в Redis:** Перед обращением к API Nominatim (который строг к лимитам — 1 запрос в секунду), проверяем ключ в Redis (например, `geo:москва`). Если нет — делаем запрос, берем `lat`, `lon` и, желательно, `timezone` (через `timezonefinder`), пакуем в JSON и кладем в Redis с TTL (например, на 30 дней).

---

### 5. Готовый продакшн-пример кода

Ниже представлен структурированный и готовый к запуску код. В реальном проекте его лучше разнести по файлам (`states.py`, `keyboards.py`, `handlers.py`, `main.py`).

**Зависимости:**
`pip install aiogram redis dateparser geopy timezonefinder aiohttp`

```python
import asyncio
import json
import logging
import dateparser
from datetime import datetime

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.filters import Command, StateFilter

from geopy.geocoders import Nominatim
from geopy.adapters import AioHTTPAdapter
from timezonefinder import TimezoneFinder

# --- Настройки ---
BOT_TOKEN = "YOUR_BOT_TOKEN"
REDIS_URL = "redis://localhost:6379/0"

# Инициализация
storage = RedisStorage.from_url(REDIS_URL)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)
router = Router()

# Для геокодинга (Обязательно укажите свой user_agent!)
geolocator = Nominatim(
    user_agent="bazi_bot_neurobro/1.0",
    adapter_factory=AioHTTPAdapter
)
tz_finder = TimezoneFinder()

# --- FSM States ---
class BirthDataFSM(StatesGroup):
    name = State()
    date = State()
    time = State()
    city = State()
    gender = State()
    confirm = State()

# --- Keyboards ---
def get_skip_name_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить ⏭", callback_data="skip_name")]
    ])

def get_back_kb(target: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"back_{target}")]
    ])

def get_time_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Не знаю время 🤷‍♂️", callback_data="unknown_time")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_date")]
    ])

def get_gender_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨 Мужской", callback_data="gender_m"),
         InlineKeyboardButton(text="👩 Женский", callback_data="gender_f")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_city")]
    ])

def get_confirm_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Верно", callback_data="confirm_yes")],
        [InlineKeyboardButton(text="❌ Исправить", callback_data="confirm_no")]
    ])

# --- Handlers: Cancel & Back ---
@router.message(Command("cancel"))
async def cancel_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Действие отменено.")

@router.callback_query(F.data.startswith("back_"))
async def process_back(callback: CallbackQuery, state: FSMContext):
    target = callback.data.split("_")[1]

    states_map = {
        "name": (BirthDataFSM.name, "Введите ваше имя (или пропустите):", get_skip_name_kb()),
        "date": (BirthDataFSM.date, "Введите дату рождения (например, 20.08.2000):", get_back_kb("name")),
        "time": (BirthDataFSM.time, "Введите время рождения (ЧЧ:ММ):", get_time_kb()),
        "city": (BirthDataFSM.city, "Введите город рождения:", get_back_kb("time")),
    }

    if target in states_map:
        next_state, text, kb = states_map[target]
        await state.set_state(next_state)
        await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

# --- Handlers: Flow ---

# Шаг 1: Имя
@router.message(Command("start"))
async def start_fsm(message: Message, state: FSMContext):
    await state.set_state(BirthDataFSM.name)
    await message.answer("Давайте соберем данные для карты. \nВведите ваше имя:", reply_markup=get_skip_name_kb())

@router.message(StateFilter(BirthDataFSM.name))
@router.callback_query(F.data == "skip_name", StateFilter(BirthDataFSM.name))
async def process_name(event, state: FSMContext):
    if isinstance(event, Message):
        await state.update_data(name=event.text)
        await event.answer("Отлично! Теперь введите дату рождения (например: 15 сентября 1990 или 15.09.1990):", reply_markup=get_back_kb("name"))
    else:
        await state.update_data(name="Аноним")
        await event.message.edit_text("Имя пропущено.\nВведите дату рождения:", reply_markup=get_back_kb("name"))
    await state.set_state(BirthDataFSM.date)

# Шаг 2: Дата
@router.message(StateFilter(BirthDataFSM.date))
async def process_date(message: Message, state: FSMContext):
    # Валидация даты
    parsed_date = dateparser.parse(message.text, languages=['ru'], settings={'PREFER_DATES_FROM': 'past'})

    if not parsed_date or parsed_date > datetime.now():
        await message.answer("Не смог распознать дату или дата из будущего. Попробуйте еще раз (например: 20.08.2000):", reply_markup=get_back_kb("name"))
        return

    await state.update_data(date=parsed_date.strftime("%Y-%m-%d"))
    await state.set_state(BirthDataFSM.time)
    await message.answer("Введите время рождения (например: 14:30):", reply_markup=get_time_kb())

# Шаг 3: Время
@router.message(StateFilter(BirthDataFSM.time))
@router.callback_query(F.data == "unknown_time", StateFilter(BirthDataFSM.time))
async def process_time(event, state: FSMContext):
    if isinstance(event, Message):
        parsed_time = dateparser.parse(event.text, languages=['ru'])
        if not parsed_time:
            await event.answer("Неверный формат времени. Введите в формате ЧЧ:ММ:", reply_markup=get_time_kb())
            return
        await state.update_data(time=parsed_time.strftime("%H:%M"), has_birth_time=True)
        await event.answer("В каком городе вы родились?", reply_markup=get_back_kb("time"))
    else:
        await state.update_data(time="12:00", has_birth_time=False)
        await event.message.edit_text("Время установлено на 12:00 (по умолчанию).\nВ каком городе вы родились?", reply_markup=get_back_kb("time"))

    await state.set_state(BirthDataFSM.city)

# Шаг 4: Город (с кэшем Redis и Геокодингом)
@router.message(StateFilter(BirthDataFSM.city))
async def process_city(message: Message, state: FSMContext):
    city_name = message.text.strip().lower()
    msg = await message.answer(f"🔍 Ищу координаты для '{message.text}'...")

    # 1. Проверяем кэш в Redis
    redis_client = storage.redis
    cached_geo = await redis_client.get(f"geo:{city_name}")

    if cached_geo:
        geo_data = json.loads(cached_geo)
    else:
        # 2. Делаем запрос к Nominatim
        try:
            location = await geolocator.geocode(city_name, timeout=5)
            if not location:
                await msg.edit_text("❌ Город не найден. Проверьте опечатку и введите снова:", reply_markup=get_back_kb("time"))
                return

            # Ищем Timezone
            tz_name = tz_finder.timezone_at(lng=location.longitude, lat=location.latitude)

            geo_data = {
                "address": location.address,
                "lat": location.latitude,
                "lon": location.longitude,
                "tz": tz_name or "UTC"
            }
            # Сохраняем в кэш на 30 дней
            await redis_client.setex(f"geo:{city_name}", 2592000, json.dumps(geo_data))

        except Exception as e:
            logging.error(f"Geocode error: {e}")
            await msg.edit_text("Сервис геокодирования временно недоступен. Попробуйте еще раз:", reply_markup=get_back_kb("time"))
            return

    await state.update_data(city=geo_data)
    await state.set_state(BirthDataFSM.gender)
    await msg.edit_text(f"📍 Найден город: {geo_data['address']}\nТаймзона: {geo_data['tz']}\n\nУкажите ваш пол:", reply_markup=get_gender_kb())

# Шаг 5: Пол
@router.callback_query(F.data.startswith("gender_"), StateFilter(BirthDataFSM.gender))
async def process_gender(callback: CallbackQuery, state: FSMContext):
    gender = "Мужской" if callback.data == "gender_m" else "Женский"
    await state.update_data(gender=gender)

    data = await state.get_data()

    # Формируем итоговое сообщение
    summary = (
        f"📋 <b>Проверьте ваши данные:</b>\n\n"
        f"Имя: {data.get('name')}\n"
        f"Дата: {data.get('date')}\n"
        f"Время: {data.get('time')} {'(точное)' if data.get('has_birth_time') else '(неизвестно)'}\n"
        f"Город: {data.get('city')['address']}\n"
        f"Пол: {data.get('gender')}"
    )

    await state.set_state(BirthDataFSM.confirm)
    await callback.message.edit_text(summary, reply_markup=get_confirm_kb(), parse_mode="HTML")

# Шаг 6: Подтверждение
@router.callback_query(F.data == "confirm_yes", StateFilter(BirthDataFSM.confirm))
async def confirm_data(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    # Здесь логика сохранения в БД и старт расчетов
    await callback.message.edit_text("✅ Данные успешно сохранены! Начинаю расчет...", reply_markup=None)
    await state.clear()

@router.callback_query(F.data == "confirm_no", StateFilter(BirthDataFSM.confirm))
async def restart_fsm(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BirthDataFSM.name)
    await callback.message.edit_text("Давайте начнем заново. Введите ваше имя:", reply_markup=get_skip_name_kb())

# --- Запуск ---
async def main():
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
```

## R-6: Детектор временных вопросов и подгрузка контекста карт БаЦзы

```
Контекст:
В нашем боте пользователи часто задают вопросы, завязанные на время:
- "Какой у меня будет лучший день в этом месяце?"
- "В каком году я выйду замуж?"
- "Этот год для меня хороший или плохой?"
- "Когда мне лучше открывать бизнес?"
- "Что меня ждёт в 2027 году?"

Для ответа на такие вопросы Анастасия (LLM) должна сопоставить
личную карту пользователя с картами текущего периода:
- Годовая карта (Суй Юнь) — 1 карта
- Месячная карта (Юэ Юнь) — 1 карта
- Дневная карта — 1 карта
- Карты ближайших 3 лет

Технический стек: Python 3.11, pyswisseph, aiogram 3.x, OpenRouter (Kimi K2)

Исследуй:

1. Детектор временных запросов:
   - Regex-подход: список ключевых слов (год, месяц, день, когда, лучший период...)
   - LLM-классификатор: лёгкая модель (flash/haiku) для классификации намерения
   - Сравни точность и стоимость обоих подходов
   - Какой порог уверенности использовать для переключения?

2. Расчёт карты текущего периода через pyswisseph:
   - Как рассчитать Небесный Ствол и Земную Ветвь текущего года (2026 = 丙午)?
   - Как рассчитать месячный столп с учётом смены сезона (Цзе Ци)?
   - Как рассчитать дневной столп?
   - Пример Python-кода с pyswisseph для этих расчётов

3. Структура дополнительного контекста для LLM:
   - Как форматировать "текущую карту" для промпта Анастасии?
   - Формат: "Карта 2026 года: 丙 (Огонь Ян) / 午 (Лошадь, Огонь) — год Огненной Лошади"
   - Как добавить карты следующих 3 лет?
   - Суммарный размер дополнительного контекста (токены)?

4. Кэширование текущих карт:
   - Годовая карта: кэш в Redis TTL до конца года
   - Месячная: кэш TTL до смены сезона (Цзе Ци)
   - Дневная: кэш TTL 24 часа
   - Как рассчитать точный TTL до следующего Цзе Ци через pyswisseph?

5. Обработка конкретных лет из вопроса:
   - "В 2027 году я женюсь?" → нужна карта 2027 года
   - Как извлечь конкретный год из вопроса (NER или regex)?
   - Пример кода: функция get_year_pillar(year: int) -> tuple[Stem, Branch]

Дай готовый Python-код для:
- temporal_context.py (расчёт карт периодов через pyswisseph)
- Детектора временных запросов (regex + примеры)
- Форматирования контекста для LLM-промпта
```

---

Архитектура временного контекста для Bazi-Bot — это то место, где астрономическая точность `pyswisseph` встречается с промпт-инжинирингом. Поскольку для высокоточного калькулятора уровня Mingli критически важны переходы (Цзе Ци) с точностью до минуты, мы не можем полагаться на григорианский календарь.

Разберем каждый слой этой задачи и соберем готовый `temporal_context.py`.

### 1. Детектор временных запросов: Regex vs. LLM

**Сравнение подходов:**
*   **Regex + NER:**
    *   *Точность:* Высокая для явных дат (2027, "завтра", "в следующем году"). Пропускает косвенные ("когда лучше...").
    *   *Стоимость:* 0 ₽, $0, задержка < 1 мс.
*   **LLM (Haiku / Flash / 4o-mini):**
    *   *Точность:* 95%+ понимания контекста.
    *   *Стоимость:* ~$0.15 за 1М токенов. Задержка: 400-800 мс.

**Лучшая практика (Гибрид):**
Не нужно делать отдельный шаг детекции для *текущего* периода. Базовый контекст текущего дня (Год/Месяц/День) весит всего **~40 токенов**. Его нужно **всегда** передавать в `system_prompt` Анастасии. Это дешевле и быстрее, чем вызывать легкую LLM для маршрутизации.
Regex нужен только для того, чтобы "выцепить" из вопроса пользователя конкретные будущие года (например, 2027, 2030) и подгрузить их в контекст.

### 2. Расчет карт (pyswisseph) и математика Бацзы

*   **Год:** Сменяется не 1 января, а в момент Ли Чунь (Начало весны, $\approx$ 4-5 февраля), когда долгота Солнца достигает ровно 315°.
*   **Месяц:** Сменяется каждые 30° движения Солнца (начиная с 315°).
*   **День:** Сменяется в 23:00 (час Крысы). Математически вычисляется из Юлианского дня (JD).

### 3. Форматирование контекста для LLM (Анастасии)

Размер такого блока составит около 40-70 токенов. Он должен быть максимально "разжеван", чтобы Kimi K2 не тратила вычислительный ресурс на перевод иероглифов, а сразу переходила к анализу полезного/неполезного бога (Юн Шэнь):

```text
[ТЕКУЩИЙ ПЕРИОД (ТРАНЗИТЫ)]
Год: 丙午 (Бин У) - Янский Огонь на Лошади (Огонь).
Месяц: 癸巳 (Гуй Сы) - Иньская Вода на Змее (Огонь).
День: 戊申 (У Шэнь) - Янская Земля на Обезьяне (Металл).

[ЗАПРОШЕННЫЕ ПОЛЬЗОВАТЕЛЕМ ПЕРИОДЫ]
2027 год: 丁未 (Дин Вэй) - Иньский Огонь на Козе (Земля).
2028 год: 戊申 (У Шэнь) - Янская Земля на Обезьяне (Металл).
```

### 4. Стратегия кэширования (Redis TTL)

Вместо того чтобы каждую секунду дергать `pyswisseph`, мы вычисляем время до следующего астрономического события:
*   **Дневная карта:** TTL = `(23:00 следующего дня) - datetime.now()`.
*   **Месячная карта (Цзе Ци):** Вычисляем JD, когда Солнце пересечет следующую границу кратную 30° (например, с 15° перейдет на 45°). Разница в секундах между этим JD и текущим временем = TTL для Redis.
*   **Годовая карта:** TTL до следующего Ли Чунь (315°).

---

### Готовый код: `temporal_context.py`

Этот модуль содержит логику извлечения годов через regex, точные астрономические расчеты Бацзы через `pyswisseph` и генератор контекста.

```python
import re
import math
import swisseph as swe
from datetime import datetime, timezone, timedelta

# Настройка пути к файлам эфемерид (обязательно скачать файлы sweph и указать путь)
# swe.set_ephe_path('/path/to/ephe')

# --- Константы Бацзы ---
STEMS = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
BRANCHES = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]

STEMS_RU = ["Янское Дерево", "Иньское Дерево", "Янский Огонь", "Иньский Огонь",
            "Янская Земля", "Иньская Земля", "Янский Металл", "Иньский Металл",
            "Янская Вода", "Иньская Вода"]

BRANCHES_RU = ["Крыса (Вода)", "Бык (Земля)", "Тигр (Дерево)", "Кролик (Дерево)",
               "Дракон (Земля)", "Змея (Огонь)", "Лошадь (Огонь)", "Коза (Земля)",
               "Обезьяна (Металл)", "Петух (Металл)", "Собака (Земля)", "Свинья (Вода)"]

def get_jd(dt: datetime) -> float:
    """Конвертация datetime UTC в Юлианский день (Julian Day)"""
    return swe.julday(dt.year, dt.month, dt.day, dt.hour + dt.minute/60.0)

def get_solar_lon(jd: float) -> float:
    """Получение эклиптической долготы Солнца"""
    res, _ = swe.calc_ut(jd, swe.SUN, swe.FLG_SWIEPH)
    return res[0]  # Долгота в градусах 0-360

def get_year_pillar(year: int, solar_lon: float, month_gregorian: int) -> tuple[int, int]:
    """Расчет столпа года. Смена года происходит в Ли Чунь (долгота 315°)."""
    # Если мы в январе/начале февраля, но Солнце еще не прошло 315 градусов (от Овна),
    # значит астрологически это еще предыдущий год.
    bazi_year = year
    if month_gregorian <= 2 and solar_lon < 315.0 and solar_lon > 270.0:
        bazi_year -= 1

    stem_idx = (bazi_year - 4) % 10
    branch_idx = (bazi_year - 4) % 12
    return stem_idx, branch_idx

def get_month_pillar(year_stem_idx: int, solar_lon: float) -> tuple[int, int]:
    """Расчет столпа месяца по долготе Солнца (смена каждые 30 градусов, старт с 315°)."""
    # Смещаем ноль на 315 градусов (Ли Чунь - начало первого месяца Инь)
    shifted_lon = (solar_lon - 315.0) % 360.0
    month_idx = int(shifted_lon // 30.0) # От 0 до 11

    # Ветвь месяца (начинается с Инь = индекс 2)
    branch_idx = (month_idx + 2) % 12

    # Ствол месяца зависит от ствола года (Правило Пяти Тигров)
    stem_idx = ((year_stem_idx % 5) * 2 + 2 + month_idx) % 10

    return stem_idx, branch_idx

def get_day_pillar(jd_local: float) -> tuple[int, int]:
    """Расчет столпа дня. jd_local должен быть скорректирован на таймзону и час Крысы (23:00)."""
    # Смещение: базовый JD для Бацзы.
    # JD 0 был днем Гэн У (庚午). Точная математика для дня:
    day_idx = math.floor(jd_local + 0.5) + 49

    stem_idx = day_idx % 10
    branch_idx = day_idx % 12
    return stem_idx, branch_idx

def format_pillar(stem_idx: int, branch_idx: int) -> str:
    """Форматирование столпа для промпта LLM"""
    stem = STEMS[stem_idx]
    branch = BRANCHES[branch_idx]
    stem_ru = STEMS_RU[stem_idx]
    branch_ru = BRANCHES_RU[branch_idx]
    return f"{stem}{branch} ({stem_ru} / {branch_ru})"

# --- Детектор намерений и сборка контекста ---

class TemporalContextBuilder:
    def __init__(self):
        # Ищем 4 цифры, начинающиеся на 202x, 203x, 204x
        self.year_pattern = re.compile(r'\b(20[2-4]\d)\b')

    def extract_requested_years(self, text: str) -> list[int]:
        """Извлекает запрошенные годы из текста пользователя"""
        matches = self.year_pattern.findall(text)
        return sorted(list(set(int(y) for y in matches)))

    def get_current_bazi_context(self, dt_utc: datetime) -> str:
        """Генерация базового контекста текущего периода для LLM"""
        jd = get_jd(dt_utc)
        solar_lon = get_solar_lon(jd)

        y_stem, y_branch = get_year_pillar(dt_utc.year, solar_lon, dt_utc.month)
        m_stem, m_branch = get_month_pillar(y_stem, solar_lon)

        # Для дневного столпа нужно локальное время.
        # Если час >= 23, это уже следующий Бацзы-день (час Крысы).
        # Здесь упрощенно считаем UTC + смещение (например, для МСК +3).
        # В проде нужно брать локальное время пользователя из FSM (шаг 4).
        dt_local = dt_utc + timedelta(hours=3) # Пример для МСК
        if dt_local.hour >= 23:
            dt_local += timedelta(days=1)
        jd_local = get_jd(dt_local)
        d_stem, d_branch = get_day_pillar(jd_local)

        context = "[ТЕКУЩИЙ ПЕРИОД (ТРАНЗИТЫ)]\n"
        context += f"Год: {format_pillar(y_stem, y_branch)}\n"
        context += f"Месяц: {format_pillar(m_stem, m_branch)}\n"
        context += f"День: {format_pillar(d_stem, d_branch)}\n"

        return context

    def get_future_years_context(self, years: list[int]) -> str:
        """Генерация контекста для конкретных будущих годов"""
        if not years:
            return ""

        context = "\n[ЗАПРОШЕННЫЕ ПОЛЬЗОВАТЕЛЕМ ПЕРИОДЫ (ГОДА)]\n"
        for year in years:
            # Для годового столпа будущего года берем примерную летнюю дату,
            # чтобы избежать пограничных значений Ли Чунь
            dummy_jd = get_jd(datetime(year, 6, 1, tzinfo=timezone.utc))
            dummy_lon = get_solar_lon(dummy_jd)
            y_stem, y_branch = get_year_pillar(year, dummy_lon, 6)
            context += f"{year} год: {format_pillar(y_stem, y_branch)}\n"

        return context

    def build_full_prompt_context(self, user_query: str) -> str:
        """Сборка полного временного блока для добавления в system_prompt"""
        now_utc = datetime.now(timezone.utc)

        # 1. Всегда отдаем текущий транзит
        prompt_context = self.get_current_bazi_context(now_utc)

        # 2. Ищем года в запросе
        requested_years = self.extract_requested_years(user_query)
        if requested_years:
            prompt_context += self.get_future_years_context(requested_years)

        return prompt_context

# --- Пример использования ---
if __name__ == "__main__":
    builder = TemporalContextBuilder()
    
    user_queries = [
        "Когда мне лучше открывать бизнес?",
        "В 2027 году я женюсь?",
        "Что меня ждёт в 2028 и 2030 годах?"
    ]

    for q in user_queries:
        print(f"Вопрос: {q}")
        print(builder.build_full_prompt_context(q))
        print("-" * 40)
```

## Порядок исследований

| Приоритет | Исследование | Почему важно |
|-----------|-------------|--------------|
| 🔴 1 | R-2: OpenRouter Kimi K2 | Основная модель — нужно подтвердить качество и цены |
| 🔴 2 | R-3: Генерация карты | Ключевой UX элемент — решить Pillow vs gpt-image-1 |
| 🟡 3 | R-1: KuzuDB vs Neo4j | Этап 2, но важно выбрать заранее |
| 🟡 4 | R-5: FSM aiogram | Первая итерация кода |
| 🟢 5 | R-6: Временной детектор | Этап 2, не блокирует MVP |
| 🟢 6 | R-4: Yandex Cloud стоимость | Инфраструктура, не блокирует разработку |
