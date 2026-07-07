# Деплой БаЦзы-Бот на Yandex Cloud

> Это ручные шаги, которые разработчик выполняет **один раз** при настройке инфраструктуры.
> После этого деплой происходит автоматически через GitHub Actions.

---

## Шаг 0: Регистрация в Yandex Cloud (сделай это первым)

### 0.1 Создать аккаунт

1. Перейди на [console.yandex.cloud](https://console.yandex.cloud)
2. Нажми «Войти» → залогинься через Яндекс ID (или создай новый)
3. При первом входе нажми «Создать платёжный аккаунт»
4. Выбери тип: **Физическое лицо** (для старта)
5. Привяжи карту (даже если ты используешь грант — карта нужна для верификации)
6. Получишь **4000 ₽ стартового гранта** автоматически

> Если у тебя уже есть грант (200 000 ₽ от партнёрской программы) — его активируют в разделе «Биллинг → Гранты». Код гранта даётся отдельно.

### 0.2 Создать каталог (folder)

В консоли: **Главная → Все сервисы → Создать каталог**
- Имя: `badzi-bot`
- Описание: `BaZi bot production`

Запомни **Folder ID** (вида `b1g...`) — он нужен в yc CLI командах.

---

## Предварительные требования (локально)

- Аккаунт Yandex Cloud с активированным биллингом (см. Шаг 0)
- Установлен `yc` CLI (см. Шаг 1 ниже)
- Установлен Docker, docker-compose
- Репозиторий склонирован локально

---

## Шаг 1: Установка и настройка yc CLI

```bash
# Установить yc CLI (macOS/Linux)
curl -sSL https://storage.yandexcloud.net/yandexcloud-yc/install.sh | bash

# Перезапустить терминал, затем:
yc --version  # проверить установку

# Инициализация — откроется браузер для авторизации
yc init
# В процессе:
# 1. Войди через браузер (откроется автоматически)
# 2. Выбери облако (cloud)
# 3. Выбери каталог badzi-bot (который создал в шаге 0)
# 4. Выбери зону: ru-central1-a

# Проверить текущий конфиг
yc config list
# Должно показать: cloud-id, folder-id, compute-default-zone

# Запомни folder-id — он нужен во всех командах
yc config get folder-id
```

---

## Шаг 2: Yandex Container Registry (для Docker образов)

```bash
# Создать реестр
yc container registry create --name badzi-registry

# Авторизовать Docker
yc container registry configure-docker

# Запомни registry ID (вида crp...) для GitHub Actions secrets
yc container registry list
```

---

## Шаг 3: Yandex Managed PostgreSQL

```bash
# Создать кластер (2 vCPU, 8 GB RAM, SSD 20 GB)
yc managed-postgresql cluster create \
  --name badzi-postgres \
  --environment production \
  --network-name default \
  --resource-preset s2.micro \
  --disk-size 20 \
  --disk-type network-ssd \
  --host zone-id=ru-central1-a,subnet-name=default-ru-central1-a

# Создать базу данных
yc managed-postgresql database create \
  --cluster-name badzi-postgres \
  --name badzi

# Создать пользователя
yc managed-postgresql user create \
  --cluster-name badzi-postgres \
  --name badzi_user \
  --password YOUR_SECURE_PASSWORD

# Получить FQDN хоста для DATABASE_URL
yc managed-postgresql host list --cluster-name badzi-postgres
# DATABASE_URL = postgresql+asyncpg://badzi_user:PASSWORD@FQDN:5432/badzi
```

---

## Шаг 4: Yandex Managed Redis

```bash
# Создать кластер Redis
yc managed-redis cluster create \
  --name badzi-redis \
  --environment production \
  --network-name default \
  --resource-preset hm1.nano \
  --disk-size 8 \
  --disk-type network-ssd \
  --host zone-id=ru-central1-a,subnet-name=default-ru-central1-a

# Получить FQDN для REDIS_URL
yc managed-redis host list --cluster-name badzi-redis
# REDIS_URL = redis://FQDN:6379/0
```

---

## Шаг 5: Yandex Object Storage

```bash
# Создать bucket для PNG карт и CSV экспорта
yc storage bucket create --name badzi-bot-assets

# Создать сервисный аккаунт
yc iam service-account create --name badzi-storage-sa

# Выдать права на bucket
yc storage bucket update \
  --name badzi-bot-assets \
  --acl public-read

# Создать ключ доступа
yc iam access-key create --service-account-name badzi-storage-sa
# Сохрани key_id → YC_ACCESS_KEY_ID
# Сохрани secret     → YC_SECRET_ACCESS_KEY
```

---

## Шаг 6: Yandex Compute Cloud (VPS)

```bash
# Создать VМ (Ubuntu 22.04, 2 vCPU, 4 GB RAM)
yc compute instance create \
  --name badzi-bot-vm \
  --zone ru-central1-a \
  --platform standard-v3 \
  --cores 2 \
  --memory 4 \
  --network-interface subnet-name=default-ru-central1-a,nat-ip-version=ipv4 \
  --create-boot-disk image-folder-id=standard-images,image-family=ubuntu-2204-lts,size=20 \
  --ssh-key ~/.ssh/id_rsa.pub

# Получить внешний IP
yc compute instance get badzi-bot-vm | grep nat_ip_address
```

---

## Шаг 7: Настройка VPS

```bash
# SSH на сервер
ssh ubuntu@YOUR_EXTERNAL_IP

# Установка Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker ubuntu
# Перелогиниться

# Клонировать репозиторий
git clone https://github.com/YOUR_REPO/BaDzi_bot.git
cd BaDzi_bot

# Создать .env из примера
cp .env.example .env
nano .env  # заполнить все значения

# Скачать Swiss Ephemeris данные
sudo mkdir -p /usr/share/swisseph
# Загрузить se1-ephe.zip из http://www.astro.com/swisseph/
# sudo unzip se1-ephe.zip -d /usr/share/swisseph/
```

---

## Шаг 8: SSL и домен для Telegram Webhook

```bash
# Yandex Certificate Manager (Let's Encrypt)
yc certificate-manager certificate request \
  --name badzi-ssl \
  --domains badzi-bot.your-domain.ru \
  --challenge dns

# Настроить A-запись DNS: badzi-bot.your-domain.ru → YOUR_EXTERNAL_IP

# Nginx как reverse proxy (на VPS)
sudo apt install nginx certbot python3-certbot-nginx -y
sudo certbot --nginx -d badzi-bot.your-domain.ru
```

---

## Шаг 9: Первый запуск и миграции

```bash
# Собрать образ
docker-compose build

# Запустить БД
docker-compose up -d db redis

# Применить миграции Alembic
docker-compose run --rm bot alembic upgrade head

# Запустить все сервисы
docker-compose up -d

# Проверить логи
docker-compose logs -f bot
```

---

## Шаг 10: Настройка Telegram Webhook

```bash
# Установить webhook (заменить BOT_TOKEN и URL)
curl "https://api.telegram.org/bot$BOT_TOKEN/setWebhook?url=https://badzi-bot.your-domain.ru/webhook"

# Проверить
curl "https://api.telegram.org/bot$BOT_TOKEN/getWebhookInfo"
```

---

## Шаг 11: GitHub Actions Secrets

В настройках репозитория GitHub → Settings → Secrets добавить:

| Secret | Значение |
|--------|----------|
| `YC_REGISTRY_ID` | ID Container Registry из шага 2 |
| `YC_SA_JSON_CREDENTIALS` | Ключ сервисного аккаунта (JSON) |
| `SSH_PRIVATE_KEY` | Приватный SSH ключ для деплоя |
| `SERVER_IP` | Внешний IP сервера |
| `BOT_TOKEN` | Токен Telegram бота |

После этого каждый push в `main` → автоматический деплой через GitHub Actions.

---

## Быстрые команды для обслуживания

```bash
# Перезапустить бота
docker-compose restart bot

# Смотреть логи в реальном времени
docker-compose logs -f bot worker

# Применить новые миграции после деплоя
docker-compose run --rm bot alembic upgrade head

# Сменить модель LLM без деплоя (через Redis)
docker-compose exec redis redis-cli SET llm:active_model "anthropic/claude-3.5-sonnet"

# Выгрузить диалоги (из Telegram команды /admin export)
# или напрямую:
docker-compose exec db psql -U badzi -c "COPY (SELECT * FROM consultations) TO STDOUT CSV HEADER;" > export.csv

# Бэкап PostgreSQL
docker-compose exec db pg_dump -U badzi badzi > backup_$(date +%Y%m%d).sql
```
