# Fuel Accounting System. Лабораторна робота 2

Вебзастосунок для предметної галузі ІС «Облік пально-мастильних матеріалів».
Проєкт скопійовано з `lab1`, але база даних перенесена з SQLite на PostgreSQL.

## Що є в роботі

- 4 основні сутності: `User`, `FuelType`, `FuelItem`, `IssueRecord`
- основний CRUD для `FuelItem`
- HTML-інтерфейс через Jinja2
- JSON API через FastAPI
- PostgreSQL як основна база даних
- окрема сторінка `/postgres` з прямими запитами через `psycopg`
- приклади `CREATE DATABASE`, `CREATE TABLE`, `INSERT`, `SELECT`, `UPDATE`, `DELETE`

## Налаштування PostgreSQL

Параметри підключення лежать у файлі `.env`:

```text
POSTGRES_DB=fuel_accounting
POSTGRES_USER=postgres
POSTGRES_PASSWORD=masterkey
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
```

Якщо пароль інший, відкрий `.env` і заміни значення `POSTGRES_PASSWORD`.
Приклад формату є у файлі `.env.example`.

## Запуск

```bash
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Після запуску:

- головна сторінка: `http://127.0.0.1:8000/`
- PostgreSQL-перевірка: `http://127.0.0.1:8000/postgres`
- Swagger UI: `http://127.0.0.1:8000/docs/fuel`

## Демо-акаунти

- адміністратор: `admin / admin123`
- користувач: `operator / user123`
