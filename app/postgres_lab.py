from __future__ import annotations

import psycopg

from app.database import (
    POSTGRES_DB,
    POSTGRES_HOST,
    POSTGRES_PASSWORD,
    POSTGRES_PORT,
    POSTGRES_USER,
)


def get_connection(dbname: str | None = None):
    return psycopg.connect(
        dbname=dbname or POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
    )


def create_database_if_not_exists() -> None:
    conn = get_connection("postgres")
    conn.autocommit = True
    cursor = conn.cursor()

    cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (POSTGRES_DB,))
    exists = cursor.fetchone()

    if not exists:
        cursor.execute(f'CREATE DATABASE "{POSTGRES_DB}"')

    cursor.close()
    conn.close()


def create_demo_table() -> None:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS postgres_notes (
            id SERIAL PRIMARY KEY,
            text VARCHAR(200) NOT NULL,
            is_done BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
        """
    )

    conn.commit()
    cursor.close()
    conn.close()


def get_postgres_info() -> dict:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT current_database(), current_user, version()")
    database_name, user_name, version = cursor.fetchone()

    cursor.execute("SELECT COUNT(*) FROM fuel_items")
    fuel_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM issue_records")
    issue_count = cursor.fetchone()[0]

    cursor.close()
    conn.close()

    return {
        "database_name": database_name,
        "user_name": user_name,
        "version": version,
        "fuel_count": fuel_count,
        "issue_count": issue_count,
    }


def get_recent_fuels() -> list[dict]:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT fuel_items.id, fuel_items.name, fuel_types.name, fuel_items.quantity_liters
        FROM fuel_items
        JOIN fuel_types ON fuel_types.id = fuel_items.fuel_type_id
        ORDER BY fuel_items.id DESC
        """
    )
    rows = cursor.fetchmany(5)

    cursor.close()
    conn.close()

    fuels = []
    for row in rows:
        fuels.append(
            {
                "id": row[0],
                "name": row[1],
                "fuel_type": row[2],
                "quantity_liters": row[3],
            }
        )
    return fuels


def get_notes() -> list[dict]:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, text, is_done, created_at
        FROM postgres_notes
        ORDER BY id DESC
        """
    )
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    notes = []
    for row in rows:
        notes.append(
            {
                "id": row[0],
                "text": row[1],
                "is_done": row[2],
                "created_at": row[3],
            }
        )
    return notes


def add_note(text: str) -> None:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("INSERT INTO postgres_notes (text) VALUES (%s)", (text,))

    conn.commit()
    cursor.close()
    conn.close()


def mark_note_done(note_id: int) -> None:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("UPDATE postgres_notes SET is_done = TRUE WHERE id = %s", (note_id,))

    conn.commit()
    cursor.close()
    conn.close()


def delete_note(note_id: int) -> None:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM postgres_notes WHERE id = %s", (note_id,))

    conn.commit()
    cursor.close()
    conn.close()
