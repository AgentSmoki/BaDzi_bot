# Мастер Шифу — анимированные стикеры (живой стикер, прозрачный фон)

Цель — **живой стикер**, а не видео-вставка: картинка стоит на месте,
двигается только **один-два мелких элемента** (дым вьётся, борода
качнулась, моргнул, блик по монете). Плюс **прозрачный фон**, чтобы
стикер сливался с чатом Telegram.

## Как это работает (проверено по докам, 2026)

- **Nano Banana / Gemini прозрачность не отдаёт** (нет alpha, слово
  «transparent» даёт «шахматку»). Поэтому персонаж генерится на
  **сплошном зелёном хромакее**, а фон вырезается отдельно.
- **Veo умеет двигать только выбранные элементы, остальное — статично**
  (это и есть cinemagraph). Ключ — жёстко просить «всё замерло, кроме X».
- **Прозрачность видео** = анимировать на зелёном → выбить зелёный
  покадрово → кодировать в **VP9 webm с alpha**.

## Формат стикера Telegram (core.telegram.org)

WEBM · кодек **VP9** · без звука · сторона **512 px** · **≤3 сек** ·
до **30 fps** · **≤256 КБ** · **прозрачность поддерживается** · зациклено.

---

## Разделение труда

**Ты (Google Flow / Veo 3.1):**
1. Берёшь **зелёные исходники** `shifu_green_<поза>.png` (лежат рядом) —
   они уже на ровном хромакее, специально под вырезание фона.
2. В Flow используй **Frames**: поставь **один и тот же кадр** и в start,
   и в end → Veo сделает бесшовный луп с минимальным дрейфом.
3. Промпт — только про микро-движение (ниже). Длительность 2-3 сек.
4. **Не меняй зелёный фон** и не двигай камеру — фон должен остаться
   ровным зелёным, иначе не вырежется чисто.
5. Пришли мне 6 клипов (mp4).

**Я:** выбиваю зелёный покадрово (chroma-key), кодирую в VP9-webm с alpha
512×512 ≤256 КБ, собираю стикерпак через @Stickers/Bot API, вшиваю в бота.

---

## Промпты (микро-движение, «всё замерло, кроме…»)

Общая обвязка к каждому:
> Static locked shot, camera perfectly still. The illustration stays
> frozen; ONLY the elements below move, everything else does not move at
> all. Keep the flat solid green background completely unchanged and even.
> Seamless 3-second loop. No new objects, no camera move, no style change.

1. **greeting** — `shifu_green_greeting.png`
   > Only the thin smoke wisps drift and curl slowly, and the very tips of
   > the beard sway a little. He blinks once, softly. Hands, robe, halo — frozen.

2. **thinking** — `shifu_green_thinking.png`
   > Only the smoke drifts and the eyes slowly close halfway and open again
   > once (thoughtful). The stroking hand and everything else stay perfectly still.

3. **explaining** — `shifu_green_explaining.png`
   > Only the raised index finger does one tiny emphatic tick up and back;
   > the smoke drifts. Face, body, beads — frozen.

4. **coin** — `shifu_green_coin.png`
   > Only a small bright glint sweeps once across the golden coin, and the
   > smoke drifts. The hands, face and everything else stay perfectly still.

5. **meditating** — `shifu_green_meditating.png`
   > Only the smoke wisps rise and curl in a slow seamless loop, and the
   > chest rises and falls once, very subtly (calm breath). Eyes stay closed,
   > body frozen.

6. **thanks** — `shifu_green_thanks.png`
   > Only the smoke drifts and the beard tips sway slightly; a very small,
   > slow head dip and return. Hands in the bow stay frozen.

**Avoid (во всех):** big motion, camera movement, background change, new
objects, extra hands, face distortion, text, watermark, flicker.

> Если Veo всё равно двигает слишком много — уменьшай длительность (2 сек)
> и усиливай формулировку «everything else is completely frozen».
