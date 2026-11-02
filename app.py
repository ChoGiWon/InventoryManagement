from datetime import date, datetime
import os
import sqlite3

import openpyxl
from flask import Flask, jsonify, render_template, request, send_file

app = Flask(__name__)
DB_PATH = "database.db"


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            barcode TEXT,
            name TEXT NOT NULL,
            expiry_date TEXT NOT NULL,
            quantity INTEGER DEFAULT 1,
            location TEXT DEFAULT '기본',
            is_deleted INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


init_db()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/barcode/<barcode_num>", methods=["GET"])
def get_barcode_info(barcode_num):
    mock_db = {
        "8801043014847": "농심 신라면",
        "8801056000010": "코카콜라 500ml",
        "8801062264826": "롯데 자일리톨 껌",
    }
    product_name = mock_db.get(barcode_num, "")
    return jsonify({"success": True, "barcode": barcode_num, "name": product_name})


# 등록된 보관 위치 목록 조회 API
@app.route("/api/locations", methods=["GET"])
def get_locations():
    try:
        conn = get_db_connection()
        rows = conn.execute(
            "SELECT DISTINCT location FROM inventory WHERE is_deleted = 0 AND location != ''"
        ).fetchall()
        conn.close()
        locations = [row["location"] for row in rows]
        if "기본" not in locations:
            locations.insert(0, "기본")
        return jsonify(locations)
    except Exception as e:
        return jsonify(["기본", "냉장실", "냉동실", "팬트리"])


# 재고 목록 조회 (정렬 및 휴지통 필터 지원)
@app.route("/api/items", methods=["GET"])
def get_items():
    sort_type = request.args.get("sort", "expiry_asc")
    show_trash = request.args.get("trash", "false") == "true"
    search_query = request.args.get("q", "").strip()

    conn = get_db_connection()

    query = "SELECT * FROM inventory WHERE 1=1"
    params = []

    if show_trash:
        query += " AND is_deleted = 1"
    else:
        query += " AND is_deleted = 0"

    if search_query:
        query += " AND (name LIKE ? OR barcode LIKE ? OR location LIKE ?)"
        like_term = f"%{search_query}%"
        params.extend([like_term, like_term, like_term])

    # 정렬 조건 반영
    if sort_type == "expiry_asc":
        query += " ORDER BY expiry_date ASC"
    elif sort_type == "expiry_desc":
        query += " ORDER BY expiry_date DESC"
    elif sort_type == "name_asc":
        query += " ORDER BY name ASC"
    elif sort_type == "name_desc":
        query += " ORDER BY name DESC"
    elif sort_type == "quantity_asc":
        query += " ORDER BY quantity ASC"
    elif sort_type == "quantity_desc":
        query += " ORDER BY quantity DESC"
    elif sort_type == "barcode_asc":
        query += " ORDER BY barcode ASC"
    elif sort_type == "barcode_desc":
        query += " ORDER BY barcode DESC"
    else:
        query += " ORDER BY expiry_date ASC"

    items = conn.execute(query, params).fetchall()
    conn.close()

    today = date.today()
    item_list = []

    for item in items:
        try:
            exp = datetime.strptime(item["expiry_date"], "%Y-%m-%d").date()
            diff = (exp - today).days
        except:
            diff = 0

        if diff < 0:
            status = "expired"
        elif diff <= 7:
            status = "warning"
        else:
            status = "normal"

        item_list.append(
            {
                "id": item["id"],
                "barcode": item["barcode"],
                "name": item["name"],
                "expiry_date": item["expiry_date"],
                "quantity": item["quantity"],
                "location": item["location"],
                "days_left": diff,
                "status": status,
                "is_deleted": item["is_deleted"],
            }
        )

    return jsonify(item_list)


