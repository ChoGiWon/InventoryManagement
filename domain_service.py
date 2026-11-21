import csv
import json
import os
import shutil
import urllib.request
from datetime import datetime
from database import get_connection, set_meta, get_meta, UPLOAD_DIR, EXPORT_DIR


def lookup_and_compare_barcode(scanned_data: dict) -> dict:
    """
    인식된 바코드 정보와 내부 DB(master_products)를 비교하여
    항목별 불일치 여부를 반환하고 사진 경로를 결정합니다.
    """
    bar_cd = str(scanned_data.get("bar_cd", "")).strip()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM master_products WHERE bar_cd = ?", (bar_cd,))
    db_row = cur.fetchone()
    conn.close()

    db_dict = dict(db_row) if db_row else {}
    compare_fields = [
        ("bar_cd", "바코드 번호"),
        ("prdlst_nm", "제품명"),
        ("bssh_nm", "제조사"),
        ("prdlst_dcnm", "식품유형"),
        ("pog_daycnt", "유통/소비기한 기준"),
    ]

    comparison_results = []
    for key, label in compare_fields:
        scanned_val = str(scanned_data.get(key, "") or "").strip()
        db_val = str(db_dict.get(key, "") or "").strip()

        if not db_dict:
            status = "DB 미등록"
            is_mismatch = True
        elif scanned_val and db_val and scanned_val != db_val:
            status = "불일치"
            is_mismatch = True
        elif not scanned_val and db_val:
            # 스캔 원천에 값이 없고 DB에만 있는 경우 DB 값으로 보완 표시
            scanned_val = db_val
            status = "일치(DB보완)"
            is_mismatch = False
        else:
            status = "일치"
            is_mismatch = False

        comparison_results.append({
            "key": key,
            "label": label,
            "scanned_val": scanned_val or "-",
            "db_val": db_val or "-",
            "status": status,
            "is_mismatch": is_mismatch,
        })

    # 사진 우선순위: 내부 DB 사진 존재 시 우선 사용, 없으면 빈 값(사용자 업로드 유도)
    photo_path = db_dict.get("photo_path", "") if db_dict else ""
    if photo_path and not os.path.exists(photo_path):
        photo_path = ""

    return {
        "found_in_db": bool(db_dict),
        "db_record": db_dict,
        "comparisons": comparison_results,
        "photo_path": photo_path,
    }


def save_uploaded_product_photo(bar_cd: str, source_file_path: str) -> str:
    """사용자가 업로드한 사진을 로컬 저장소에 보관하고 내부 DB에 연결합니다."""
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(source_file_path)[1] or ".jpg"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest_filename = f"{bar_cd}_{timestamp}{ext}"
    dest_path = os.path.join(UPLOAD_DIR, dest_filename)
    shutil.copy2(source_file_path, dest_path)

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT bar_cd FROM master_products WHERE bar_cd = ?", (bar_cd,))
    if cur.fetchone():
        cur.execute("UPDATE master_products SET photo_path = ? WHERE bar_cd = ?", (dest_path, bar_cd))
    else:
        cur.execute("""
            INSERT INTO master_products (bar_cd, prdlst_nm, photo_path, source_type)
            VALUES (?, ?, ?, '사용자직접등록')
        """, (bar_cd, f"미등록상품({bar_cd})", dest_path))

    cur.execute("UPDATE inventory_items SET photo_path = ? WHERE bar_cd = ?", (dest_path, bar_cd))
    conn.commit()
    conn.close()
    return dest_path


