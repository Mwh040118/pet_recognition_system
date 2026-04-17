import sqlite3  # 轻量级数据库 SQLite
from config import DB_PATH
import os
from datetime import date, timedelta

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS pets (
            id TEXT PRIMARY KEY,
            category TEXT,
            name TEXT,
            scientific_name TEXT,
            class_name TEXT,
            order_name TEXT,
            family TEXT,
            species TEXT,
            advice TEXT,
            image_path TEXT,
            size TEXT,
            coat TEXT,
            lifespan TEXT,
            temperament TEXT,
            origin TEXT
        )
    ''')
    # 旧表迁移：尝试添加新列（若已存在则忽略）
    for col, coltype in [("size","TEXT"),("coat","TEXT"),("lifespan","TEXT"),
                         ("temperament","TEXT"),("origin","TEXT")]:
        try:
            c.execute(f"ALTER TABLE pets ADD COLUMN {col} {coltype}")
        except Exception:
            pass

    c.execute('''
        CREATE TABLE IF NOT EXISTS pet_profile (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            pet_name TEXT,
            pet_type TEXT,
            pet_stage TEXT,
            note TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS pet_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pet_name TEXT NOT NULL,
            pet_type TEXT NOT NULL,
            pet_stage TEXT NOT NULL,
            note TEXT,
            photo_path TEXT,
            emoji TEXT,
            breed_name TEXT,
            gender TEXT,
            birthday TEXT,
            weight TEXT,
            health_notes TEXT
        )
    ''')
    # 旧表迁移
    for col, coltype in [("photo_path","TEXT"),("emoji","TEXT"),("breed_name","TEXT"),
                         ("gender","TEXT"),("birthday","TEXT"),("weight","TEXT"),("health_notes","TEXT")]:
        try:
            c.execute(f"ALTER TABLE pet_profiles ADD COLUMN {col} {coltype}")
        except Exception:
            pass

    c.execute('''
        CREATE TABLE IF NOT EXISTS daily_reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            is_done INTEGER NOT NULL DEFAULT 0
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS health_calendar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL UNIQUE,
            due_date TEXT NOT NULL
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS recognition_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            source TEXT NOT NULL,
            label TEXT NOT NULL,
            confidence REAL NOT NULL
        )
    ''')

    c.execute("SELECT COUNT(*) FROM pet_profile")
    if c.fetchone()[0] == 0:
        c.execute(
            "INSERT INTO pet_profile (id, pet_name, pet_type, pet_stage, note) VALUES (1, ?, ?, ?, ?)",
            ("Milo", "猫", "成猫", "已接种疫苗")
        )

    c.execute("SELECT COUNT(*) FROM pet_profiles")
    profile_count = c.fetchone()[0]
    if profile_count == 0:
        c.execute("SELECT pet_name, pet_type, pet_stage, note FROM pet_profile WHERE id=1")
        old_row = c.fetchone()
        if old_row:
            c.execute(
                "INSERT INTO pet_profiles (pet_name, pet_type, pet_stage, note) VALUES (?, ?, ?, ?)",
                old_row
            )
        else:
            c.execute(
                "INSERT INTO pet_profiles (pet_name, pet_type, pet_stage, note) VALUES (?, ?, ?, ?)",
                ("Milo", "猫", "成猫", "已接种疫苗")
            )

    c.execute("SELECT COUNT(*) FROM daily_reminders")
    if c.fetchone()[0] == 0:
        c.executemany(
            "INSERT INTO daily_reminders (title, is_done) VALUES (?, ?)",
            [("早晚喂食", 0), ("补充饮水", 0), ("梳毛清洁", 0)]
        )

    c.execute("SELECT COUNT(*) FROM health_calendar")
    if c.fetchone()[0] == 0:
        c.executemany(
            "INSERT INTO health_calendar (item_name, due_date) VALUES (?, ?)",
            [
                ("疫苗复查", (date.today() + timedelta(days=12)).isoformat()),
                ("体内驱虫", (date.today() + timedelta(days=5)).isoformat())
            ]
        )

    # ── 时间隧道记录表 ─────────────────────────────────────────
    c.execute('''
        CREATE TABLE IF NOT EXISTS tunnel_records (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            title     TEXT    NOT NULL,
            text_note TEXT    DEFAULT '',
            created_at TEXT   NOT NULL,
            ts        INTEGER NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS tunnel_images (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id  INTEGER NOT NULL REFERENCES tunnel_records(id) ON DELETE CASCADE,
            image_path TEXT    NOT NULL,
            sort_order INTEGER DEFAULT 0
        )
    ''')

    conn.commit()
    conn.close()

def insert_pet(data):
    # data = (id, category, name, scientific_name, class_name, order_name, family, species, advice, image_path,
    #          size, coat, lifespan, temperament, origin)  — 新格式15列
    # 兼容旧10列格式
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if len(data) == 10:
        c.execute("INSERT INTO pets (id,category,name,scientific_name,class_name,order_name,family,species,advice,image_path) VALUES (?,?,?,?,?,?,?,?,?,?)", data)
    else:
        c.execute("INSERT INTO pets VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", data)
    conn.commit()
    conn.close()

def get_pets_by_category(category):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id,category,name,scientific_name,class_name,order_name,family,species,advice,image_path,size,coat,lifespan,temperament,origin FROM pets WHERE category=?", (category,))
    data = c.fetchall()
    conn.close()
    return data

def get_pet_by_id(pet_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id,category,name,scientific_name,class_name,order_name,family,species,advice,image_path,size,coat,lifespan,temperament,origin FROM pets WHERE id=?", (pet_id,))
    row = c.fetchone()
    conn.close()
    return row

def _ensure_pet_columns(c):
    """确保 pets 表有所有新列（兼容旧数据库）"""
    for col, coltype in [("size","TEXT"),("coat","TEXT"),("lifespan","TEXT"),
                         ("temperament","TEXT"),("origin","TEXT")]:
        try:
            c.execute(f"ALTER TABLE pets ADD COLUMN {col} {coltype}")
        except Exception:
            pass

def update_pet(pet_id, category, name, advice, image_path, size, coat, lifespan, temperament, origin, scientific_name="", class_name="", order_name="", family="", species=""):
    """更新宠物品种信息，image_path 为 None 时不更新图片字段。异常会向上抛出。"""
    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()
        _ensure_pet_columns(c)  # 确保列存在
        if image_path is not None:
            c.execute("""
                UPDATE pets SET category=?, name=?, scientific_name=?, class_name=?, order_name=?, family=?, species=?,
                advice=?, image_path=?, size=?, coat=?, lifespan=?, temperament=?, origin=?
                WHERE id=?
            """, (category, name, scientific_name, class_name, order_name, family, species,
                  advice, image_path, size, coat, lifespan, temperament, origin, pet_id))
        else:
            c.execute("""
                UPDATE pets SET category=?, name=?, scientific_name=?, class_name=?, order_name=?, family=?, species=?,
                advice=?, size=?, coat=?, lifespan=?, temperament=?, origin=?
                WHERE id=?
            """, (category, name, scientific_name, class_name, order_name, family, species,
                  advice, size, coat, lifespan, temperament, origin, pet_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def delete_pet(pet_id):
    # 删除一条宠物记录，返回其图片路径用于清理文件
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT image_path FROM pets WHERE id=?", (pet_id,))
    row = c.fetchone()
    image_path = row[0] if row else None
    c.execute("DELETE FROM pets WHERE id=?", (pet_id,))
    conn.commit()
    conn.close()
    return image_path

def search_pets(keyword):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    kw = f"%{keyword}%"
    c.execute("""
        SELECT id,category,name,scientific_name,class_name,order_name,family,species,advice,image_path,size,coat,lifespan,temperament,origin
        FROM pets
        WHERE name LIKE ? OR scientific_name LIKE ?
           OR family LIKE ? OR species LIKE ?
    """, (kw, kw, kw, kw))
    data = c.fetchall()
    conn.close()
    return data

def get_pet_profile():
    profiles = list_pet_profiles()
    if not profiles:
        return {"id": None, "pet_name": "", "pet_type": "", "pet_stage": "", "note": ""}
    return profiles[0]

def update_pet_profile(pet_name, pet_type, pet_stage, note):
    profile = get_pet_profile()
    if profile.get("id") is None:
        create_pet_profile(pet_name, pet_type, pet_stage, note)
        return
    update_pet_profile_by_id(profile["id"], pet_name, pet_type, pet_stage, note)

def list_pet_profiles():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id,pet_name,pet_type,pet_stage,note,photo_path,emoji,breed_name,gender,birthday,weight,health_notes FROM pet_profiles ORDER BY id ASC")
    rows = c.fetchall()
    conn.close()
    return [
        {
            "id": row[0], "pet_name": row[1] or "", "pet_type": row[2] or "",
            "pet_stage": row[3] or "", "note": row[4] or "",
            "photo_path": row[5] or "", "emoji": row[6] or "🐾",
            "breed_name": row[7] or "", "gender": row[8] or "",
            "birthday": row[9] or "", "weight": row[10] or "",
            "health_notes": row[11] or "[]"
        }
        for row in rows
    ]

def get_pet_profile_by_id(profile_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id,pet_name,pet_type,pet_stage,note,photo_path,emoji,breed_name,gender,birthday,weight,health_notes FROM pet_profiles WHERE id=?", (profile_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0], "pet_name": row[1] or "", "pet_type": row[2] or "",
        "pet_stage": row[3] or "", "note": row[4] or "",
        "photo_path": row[5] or "", "emoji": row[6] or "🐾",
        "breed_name": row[7] or "", "gender": row[8] or "",
        "birthday": row[9] or "", "weight": row[10] or "",
        "health_notes": row[11] or "[]"
    }

def create_pet_profile(pet_name, pet_type, pet_stage, note,
                       photo_path="", emoji="🐾", breed_name="",
                       gender="", birthday="", weight="", health_notes="[]"):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO pet_profiles (pet_name,pet_type,pet_stage,note,photo_path,emoji,breed_name,gender,birthday,weight,health_notes) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (pet_name, pet_type, pet_stage, note, photo_path, emoji, breed_name, gender, birthday, weight, health_notes)
    )
    new_id = c.lastrowid
    conn.commit()
    conn.close()
    return new_id

def update_pet_profile_by_id(profile_id, pet_name, pet_type, pet_stage, note,
                              photo_path=None, emoji=None, breed_name=None,
                              gender=None, birthday=None, weight=None, health_notes=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # 先读出已有值
    c.execute("SELECT photo_path,emoji,breed_name,gender,birthday,weight,health_notes FROM pet_profiles WHERE id=?", (profile_id,))
    row = c.fetchone()
    if row:
        photo_path  = photo_path  if photo_path  is not None else (row[0] or "")
        emoji       = emoji       if emoji       is not None else (row[1] or "🐾")
        breed_name  = breed_name  if breed_name  is not None else (row[2] or "")
        gender      = gender      if gender      is not None else (row[3] or "")
        birthday    = birthday    if birthday    is not None else (row[4] or "")
        weight      = weight      if weight      is not None else (row[5] or "")
        health_notes= health_notes if health_notes is not None else (row[6] or "[]")
    c.execute(
        "UPDATE pet_profiles SET pet_name=?,pet_type=?,pet_stage=?,note=?,photo_path=?,emoji=?,breed_name=?,gender=?,birthday=?,weight=?,health_notes=? WHERE id=?",
        (pet_name, pet_type, pet_stage, note, photo_path, emoji, breed_name, gender, birthday, weight, health_notes, profile_id)
    )
    conn.commit()
    conn.close()

def get_daily_reminders():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, title, is_done FROM daily_reminders ORDER BY id ASC")
    rows = c.fetchall()
    conn.close()
    return rows

def update_daily_reminder(reminder_id, is_done):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE daily_reminders SET is_done=? WHERE id=?", (1 if is_done else 0, reminder_id))
    conn.commit()
    conn.close()

def get_health_events():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT item_name, due_date FROM health_calendar ORDER BY due_date ASC")
    rows = c.fetchall()
    conn.close()
    return rows

def upsert_health_event(item_name, due_date):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO health_calendar (item_name, due_date)
        VALUES (?, ?)
        ON CONFLICT(item_name) DO UPDATE SET due_date=excluded.due_date
        """,
        (item_name, due_date)
    )
    conn.commit()
    conn.close()

def add_recognition_record(source, label, confidence, created_at):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO recognition_records (created_at, source, label, confidence) VALUES (?, ?, ?, ?)",
        (created_at, source, label, confidence)
    )
    conn.commit()
    conn.close()

def get_recognition_records(limit=500):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT created_at, source, label, confidence FROM recognition_records ORDER BY id DESC LIMIT ?",
        (limit,)
    )
    rows = c.fetchall()
    conn.close()
    return rows


# ─── 时间隧道 CRUD ──────────────────────────────────────────
def create_tunnel_record(title, text_note, created_at, ts, image_paths):
    """新建一条时光记录，image_paths 是 ['/uploads/xxx.jpg', ...] 列表"""
    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()
        c.execute(
            "INSERT INTO tunnel_records (title, text_note, created_at, ts) VALUES (?, ?, ?, ?)",
            (title, text_note or '', created_at, ts)
        )
        record_id = c.lastrowid
        for i, path in enumerate(image_paths):
            c.execute(
                "INSERT INTO tunnel_images (record_id, image_path, sort_order) VALUES (?, ?, ?)",
                (record_id, path, i)
            )
        conn.commit()
        return record_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_tunnel_records():
    """返回全部记录，每条包含 images 列表，按时间倒序"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, title, text_note, created_at, ts FROM tunnel_records ORDER BY ts DESC")
    rows = c.fetchall()
    result = []
    for row in rows:
        rid, title, text_note, created_at, ts = row
        c.execute(
            "SELECT image_path FROM tunnel_images WHERE record_id=? ORDER BY sort_order",
            (rid,)
        )
        imgs = [r[0] for r in c.fetchall()]
        result.append({
            "id": rid,
            "title": title,
            "text": text_note,
            "date": created_at,
            "ts": ts,
            "images": imgs
        })
    conn.close()
    return result


def delete_tunnel_record(record_id):
    """删除一条记录，返回该记录的图片路径列表（用于清理文件）"""
    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()
        c.execute("SELECT image_path FROM tunnel_images WHERE record_id=?", (record_id,))
        paths = [r[0] for r in c.fetchall()]
        c.execute("DELETE FROM tunnel_images WHERE record_id=?", (record_id,))
        c.execute("DELETE FROM tunnel_records WHERE id=?", (record_id,))
        conn.commit()
        return paths
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

