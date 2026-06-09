import sqlite3
import hashlib
from datetime import datetime

DB_PATH = "auction.db"


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _hash(password):
    return hashlib.sha256(password.encode()).hexdigest()


def create_tables():
    conn = _connect()
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            username   TEXT UNIQUE NOT NULL,
            password   TEXT NOT NULL,
            email      TEXT,
            full_name  TEXT,
            role       TEXT NOT NULL DEFAULT 'buyer',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS categories (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT UNIQUE NOT NULL,
            description TEXT
        );

        CREATE TABLE IF NOT EXISTS products (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            seller_id     INTEGER NOT NULL REFERENCES users(id),
            category_name TEXT NOT NULL,
            title         TEXT NOT NULL,
            description   TEXT,
            image_url     TEXT,
            start_price   INTEGER NOT NULL,
            step_price    INTEGER NOT NULL,
            buy_now_price INTEGER,
            current_price INTEGER NOT NULL,
            status        TEXT NOT NULL DEFAULT 'pending',
            start_time    TEXT,
            end_time      TEXT,
            created_at    TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS bids (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL REFERENCES products(id),
            bidder_id  INTEGER NOT NULL REFERENCES users(id),
            amount     INTEGER NOT NULL,
            created_at TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()


def seed_data():
    conn = _connect()
    c = conn.cursor()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        c.execute(
            "INSERT INTO users (username, password, email, full_name, role, created_at) VALUES (?,?,?,?,?,?)",
            ("admin", _hash("admin123"), "admin@humg.edu.vn", "Quản trị viên", "admin", now)
        )
        c.execute(
            "INSERT INTO users (username, password, email, full_name, role, created_at) VALUES (?,?,?,?,?,?)",
            ("seller1", _hash("seller123"), "seller@humg.edu.vn", "Người bán Demo", "seller", now)
        )
        c.execute(
            "INSERT INTO users (username, password, email, full_name, role, created_at) VALUES (?,?,?,?,?,?)",
            ("buyer1", _hash("buyer123"), "buyer@humg.edu.vn", "Người mua Demo", "buyer", now)
        )

    c.execute("SELECT COUNT(*) FROM categories")
    if c.fetchone()[0] == 0:
        cats = [
            ("Điện tử",      "Thiết bị điện tử, công nghệ"),
            ("Thời trang",   "Quần áo, phụ kiện"),
            ("Đồ cổ",        "Đồ vật cổ, nghệ thuật"),
            ("Xe cộ",        "Ô tô, xe máy, phương tiện"),
            ("Bất động sản", "Nhà đất, căn hộ"),
        ]
        c.executemany(
            "INSERT INTO categories (name, description) VALUES (?,?)", cats
        )

    conn.commit()
    conn.close()


def login(username, password):
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM users WHERE username=? AND password=?",
        (username, _hash(password))
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def register(username, password, email, full_name, role):
    conn = _connect()
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO users (username, password, email, full_name, role, created_at) VALUES (?,?,?,?,?,?)",
            (username, _hash(password), email, full_name, role, now)
        )
        conn.commit()
        return True, "OK"
    except sqlite3.IntegrityError:
        return False, f"Tên đăng nhập '{username}' đã tồn tại."
    finally:
        conn.close()


def get_all_users():
    conn = _connect()
    rows = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_user_role(uid, new_role):
    conn = _connect()
    conn.execute("UPDATE users SET role=? WHERE id=?", (new_role, uid))
    conn.commit()
    conn.close()


def get_categories():
    conn = _connect()
    rows = conn.execute("SELECT * FROM categories ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_category_names():
    conn = _connect()
    rows = conn.execute("SELECT name FROM categories ORDER BY name").fetchall()
    conn.close()
    return [r["name"] for r in rows]


def add_category(name, description):
    if not name:
        return False, "Tên danh mục không được để trống."
    conn = _connect()
    try:
        conn.execute("INSERT INTO categories (name, description) VALUES (?,?)", (name, description))
        conn.commit()
        return True, "OK"
    except sqlite3.IntegrityError:
        return False, f"Danh mục '{name}' đã tồn tại."
    finally:
        conn.close()


def delete_category(cid):
    conn = _connect()
    used = conn.execute(
        "SELECT COUNT(*) FROM products WHERE category_name=(SELECT name FROM categories WHERE id=?)", (cid,)
    ).fetchone()[0]
    if used:
        conn.close()
        return False, "Không thể xóa: danh mục đang được sử dụng."
    conn.execute("DELETE FROM categories WHERE id=?", (cid,))
    conn.commit()
    conn.close()
    return True, "OK"


def create_product(seller_id, category, title, description, image_url,
                   start_price, step_price, buy_now_price, start_time, end_time):
    if not title:
        return False, "Tên sản phẩm không được để trống."
    if start_price <= 0 or step_price <= 0:
        return False, "Giá khởi điểm và bước giá phải lớn hơn 0."
    conn = _connect()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        """INSERT INTO products
           (seller_id, category_name, title, description, image_url,
            start_price, step_price, buy_now_price, current_price,
            status, start_time, end_time, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (seller_id, category, title, description, image_url,
         start_price, step_price, buy_now_price, start_price,
         "pending", start_time, end_time, now)
    )
    conn.commit()
    conn.close()
    return True, "OK"


def get_products(status=None, seller_id=None):
    conn = _connect()
    query = """
        SELECT p.*, u.username AS seller_name
        FROM products p
        JOIN users u ON u.id = p.seller_id
        WHERE 1=1
    """
    params = []
    if status:
        query += " AND p.status=?"
        params.append(status)
    if seller_id:
        query += " AND p.seller_id=?"
        params.append(seller_id)
    query += " ORDER BY p.created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_product_status(pid, status):
    conn = _connect()
    conn.execute("UPDATE products SET status=? WHERE id=?", (status, pid))
    conn.commit()
    conn.close()


def get_bids_for_product(pid):
    conn = _connect()
    rows = conn.execute(
        """SELECT b.amount, b.created_at, u.username AS bidder_name
           FROM bids b JOIN users u ON u.id = b.bidder_id
           WHERE b.product_id=?
           ORDER BY b.amount DESC""",
        (pid,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def place_bid(pid, user_id, amount):
    conn = _connect()
    product = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    if not product:
        conn.close()
        return False, "Sản phẩm không tồn tại."
    if product["status"] != "active":
        conn.close()
        return False, "Phiên đấu giá không còn hoạt động."
    min_bid = product["current_price"] + product["step_price"]
    if amount < min_bid:
        conn.close()
        return False, f"Giá đặt phải ít nhất {min_bid:,}đ.".replace(",", ".")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO bids (product_id, bidder_id, amount, created_at) VALUES (?,?,?,?)",
        (pid, user_id, amount, now)
    )
    conn.execute("UPDATE products SET current_price=? WHERE id=?", (amount, pid))
    conn.commit()
    conn.close()
    return True, "OK"


def buy_now(pid, user_id):
    conn = _connect()
    product = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    if not product:
        conn.close()
        return False, "Sản phẩm không tồn tại."
    if product["status"] != "active":
        conn.close()
        return False, "Phiên đấu giá không còn hoạt động."
    if not product["buy_now_price"]:
        conn.close()
        return False, "Sản phẩm này không hỗ trợ mua ngay."
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO bids (product_id, bidder_id, amount, created_at) VALUES (?,?,?,?)",
        (pid, user_id, product["buy_now_price"], now)
    )
    conn.execute(
        "UPDATE products SET current_price=?, status='completed' WHERE id=?",
        (product["buy_now_price"], pid)
    )
    conn.commit()
    conn.close()
    return True, "OK"


def get_bids_by_user(user_id):
    conn = _connect()
    rows = conn.execute(
        """SELECT b.amount, b.created_at,
                  p.title AS product_title, p.current_price
           FROM bids b
           JOIN products p ON p.id = b.product_id
           WHERE b.bidder_id=?
           ORDER BY b.created_at DESC""",
        (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
