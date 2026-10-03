"""SQLite database: user accounts and each user's history."""
import hashlib
import hmac
import os
import sqlite3


def hash_password(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)


class Database:
    def __init__(self, path):
        self.con = sqlite3.connect(path)
        self.con.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY,
                username      TEXT UNIQUE NOT NULL,
                password_hash BLOB NOT NULL,
                salt          BLOB NOT NULL
            );
            CREATE TABLE IF NOT EXISTS history (
                id         INTEGER PRIMARY KEY,
                user_id    INTEGER NOT NULL REFERENCES users(id),
                path       TEXT NOT NULL,
                action     TEXT NOT NULL,
                encrypted  INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)

    def register(self, username, password):
        username = username.strip()
        if not username:
            raise ValueError("Username is required.")
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters.")
        salt = os.urandom(16)   # random salt: two users with the same password get different hashes
        try:
            with self.con:      # commits automatically
                self.con.execute("INSERT INTO users (username, password_hash, salt) VALUES (?, ?, ?)",
                                 (username, hash_password(password, salt), salt))
        except sqlite3.IntegrityError:   # UNIQUE username already exists
            raise ValueError("That username is already taken.")

    def login(self, username, password):
        """Return the user's id, or raise ValueError."""
        row = self.con.execute("SELECT id, password_hash, salt FROM users WHERE username = ?",
                               (username.strip(),)).fetchone()
        if row is None or not hmac.compare_digest(row[1], hash_password(password, row[2])):
            raise ValueError("Invalid username or password.")
        return row[0]

    def add_history(self, user_id, path, action, encrypted):
        with self.con:
            self.con.execute("INSERT INTO history (user_id, path, action, encrypted) VALUES (?, ?, ?, ?)",
                             (user_id, path, action, int(encrypted)))

    def get_history(self, user_id, search=""):
        """Rows of (date, action, encrypted, path), newest first, filtered by file path."""
        return self.con.execute(
            "SELECT datetime(created_at, 'localtime'), action, encrypted, path FROM history "
            "WHERE user_id = ? AND path LIKE ? ORDER BY id DESC",
            (user_id, f"%{search}%")).fetchall()