def get_checked_extra_fields(db_record: dict) -> list:
    """우측 옵션에서 체크된 항목만 추출하여 하단 별도 출력용 리스트를 생성합니다."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT field_key, field_label, is_checked FROM option_preferences")
    prefs = cur.fetchall()
    conn.close()

    extra_items = []
    for p in prefs:
        if p["is_checked"] == 1:
            val = db_record.get(p["field_key"], "") if db_record else ""
            extra_items.append({
                "key": p["field_key"],
                "label": p["field_label"],
                "value": val if val else "정보 없음",
            })
    return extra_items


def update_option_preference(field_key: str, is_checked: bool):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE option_preferences SET is_checked = ? WHERE field_key = ?",
        (1 if is_checked else 0, field_key),
    )
    conn.commit()
    conn.close()


def get_all_option_preferences() -> list:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT field_key, field_label, is_checked FROM option_preferences")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def download_public_dataset(dataset_type: str) -> tuple[bool, str]:
    """
    지정 폴더에 저장된 인증키 파일을 읽어 공공데이터를 다운로드하고 내부 DB에 적재합니다.
    dataset_type: 'barcode' (바코드연계제품정보) | 'report' (식품(첨가물)품목제조보고)
    """
    folder = get_meta("custom_folder_path", EXPORT_DIR)
    if dataset_type == "barcode":
        key_file = os.path.join(folder, "barcode_api_key.txt")
        service_id = "C005"
        meta_key = "barcode_api_updated_at"
        label = "바코드연계제품정보"
    else:
        key_file = os.path.join(folder, "food_report_api_key.txt")
        service_id = "I1250"
        meta_key = "report_api_updated_at"
        label = "식품(첨가물)품목제조보고"

    if not os.path.exists(key_file):
        return False, f"인증키 파일이 없습니다.\n경로: {key_file}\n안내 팝업의 절차대로 키 파일을 먼저 저장해주세요."

    with open(key_file, "r", encoding="utf-8") as f:
        api_key = f.read().strip()

    if not api_key:
        return False, f"인증키 파일({os.path.basename(key_file)}) 내용이 비어 있습니다."

    url = f"http://openapi.foodsafetykorea.go.kr/api/{api_key}/{service_id}/json/1/200"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
            data = json.loads(raw)

        service_block = data.get(service_id, {})
        result_info = service_block.get("RESULT", {})
        if result_info.get("CODE") != "INFO-000":
            return False, f"API 응답 오류: {result_info.get('MSG', '알 수 없는 오류')}"

        rows = service_block.get("row", [])
        conn = get_connection()
        cur = conn.cursor()
        saved_count = 0

        for r in rows:
            bar_cd = str(r.get("BAR_CD") or r.get("PRDLST_REPORT_NO") or "").strip()
            if not bar_cd:
                continue
            cur.execute("""
                INSERT INTO master_products (
                    bar_cd, prdlst_report_no, prdlst_nm, pog_daycnt, prdlst_dcnm,
                    bssh_nm, induty_nm, site_addr, prms_dt, end_dt, clsbiz_dt, source_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(bar_cd) DO UPDATE SET
                    prdlst_report_no = excluded.prdlst_report_no,
                    prdlst_nm = excluded.prdlst_nm,
                    pog_daycnt = excluded.pog_daycnt,
                    prdlst_dcnm = excluded.prdlst_dcnm,
                    bssh_nm = excluded.bssh_nm,
                    induty_nm = excluded.induty_nm,
                    site_addr = excluded.site_addr,
                    prms_dt = excluded.prms_dt,
                    end_dt = excluded.end_dt,
                    clsbiz_dt = excluded.clsbiz_dt,
                    source_type = excluded.source_type
            """, (
                bar_cd,
                str(r.get("PRDLST_REPORT_NO", "")),
                str(r.get("PRDLST_NM", "")),
                str(r.get("POG_DAYCNT", "")),
                str(r.get("PRDLST_DCNM", "")),
                str(r.get("BSSH_NM", "")),
                str(r.get("INDUTY_NM", "")),
                str(r.get("SITE_ADDR", "")),
                str(r.get("PRMS_DT", "")),
                str(r.get("END_DT", "")),
                str(r.get("CLSBIZ_DT", "")),
                label,
            ))
            saved_count += 1

        conn.commit()
        conn.close()

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        set_meta(meta_key, now_str)
        return True, f"[{label}] {saved_count}건 적재 완료\n다운로드 일시: {now_str}"

    except Exception as e:
        return False, f"다운로드 중 오류 발생: {str(e)}"


def export_inventory_csv_for_pc() -> str:
    """모바일 로컬 폴더에 PC 활용/이메일 전송용 CSV 파일을 생성합니다."""
    folder = get_meta("custom_folder_path", EXPORT_DIR)
    os.makedirs(folder, exist_ok=True)
    filename = f"inventory_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = os.path.join(folder, filename)

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM inventory_items ORDER BY expiry_date ASC")
    rows = cur.fetchall()
    conn.close()

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "바코드", "제품명", "유통기한", "수량", "보관위치", "메모", "등록일"])
        for r in rows:
            writer.writerow([
                r["id"], r["bar_cd"], r["prdlst_nm"], r["expiry_date"],
                r["quantity"], r["location"], r["memo"], r["created_at"]
            ])
    return filepath


def get_calendar_month_summary(year: int, month: int) -> dict:
    """특정 연·월의 일자별 재고 만료/임박 요약 정보를 집계합니다."""
    prefix = f"{year:04d}-{month:02d}-"
    today = datetime.now().date()

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM inventory_items WHERE expiry_date LIKE ?", (f"{prefix}%",))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    summary = {}
    for item in rows:
        d_str = item["expiry_date"]
        if d_str not in summary:
            summary[d_str] = {"count": 0, "total_qty": 0, "expired": 0, "soon": 0, "items": []}

        exp_date = datetime.strptime(d_str, "%Y-%m-%d").date()
        diff_days = (exp_date - today).days

        summary[d_str]["count"] += 1
        summary[d_str]["total_qty"] += int(item.get("quantity", 1))
        if diff_days < 0:
            summary[d_str]["expired"] += 1
        elif diff_days <= 7:
            summary[d_str]["soon"] += 1
        summary[d_str]["items"].append(item)

    return summary


def add_inventory_item(bar_cd: str, prdlst_nm: str, expiry_date: str, quantity: int, location: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT photo_path FROM master_products WHERE bar_cd = ?", (bar_cd,))
    row = cur.fetchone()
    photo_path = row["photo_path"] if row else ""
    now_str = datetime.now().strftime("%Y-%m-%d")

    cur.execute("""
        INSERT INTO inventory_items (bar_cd, prdlst_nm, expiry_date, quantity, location, photo_path, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (bar_cd, prdlst_nm, expiry_date, quantity, location, photo_path, now_str))
    conn.commit()
    conn.close()