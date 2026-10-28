
from contextvars import ContextVar
from pathlib import Path
import sqlite3

DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Central database: user accounts and login sessions.
DB_PATH = DATA_DIR / "pennywise.db"
USER_DATA_DIR = DATA_DIR / "users"
USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

_active_user_id: ContextVar[int | None] = ContextVar(
    "pennywise_active_user_id", default=None
)

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token_jti TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'Cash',
    opening_balance REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL CHECK(kind IN ('income','expense')),
    color TEXT NOT NULL DEFAULT '#62d6ad',
    icon TEXT NOT NULL DEFAULT 'circle'
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL CHECK(kind IN ('income','expense','transfer')),
    amount REAL NOT NULL CHECK(amount > 0),
    date TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    merchant TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    payment_method TEXT NOT NULL DEFAULT '',
    account_id INTEGER,
    to_account_id INTEGER,
    tags TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    goal_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE SET NULL,
    FOREIGN KEY(to_account_id) REFERENCES accounts(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS budgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    month TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'All expenses',
    amount REAL NOT NULL CHECK(amount > 0),
    recurring INTEGER NOT NULL DEFAULT 0,
    UNIQUE(month, category)
);

CREATE TABLE IF NOT EXISTS goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    target_amount REAL NOT NULL CHECK(target_amount > 0),
    saved_amount REAL NOT NULL DEFAULT 0 CHECK(saved_amount >= 0),
    target_date TEXT,
    priority TEXT NOT NULL DEFAULT 'Medium',
    icon TEXT NOT NULL DEFAULT '🎯',
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

DEFAULT_CATEGORIES = [
    ('Parents', 'income', '#6bd6b1', 'users'),
    ('Salary', 'income', '#6bd6b1', 'briefcase'),
    ('Freelance', 'income', '#6bd6b1', 'laptop'),
    ('Gifts', 'income', '#6bd6b1', 'gift'),
    ('Refunds', 'income', '#6bd6b1', 'rotate-ccw'),
    ('Other income', 'income', '#6bd6b1', 'plus'),
    ('Food & groceries', 'expense', '#f5b85c', 'utensils'),
    ('Cigarettes & smoking', 'expense', '#b8a0e8', 'cloud'),
    ('Alcohol & going out', 'expense', '#e99b9b', 'wine'),
    ('Football & sports', 'expense', '#72b8f2', 'trophy'),
    ('Clothes & fashion', 'expense', '#e8a4d0', 'shirt'),
    ('Home decor', 'expense', '#d5b28b', 'lamp'),
    ('Transport', 'expense', '#9ba9ba', 'car'),
    ('Entertainment', 'expense', '#a9a0f2', 'gamepad-2'),
    ('Subscriptions', 'expense', '#7ec8d7', 'repeat'),
    ('Education & college', 'expense', '#8acb9c', 'book-open'),
    ('Personal care', 'expense', '#e5b0a2', 'heart'),
    ('Health', 'expense', '#e5b0a2', 'activity'),
    ('Shopping', 'expense', '#e8a4d0', 'shopping-bag'),
    ('Gifts & social', 'expense', '#e9b67e', 'gift'),
    ('Bills', 'expense', '#a5b8cc', 'receipt'),
    ('Miscellaneous', 'expense', '#a5b8cc', 'circle-dots'),
]


def _connect_path(path: Path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def central_connect():
    """Use this only for users and login sessions."""
    return _connect_path(DB_PATH)


def _initialize_user_db(user_id: int):
    path = USER_DATA_DIR / f"user_{user_id}.db"

    with _connect_path(path) as conn:
        conn.executescript(SCHEMA)
        conn.executemany(
            """INSERT OR IGNORE INTO categories(name, kind, color, icon)
               VALUES (?, ?, ?, ?)""",
            DEFAULT_CATEGORIES,
        )
        conn.execute(
            """INSERT OR IGNORE INTO accounts(name, type, opening_balance)
               VALUES ('Cash', 'Cash', 0)"""
        )
        conn.execute(
            """INSERT OR IGNORE INTO accounts(name, type, opening_balance)
               VALUES ('Bank / UPI', 'Bank', 0)"""
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings(key, value) VALUES('currency', 'INR')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO settings(key, value) VALUES('theme', 'dark')"
        )


def set_active_user(user_id: int | None):
    return _active_user_id.set(user_id)


def reset_active_user(token):
    _active_user_id.reset(token)


def connect():
    """
    Financial queries use the authenticated user's database.
    Calls outside an authenticated request use the central database.
    """
    user_id = _active_user_id.get()

    if user_id is None:
        return central_connect()

    if user_id < 1:
        raise ValueError("Invalid user ID")

    path = USER_DATA_DIR / f"user_{user_id}.db"

    if not path.exists():
        _initialize_user_db(user_id)

    return _connect_path(path)


def init_db():
    """Initialize the central database without deleting existing records."""
    with central_connect() as conn:
        conn.executescript(SCHEMA)
