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
                is_public INTEGER DEFAULT 1,
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
                is_public INTEGER DEFAULT 1,
                last_synced TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        ''')

        # Migrate existing data: add is_public column if it doesn't exist
        try:
            cursor.execute('SELECT is_public FROM bookmarks LIMIT 1')
        except:
            cursor.execute('ALTER TABLE bookmarks ADD COLUMN is_public INTEGER DEFAULT 1')
            cursor.execute('UPDATE bookmarks SET is_public = 1 WHERE is_public IS NULL')

        try:
            cursor.execute('SELECT is_public FROM repositories LIMIT 1')
        except:
            cursor.execute('ALTER TABLE repositories ADD COLUMN is_public INTEGER DEFAULT 1')
            cursor.execute('UPDATE repositories SET is_public = 1 WHERE is_public IS NULL')

        # Create indexes for better performance (after columns exist)
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_bookmarks_user_id ON bookmarks(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_repositories_user_id ON repositories(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_bookmarks_is_public ON bookmarks(is_public)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_repositories_is_public ON repositories(is_public)')


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

def create_bookmark(user_id: int, url: str, description: str, tags: List[str], category: str, source: Optional[str] = None, is_public: bool = True) -> int:
    """Create a new bookmark for a user"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        tags_json = json.dumps(tags)
        cursor.execute(
            'INSERT INTO bookmarks (user_id, url, description, tags, category, source, is_public) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (user_id, url, description, tags_json, category, source, 1 if is_public else 0)
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

def create_repository(user_id: int, name: str, url: str, is_public: bool = True) -> int:
    """Create a new repository"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO repositories (user_id, name, url, is_public) VALUES (?, ?, ?, ?)',
            (user_id, name, url, 1 if is_public else 0)
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


# ============================================
# PUBLIC SEARCH OPERATIONS
# ============================================

def search_public_bookmarks(keyword: Optional[str] = None) -> List[Dict[str, Any]]:
    """Search all public bookmarks across all users"""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        if keyword:
            # Search in URL, description, tags, and category for public bookmarks only
            query = '''
                SELECT b.*, u.username
                FROM bookmarks b
                JOIN users u ON b.user_id = u.id
                WHERE b.is_public = 1 AND (
                    b.url LIKE ? OR
                    b.description LIKE ? OR
                    b.tags LIKE ? OR
                    b.category LIKE ?
                )
                ORDER BY b.created_at DESC
            '''
            search_term = f'%{keyword}%'
            cursor.execute(query, (search_term, search_term, search_term, search_term))
        else:
            cursor.execute('''
                SELECT b.*, u.username
                FROM bookmarks b
                JOIN users u ON b.user_id = u.id
                WHERE b.is_public = 1
                ORDER BY b.created_at DESC
            ''')

        rows = cursor.fetchall()

        bookmarks = []
        for row in rows:
            bookmark = dict(row)
            bookmark['tags'] = json.loads(bookmark['tags']) if bookmark['tags'] else []
            bookmarks.append(bookmark)

        return bookmarks


def get_user_public_bookmarks(user_id: int) -> List[Dict[str, Any]]:
    """Get all public bookmarks for a specific user"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM bookmarks
            WHERE user_id = ? AND is_public = 1
            ORDER BY created_at DESC
        ''', (user_id,))
        rows = cursor.fetchall()

        bookmarks = []
        for row in rows:
            bookmark = dict(row)
            bookmark['tags'] = json.loads(bookmark['tags']) if bookmark['tags'] else []
            bookmarks.append(bookmark)

        return bookmarks


def get_user_public_repositories(user_id: int) -> List[Dict[str, Any]]:
    """Get all public repositories for a specific user"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM repositories
            WHERE user_id = ? AND is_public = 1
            ORDER BY created_at DESC
        ''', (user_id,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_public_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """Get public user information by username (no password hash)"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, created_at FROM users WHERE username = ?', (username,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_users_with_public_content() -> List[Dict[str, Any]]:
    """Get all users who have public bookmarks or repositories"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT DISTINCT u.id, u.username, u.created_at
            FROM users u
            WHERE EXISTS (
                SELECT 1 FROM bookmarks b WHERE b.user_id = u.id AND b.is_public = 1
            ) OR EXISTS (
                SELECT 1 FROM repositories r WHERE r.user_id = u.id AND r.is_public = 1
            )
            ORDER BY u.username
        ''')
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
