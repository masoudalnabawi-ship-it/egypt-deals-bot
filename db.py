import sqlite3
import hashlib
import json
from dataclasses import asdict
from contextlib import closing
from models import Deal

DB_PATH = "deals.db"

SCHEMA = '''
CREATE TABLE IF NOT EXISTS products (
    fingerprint TEXT PRIMARY KEY, store TEXT NOT NULL, title TEXT NOT NULL,
    url TEXT NOT NULL, first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
    last_seen TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT, fingerprint TEXT NOT NULL,
    current_price REAL NOT NULL, old_price REAL, discount_percent REAL NOT NULL,
    seen_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS posted_deals (
    fingerprint TEXT PRIMARY KEY, price REAL NOT NULL,
    discount_percent REAL NOT NULL, posted_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS pending_deals (
    fingerprint TEXT PRIMARY KEY, payload TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending', admin_message_id INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS market_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT, product_key TEXT NOT NULL,
    store TEXT NOT NULL, title TEXT NOT NULL, current_price REAL NOT NULL,
    old_price REAL, url TEXT NOT NULL, seen_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_market_product_key
ON market_observations(product_key, seen_at);
'''

def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with closing(connect()) as con:
        con.executescript(SCHEMA)
        con.commit()

def fingerprint(deal: Deal) -> str:
    raw = f"{deal.store}|{deal.external_id or deal.url}|{deal.title}".lower().strip()
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def save_seen(deal: Deal) -> str:
    fp = fingerprint(deal)
    with closing(connect()) as con:
        con.execute(
            '''INSERT INTO products(fingerprint,store,title,url) VALUES(?,?,?,?)
               ON CONFLICT(fingerprint) DO UPDATE SET title=excluded.title,
               url=excluded.url,last_seen=CURRENT_TIMESTAMP''',
            (fp, deal.store, deal.title, deal.url),
        )
        con.execute(
            '''INSERT INTO price_history(fingerprint,current_price,old_price,discount_percent)
               VALUES(?,?,?,?)''',
            (fp, deal.current_price, deal.old_price, deal.discount_percent),
        )
        con.commit()
    return fp

def save_market_observation(product_key: str, deal: Deal):
    with closing(connect()) as con:
        row = con.execute(
            '''SELECT current_price FROM market_observations
               WHERE product_key=? AND store=? AND url=?
               AND seen_at >= datetime('now','-1 hour')
               ORDER BY seen_at DESC LIMIT 1''',
            (product_key, deal.store, deal.url),
        ).fetchone()
        if row is not None and float(row["current_price"]) == float(deal.current_price):
            return
        con.execute(
            '''INSERT INTO market_observations
               (product_key,store,title,current_price,old_price,url)
               VALUES(?,?,?,?,?,?)''',
            (product_key, deal.store, deal.title, deal.current_price, deal.old_price, deal.url),
        )
        con.commit()

def history_stats_for_key(product_key: str):
    with closing(connect()) as con:
        row = con.execute(
            '''SELECT COUNT(*) c, MIN(current_price) mn, AVG(current_price) av
               FROM market_observations WHERE product_key=?''',
            (product_key,),
        ).fetchone()
    return {
        "count": int(row["c"] or 0),
        "min_price": float(row["mn"]) if row["mn"] is not None else None,
        "avg_price": float(row["av"]) if row["av"] is not None else None,
    }

def should_post(fp: str, deal: Deal) -> bool:
    with closing(connect()) as con:
        row = con.execute("SELECT price,discount_percent FROM posted_deals WHERE fingerprint=?", (fp,)).fetchone()
    if row is None:
        return True
    return deal.current_price < float(row["price"]) or deal.discount_percent >= float(row["discount_percent"]) + 5

def should_review(fp: str, deal: Deal) -> bool:
    if not should_post(fp, deal):
        return False
    with closing(connect()) as con:
        row = con.execute("SELECT payload,status FROM pending_deals WHERE fingerprint=?", (fp,)).fetchone()
    if row is None:
        return True
    if row["status"] == "pending":
        return False
    try:
        old = json.loads(row["payload"])
        old_price = float(old.get("current_price") or 0)
        old_discount = float(old.get("discount_percent") or 0)
    except Exception:
        return True
    if row["status"] == "rejected":
        return (old_price > 0 and deal.current_price < old_price) or deal.discount_percent >= old_discount + 5
    return True

def save_pending(fp: str, deal: Deal, admin_message_id=None):
    payload = asdict(deal)
    payload["discount_percent"] = deal.discount_percent
    with closing(connect()) as con:
        con.execute(
            '''INSERT INTO pending_deals(fingerprint,payload,status,admin_message_id)
               VALUES(?,?,'pending',?)
               ON CONFLICT(fingerprint) DO UPDATE SET payload=excluded.payload,
               status='pending',admin_message_id=excluded.admin_message_id,
               updated_at=CURRENT_TIMESTAMP''',
            (fp, json.dumps(payload, ensure_ascii=False), admin_message_id),
        )
        con.commit()

def set_admin_message_id(fp, message_id):
    with closing(connect()) as con:
        con.execute("UPDATE pending_deals SET admin_message_id=?,updated_at=CURRENT_TIMESTAMP WHERE fingerprint=?", (message_id, fp))
        con.commit()

def get_pending_by_short(short_fp):
    with closing(connect()) as con:
        row = con.execute(
            "SELECT * FROM pending_deals WHERE fingerprint LIKE ? ORDER BY updated_at DESC LIMIT 1",
            (short_fp + "%",),
        ).fetchone()
    return dict(row) if row else None

def set_pending_status(fp, status):
    with closing(connect()) as con:
        con.execute("UPDATE pending_deals SET status=?,updated_at=CURRENT_TIMESTAMP WHERE fingerprint=?", (status, fp))
        con.commit()

def mark_posted(fp, deal):
    with closing(connect()) as con:
        con.execute(
            '''INSERT INTO posted_deals(fingerprint,price,discount_percent) VALUES(?,?,?)
               ON CONFLICT(fingerprint) DO UPDATE SET price=excluded.price,
               discount_percent=excluded.discount_percent,posted_at=CURRENT_TIMESTAMP''',
            (fp, deal.current_price, deal.discount_percent),
        )
        con.commit()

def historical_low(fp):
    with closing(connect()) as con:
        row = con.execute("SELECT MIN(current_price) p FROM price_history WHERE fingerprint=?", (fp,)).fetchone()
    return float(row["p"]) if row and row["p"] is not None else None