@app.route("/api/items", methods=["POST"])
def add_item():
    try:
        data = request.json
        if not data or not data.get("name") or not data.get("expiry_date"):
            return jsonify({"success": False, "message": "상품명과 유통기한은 필수입니다."}), 400

        conn = get_db_connection()
        conn.execute(
            "INSERT INTO inventory (barcode, name, expiry_date, quantity, location, is_deleted) VALUES (?, ?, ?, ?, ?, 0)",
            (
                data.get("barcode", ""),
                data["name"],
                data["expiry_date"],
                data.get("quantity", 1),
                data.get("location", "기본"),
            ),
        )
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        print(f"Add Item Error: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500


# 휴지통으로 이동 (소프트 삭제)
@app.route("/api/items/<int:item_id>", methods=["DELETE"])
def delete_item(item_id):
    conn = get_db_connection()
    conn.execute("UPDATE inventory SET is_deleted = 1 WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


# 휴지통 항목 복원
@app.route("/api/items/<int:item_id>/restore", methods=["POST"])
def restore_item(item_id):
    conn = get_db_connection()
    conn.execute("UPDATE inventory SET is_deleted = 0 WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


# 휴지통 항목 영구 삭제
@app.route("/api/items/<int:item_id>/permanent", methods=["DELETE"])
def permanent_delete_item(item_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM inventory WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@app.route("/api/export/excel", methods=["GET"])
def export_excel():
    conn = get_db_connection()
    items = conn.execute(
        "SELECT * FROM inventory WHERE is_deleted = 0 ORDER BY expiry_date ASC"
    ).fetchall()
    conn.close()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "유통기한 재고 목록"

    headers = ["ID", "바코드", "상품명", "유통기한", "수량", "보관장소"]
    ws.append(headers)

    for item in items:
        ws.append(
            [
                item["id"],
                item["barcode"],
                item["name"],
                item["expiry_date"],
                item["quantity"],
                item["location"],
            ]
        )

    file_path = "inventory_export.xlsx"
    wb.save(file_path)

    return send_file(
        file_path, as_attachment=True, download_name=f"inventory_{date.today()}.xlsx"
    )


# 바코드별 수량 합계 조회 (바코드 합계 뷰)
@app.route("/api/items/summary", methods=["GET"])
def get_items_summary():
    conn = get_db_connection()
    query = """
        SELECT 
            barcode, 
            name, 
            SUM(quantity) AS total_quantity,
            COUNT(*) AS item_count,
            MIN(expiry_date) AS earliest_expiry
        FROM inventory 
        WHERE is_deleted = 0
        GROUP BY CASE WHEN barcode != '' THEN barcode ELSE name END
        ORDER BY earliest_expiry ASC
    """
    summaries = conn.execute(query).fetchall()
    conn.close()

    summary_list = []
    today = date.today()

    for item in summaries:
        try:
            exp = datetime.strptime(item["earliest_expiry"], "%Y-%m-%d").date()
            diff = (exp - today).days
        except:
            diff = 0

        summary_list.append(
            {
                "barcode": item["barcode"] if item["barcode"] else "바코드 없음",
                "name": item["name"],
                "total_quantity": item["total_quantity"],
                "item_count": item["item_count"],
                "earliest_expiry": item["earliest_expiry"],
                "days_left": diff,
            }
        )

    return jsonify(summary_list)


# 월별 유통기한 캘린더 데이터 조회
@app.route("/api/items/calendar", methods=["GET"])
def get_calendar_items():
    year_month = request.args.get("ym", datetime.now().strftime("%Y-%m"))

    conn = get_db_connection()
    query = """
        SELECT * FROM inventory 
        WHERE is_deleted = 0 AND expiry_date LIKE ?
        ORDER BY expiry_date ASC
    """
    items = conn.execute(query, (f"{year_month}%",)).fetchall()
    conn.close()

    calendar_data = {}
    for item in items:
        day = item["expiry_date"]
        if day not in calendar_data:
            calendar_data[day] = []

        calendar_data[day].append(
            {
                "id": item["id"],
                "name": item["name"],
                "quantity": item["quantity"],
                "location": item["location"],
            }
        )

    return jsonify(calendar_data)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)