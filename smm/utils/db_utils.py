import sqlite3

def init_gazeta_db(path):
    conn = sqlite3.connect(path)
    cursor = conn.cursor()

    cursor.execute("DROP TABLE IF EXISTS articles")
    cursor.execute("DROP TABLE IF EXISTS comments")

    cursor.execute("""
    CREATE TABLE articles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT UNIQUE,
        title TEXT,
        content TEXT
    )
    """)
    cursor.execute("""
    CREATE TABLE comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        article_id INTEGER,
        user TEXT,
        comment TEXT,
        upvotes INTEGER,
        downvotes INTEGER,
        FOREIGN KEY(article_id) REFERENCES articles(id)
    )
    """)
    conn.commit()
    conn.close()


def init_upl_db(path):
    init_gazeta_db(path)  # same structure


def init_podrobno_db(path):
    conn = sqlite3.connect(path)
    cursor = conn.cursor()

    cursor.execute("DROP TABLE IF EXISTS articles")
    cursor.execute("DROP TABLE IF EXISTS comments")
    cursor.execute("DROP TABLE IF EXISTS emotions")

    cursor.execute("""
    CREATE TABLE articles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        url TEXT UNIQUE,
        title TEXT,
        content TEXT
    )
    """)
    cursor.execute("""
    CREATE TABLE comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        article_id INTEGER,
        comment TEXT,
        FOREIGN KEY(article_id) REFERENCES articles(id)
    )
    """)
    cursor.execute("""
    CREATE TABLE emotions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        article_id INTEGER,
        emotion TEXT,
        count INTEGER,
        FOREIGN KEY(article_id) REFERENCES articles(id)
    )
    """)
    conn.commit()
    conn.close()
