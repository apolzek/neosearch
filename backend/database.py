import sqlite3
import json
import os
from datetime import datetime
from typing import List, Optional, Dict, Any
from contextlib import contextmanager


DATABASE_PATH = os.getenv("DATABASE_PATH", "/app/database/neosearch.db")


@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database():
    """Initialize database with all tables"""
    # Ensure database directory exists
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Bookmarks table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bookmarks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                url TEXT NOT NULL,
                description TEXT NOT NULL,
                tags TEXT,
                category TEXT,
                source TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        ''')

        # Repositories table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS repositories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                last_synced TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        ''')

        # Create indexes for better performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_bookmarks_user_id ON bookmarks(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_repositories_user_id ON repositories(user_id)')


# ============================================
# USER OPERATIONS
# ============================================

def create_user(username: str, password_hash: str) -> int:
    """Create a new user"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO users (username, password_hash) VALUES (?, ?)',
            (username, password_hash)
        )
        return cursor.lastrowid


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """Get user by username"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Get user by ID"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, created_at FROM users WHERE id = ?', (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


# ============================================
# BOOKMARK OPERATIONS
# ============================================

def create_bookmark(user_id: int, url: str, description: str, tags: List[str], category: str, source: Optional[str] = None) -> int:
    """Create a new bookmark for a user"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        tags_json = json.dumps(tags)
        cursor.execute(
            'INSERT INTO bookmarks (user_id, url, description, tags, category, source) VALUES (?, ?, ?, ?, ?, ?)',
            (user_id, url, description, tags_json, category, source)
        )
        return cursor.lastrowid


def get_user_bookmarks(user_id: int) -> List[Dict[str, Any]]:
    """Get all bookmarks for a user"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM bookmarks WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
        rows = cursor.fetchall()

        bookmarks = []
        for row in rows:
            bookmark = dict(row)
            bookmark['tags'] = json.loads(bookmark['tags']) if bookmark['tags'] else []
            bookmarks.append(bookmark)

        return bookmarks


def search_user_bookmarks(user_id: int, keyword: Optional[str] = None) -> List[Dict[str, Any]]:
    """Search bookmarks for a user"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        if keyword:
            # Search in URL, description, tags, and category
            query = '''
                SELECT * FROM bookmarks
                WHERE user_id = ? AND (
                    url LIKE ? OR
                    description LIKE ? OR
                    tags LIKE ? OR
                    category LIKE ?
                )
                ORDER BY created_at DESC
            '''
            search_term = f'%{keyword}%'
            cursor.execute(query, (user_id, search_term, search_term, search_term, search_term))
        else:
            cursor.execute('SELECT * FROM bookmarks WHERE user_id = ? ORDER BY created_at DESC', (user_id,))

        rows = cursor.fetchall()

        bookmarks = []
        for row in rows:
            bookmark = dict(row)
            bookmark['tags'] = json.loads(bookmark['tags']) if bookmark['tags'] else []
            bookmarks.append(bookmark)

        return bookmarks


def get_bookmark_by_id(bookmark_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    """Get a specific bookmark if it belongs to the user"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM bookmarks WHERE id = ? AND user_id = ?', (bookmark_id, user_id))
        row = cursor.fetchone()

        if row:
            bookmark = dict(row)
            bookmark['tags'] = json.loads(bookmark['tags']) if bookmark['tags'] else []
            return bookmark
        return None


def delete_bookmark(bookmark_id: int, user_id: int) -> bool:
    """Delete a bookmark if it belongs to the user"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM bookmarks WHERE id = ? AND user_id = ?', (bookmark_id, user_id))
        return cursor.rowcount > 0


def delete_bookmarks_by_source(user_id: int, source: str):
    """Delete all bookmarks from a specific source"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM bookmarks WHERE user_id = ? AND source = ?', (user_id, source))


# ============================================
# REPOSITORY OPERATIONS
# ============================================

def create_repository(user_id: int, name: str, url: str) -> int:
    """Create a new repository"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO repositories (user_id, name, url) VALUES (?, ?, ?)',
            (user_id, name, url)
        )
        return cursor.lastrowid


def get_user_repositories(user_id: int) -> List[Dict[str, Any]]:
    """Get all repositories for a user"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM repositories WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_repository_by_id(repository_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    """Get a specific repository if it belongs to the user"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM repositories WHERE id = ? AND user_id = ?', (repository_id, user_id))
        row = cursor.fetchone()
        return dict(row) if row else None


def update_repository_sync_time(repository_id: int):
    """Update the last synced timestamp for a repository"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE repositories SET last_synced = CURRENT_TIMESTAMP WHERE id = ?',
            (repository_id,)
        )


def delete_repository(repository_id: int, user_id: int) -> bool:
    """Delete a repository if it belongs to the user"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # First, get the repository name to use as source
        cursor.execute('SELECT name FROM repositories WHERE id = ? AND user_id = ?', (repository_id, user_id))
        row = cursor.fetchone()

        if row:
            repo_name = row['name']
            # Delete all bookmarks from this repository
            delete_bookmarks_by_source(user_id, repo_name)
            # Delete the repository
            cursor.execute('DELETE FROM repositories WHERE id = ? AND user_id = ?', (repository_id, user_id))
            return cursor.rowcount > 0

        return False
