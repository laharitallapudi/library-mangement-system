from datetime import date, timedelta
from pathlib import Path
import sqlite3

DATABASE = Path(__file__).with_name("library.db")


def get_connection():
    """Open the SQLite database and return rows that work like dictionaries."""
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database():
    """Create the tables and add a small set of records on the first run."""
    with get_connection() as connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                isbn TEXT,
                category TEXT,
                publication_year INTEGER,
                available INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                status TEXT NOT NULL DEFAULT 'Active',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS loans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE RESTRICT,
                member_id INTEGER NOT NULL REFERENCES members(id) ON DELETE RESTRICT,
                checkout_date TEXT NOT NULL,
                due_date TEXT NOT NULL,
                return_date TEXT,
                status TEXT NOT NULL DEFAULT 'Active'
            );
        """)
        if connection.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 0:
            books = [
                ("The Alchemist", "Paulo Coelho", "9780061122415", "Fiction", 1988, 1),
                ("Python Crash Course", "Eric Matthes", "9781718502703", "Programming", 2019, 0),
                ("Atomic Habits", "James Clear", "9780735211292", "Self-help", 2018, 1),
                ("Wings of Fire", "A. P. J. Abdul Kalam", "9788173711466", "Biography", 1999, 0),
                ("The Hobbit", "J. R. R. Tolkien", "9780547928227", "Fantasy", 1937, 1),
            ]
            connection.executemany(
                "INSERT INTO books (title, author, isbn, category, publication_year, available) VALUES (?, ?, ?, ?, ?, ?)", books
            )
            members = [
                ("Asha Patel", "asha@example.com", "", "Active"),
                ("Rahul Sharma", "rahul@example.com", "", "Active"),
                ("Maya Singh", "maya@example.com", "", "Active"),
            ]
            connection.executemany(
                "INSERT INTO members (name, email, phone, status) VALUES (?, ?, ?, ?)", members
            )
            today = date.today()
            connection.executemany(
                "INSERT INTO loans (book_id, member_id, checkout_date, due_date, status) VALUES (?, ?, ?, ?, 'Active')",
                [
                    (2, 1, today.isoformat(), (today + timedelta(days=7)).isoformat()),
                    (4, 2, today.isoformat(), (today - timedelta(days=3)).isoformat()),
                ],
            )


if __name__ == "__main__":
    initialize_database()
    print(f"Database ready: {DATABASE}")
