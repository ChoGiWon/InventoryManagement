import os
import sqlite3
from datetime import datetime

DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "local_storage")
DB_PATH = os.path.join(DB_DIR, "inventory_local.db")
UPLOAD_DIR = os.path.join(DB_DIR, "product_photos")
EXPORT_DIR = os.path.join(DB_DIR, "InventoryManagement_Export")


def ensure_directories():
    os.makedirs(DB_DIR, exist_ok=True)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(EXPORT_DIR, exist_ok=True)


def get_connection():
    ensure_directories()
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    # 1. 공공데이터 마스터 테이블 (바코드연계제품정보 + 품목제조보고 통합 적재)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS master_products (
            bar_cd TEXT PRIMARY KEY,
            prdlst_report_no TEXT,
            prdlst_nm TEXT,
            pog_daycnt TEXT,
            prdlst_dcnm TEXT,
            bssh_nm TEXT,
            induty_nm TEXT,
            site_addr TEXT,
            prms_dt TEXT,
            end_dt TEXT,
            clsbiz_dt TEXT,
            photo_path TEXT,
            source_type TEXT
        )
    """)

    # 2. 사용자 보관 재고 테이블 (달력 및 실제 재고관리용)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS inventory_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bar_cd TEXT,
            prdlst_nm TEXT NOT NULL,
            expiry_date TEXT NOT NULL,
            quantity INTEGER DEFAULT 1,
            location TEXT DEFAULT '기본보관함',
            photo_path TEXT,
            memo TEXT,
            created_at TEXT
        )
    """)

    # 3. 우측 옵션 체크박스 표시 설정 테이블
    cur.execute("""
        CREATE TABLE IF NOT EXISTS option_preferences (
            field_key TEXT PRIMARY KEY,
            field_label TEXT NOT NULL,
            is_checked INTEGER DEFAULT 0
        )
    """)

    # 4. 버전 및 다운로드 일시 메타 테이블
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sync_metadata (
            meta_key TEXT PRIMARY KEY,
            meta_value TEXT
        )
    """)

    # 기본 추가 옵션 항목 초기화
    default_options = [
        ("prdlst_report_no", "품목제조보고번호", 0),
        ("prdlst_dcnm", "식품유형", 1),
        ("pog_daycnt", "소비기한/유통기한 기준", 1),
        ("bssh_nm", "제조사(업소명)", 0),
        ("induty_nm", "업종명", 0),
        ("site_addr", "제조소 소재지", 0),
        ("prms_dt", "허가(신고)일자", 0),
        ("clsbiz_dt", "폐업일자", 0),
    ]
    for key, label, checked in default_options:
        cur.execute("""
            INSERT OR IGNORE INTO option_preferences (field_key, field_label, is_checked)
            VALUES (?, ?, ?)
        """, (key, label, checked))

    # 기본 메타 정보 초기화
    cur.execute("INSERT OR IGNORE INTO sync_metadata (meta_key, meta_value) VALUES ('app_version', '1.0.0')")
    cur.execute("INSERT OR IGNORE INTO sync_metadata (meta_key, meta_value) VALUES ('barcode_api_updated_at', '미다운로드')")
    cur.execute("INSERT OR IGNORE INTO sync_metadata (meta_key, meta_value) VALUES ('report_api_updated_at', '미다운로드')")
    cur.execute("INSERT OR IGNORE INTO sync_metadata (meta_key, meta_value) VALUES ('custom_folder_path', ?)", (EXPORT_DIR,))

    # 샘플 테스트 데이터 (초기 확인용)
    cur.execute("""
        INSERT OR IGNORE INTO master_products (
            bar_cd, prdlst_report_no, prdlst_nm, pog_daycnt, prdlst_dcnm,
            bssh_nm, induty_nm, site_addr, prms_dt, end_dt, clsbiz_dt, photo_path, source_type
        ) VALUES (
            '8801062000012', '19970312001', '쵸코카라멜', '제조일로부터 12개월', '캔디류',
            '한양제과주식회사', '식품제조가공업', '경기도 동두천시', '19971009', '20161124', '', '', '바코드연계제품정보'
        )
    """)

    today_str = datetime.now().strftime("%Y-%m-%d")
    cur.execute("SELECT COUNT(*) as cnt FROM inventory_items")
    if cur.fetchone()["cnt"] == 0:
        cur.execute("""
            INSERT INTO inventory_items (bar_cd, prdlst_nm, expiry_date, quantity, location, photo_path, memo, created_at)
            VALUES ('8801062000012', '쵸코카라멜', ?, 3, '거실 간식함', '', '테스트 재고', ?)
        """, (today_str, today_str))

    conn.commit()
    conn.close()


def get_meta(key: str, default: str = "") -> str:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT meta_value FROM sync_metadata WHERE meta_key = ?", (key,))
    row = cur.fetchone()
    conn.close()
    return row["meta_value"] if row and row["meta_value"] is not None else default


def set_meta(key: str, value: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO sync_metadata (meta_key, meta_value)
        VALUES (?, ?)
        ON CONFLICT(meta_key) DO UPDATE SET meta_value = excluded.meta_value
    """, (key, value))
    conn.commit()
    conn.close()