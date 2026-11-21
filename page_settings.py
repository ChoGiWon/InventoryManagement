import csv
import datetime
import inspect
import os
import threading
import urllib.parse
import flet as ft
from database import get_meta, set_meta
from domain_service import download_public_dataset, export_inventory_csv_for_pc


PUBLIC_ROOT_DIR = "/storage/emulated/0/Download"
PUBLIC_CSV_DIR = "/storage/emulated/0/Download"
PUBLIC_KEY_DIR = "/storage/emulated/0/Download"
MAIL_SPLIT_DIR = "/storage/emulated/0/Download"
EMAIL_SPLIT_LIMIT_BYTES = 10 * 1024 * 1024  # 10MB 기준 분할
LOG_MAX_BYTES = 512 * 1024  # 로그 최대 보관 용량: 512KB (최신 로그 위주 유지)
LOG_FILE_CANDIDATES = [
    "/storage/emulated/0/Download/inventory_app_debug.log",
    os.path.join("local_storage", "inventory_app_debug.log"),
]


def _posix_join(base: str, name: str) -> str:
    b = (base or "").replace("\\", "/").rstrip("/")
    n = (name or "").replace("\\", "/").lstrip("/")
    if not b:
        return n
    return f"{b}/{n}"


def _get_active_log_path() -> str:
    for p in LOG_FILE_CANDIDATES:
        norm = p.replace("\\", "/")
        try:
            parent = os.path.dirname(norm)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(norm, "a", encoding="utf-8"):
                pass
            return norm
        except Exception:
            continue
    fallback = os.path.abspath("inventory_app_debug.log").replace("\\", "/")
    try:
        with open(fallback, "a", encoding="utf-8"):
            pass
    except Exception:
        pass
    return fallback


def _trim_log_to_limit(log_path: str, max_bytes: int = LOG_MAX_BYTES):
    """로그 용량이 max_bytes를 초과하면 오래된 앞부분을 잘라내어 최신 로그만 남깁니다."""
    try:
        if not os.path.exists(log_path):
            return
        size = os.path.getsize(log_path)
        if size <= max_bytes:
            return
        with open(log_path, "rb") as f:
            f.seek(max(0, size - max_bytes))
            tail = f.read()
        nl_idx = tail.find(b"\n")
        if nl_idx != -1 and nl_idx + 1 < len(tail):
            tail = tail[nl_idx + 1 :]
        with open(log_path, "wb") as f:
            f.write(tail)
    except Exception:
        pass


def _append_log(level: str, message: str):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {(message or '').strip()}\n"
    log_path = _get_active_log_path()
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line)
        _trim_log_to_limit(log_path, LOG_MAX_BYTES)
    except Exception:
        pass


def _read_logs_descending(max_lines: int = 200) -> tuple[str, str]:
    """저장된 로그를 읽어 맨 윗줄이 최신 정보가 되도록 내림차순으로 반환합니다."""
    log_path = _get_active_log_path()
    _trim_log_to_limit(log_path, LOG_MAX_BYTES)
    try:
        if not os.path.exists(log_path):
            return log_path, "기록된 로그가 없습니다."
        size_kb = os.path.getsize(log_path) / 1024.0
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = [ln.rstrip("\r\n") for ln in f.readlines() if ln.strip()]
        if not lines:
            return log_path, f"로그 파일 ({size_kb:.1f} KB / 최대 512 KB) - 기록된 로그가 없습니다."
        desc_lines = list(reversed(lines))[:max_lines]
        header = f"[최신순(내림차순) · 현재 {size_kb:.1f} KB / 상한 512 KB · {len(desc_lines)}줄 표시]\n"
        return log_path, header + "\n".join(desc_lines)
    except Exception as exc:
        return log_path, f"로그 읽기 오류: {exc}"


def _check_storage_permission_available() -> tuple[bool, str]:
    """공용 저장소(Download) 실제 쓰기 가능 여부로 저장소 권한 상태를 점검합니다."""
    test_dir = PUBLIC_ROOT_DIR
    probe_file = _posix_join(test_dir, ".perm_probe.tmp")
    try:
        os.makedirs(test_dir, exist_ok=True)
        with open(probe_file, "wb") as f:
            f.write(b"ok")
            f.flush()
        try:
            os.remove(probe_file)
        except Exception:
            pass
        return True, "공용 저장소(Download) 접근 가능"
    except PermissionError as exc:
        return False, f"저장소 권한이 허용되지 않았습니다 ({exc})"
    except Exception as exc:
        return False, f"공용 저장소 접근 불가 ({exc})"


def _write_bytes_safe(target_path: str, data: bytes) -> tuple[bool, str]:
    norm = target_path.replace("\\", "/")
    try:
        parent = os.path.dirname(norm)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(norm, "wb") as dst:
            dst.write(data)
            dst.flush()
            try:
                os.fsync(dst.fileno())
            except Exception:
                pass
        if os.path.exists(norm):
            size_b = os.path.getsize(norm)
            _append_log("INFO", f"파일 저장 성공: {norm} ({size_b} B)")
            return True, f"저장됨 ({size_b} B)"
        _append_log("WARN", f"파일 생성 후 미확인: {norm}")
        return False, "파일 생성 후 존재 확인 실패"
    except Exception as exc:
        _append_log("ERROR", f"파일 저장 실패 ({norm}): {exc}")
        return False, f"저장 실패: {exc}"


def _write_text_safe(target_path: str, text: str) -> tuple[bool, str]:
    return _write_bytes_safe(target_path, (text or "").encode("utf-8-sig"))


def _ensure_public_dirs():
    for d in (PUBLIC_ROOT_DIR, PUBLIC_CSV_DIR, PUBLIC_KEY_DIR, MAIL_SPLIT_DIR):
        try:
            os.makedirs(d, exist_ok=True)
        except Exception:
            pass


def _load_saved_key(meta_key: str, filename: str) -> str:
    val = (get_meta(meta_key, "") or "").strip()
    if val:
        return val
    candidates = [
        _posix_join(PUBLIC_KEY_DIR, filename),
        _posix_join("/storage/emulated/0/Download/InventoryManagement_Export", filename),
        os.path.join("local_storage", filename),
    ]
    for p in candidates:
        try:
            if os.path.exists(p) and os.path.isfile(p):
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    txt = (f.read() or "").strip()
                    if txt:
                        return txt
        except Exception:
            pass
    return ""


def _persist_api_key(meta_key: str, filename: str, raw_key: str) -> str:
    clean_key = (raw_key or "").strip()
    set_meta(meta_key, clean_key)
    if clean_key:
        _ensure_public_dirs()
        try:
            _write_bytes_safe(_posix_join(PUBLIC_KEY_DIR, filename), clean_key.encode("utf-8"))
        except Exception:
            pass
        _append_log("INFO", f"인증키 저장 완료 ({meta_key})")
    return clean_key


def _auto_generate_csv() -> tuple[str, str]:
    _ensure_public_dirs()
    exported = ""
    try:
        exported = export_inventory_csv_for_pc() or ""
    except Exception as exc:
        _append_log("WARN", f"export_inventory_csv_for_pc 호출 오류: {exc}")
        exported = ""

    target_path = _posix_join(PUBLIC_CSV_DIR, "inventory_latest.csv")
    if exported and os.path.exists(exported):
        try:
            with open(exported, "rb") as src:
                raw_bytes = src.read()
            ok, status_msg = _write_bytes_safe(target_path, raw_bytes)
            if ok:
                return target_path, status_msg
            return exported.replace("\\", "/"), f"공용 저장 실패({status_msg}) -> 앱 경로 사용"
        except Exception as exc:
            _append_log("ERROR", f"CSV 복사 오류: {exc}")
            return exported.replace("\\", "/"), f"복사 오류({exc}) -> 앱 경로 사용"

    ok, status_msg = _write_text_safe(target_path, "품목명,수량,비고\n")
    return target_path, status_msg


def _build_email_csv_files(source_csv_path: str, max_bytes: int = EMAIL_SPLIT_LIMIT_BYTES) -> list[str]:
    _ensure_public_dirs()
    single_mail_path = _posix_join(MAIL_SPLIT_DIR, "inventory_mail_attach.csv")

    if not source_csv_path or not os.path.exists(source_csv_path):
        _write_text_safe(single_mail_path, "품목명,수량,비고\n")
        _append_log("INFO", f"이메일용 기본 CSV 생성: {single_mail_path}")
        return [single_mail_path]

    total_size = os.path.getsize(source_csv_path)
    if total_size <= max_bytes:
        try:
            with open(source_csv_path, "rb") as src:
                _write_bytes_safe(single_mail_path, src.read())
        except Exception:
            _write_text_safe(single_mail_path, "")
        _append_log("INFO", f"이메일용 단일 CSV 생성: {single_mail_path} ({total_size} B)")
        return [single_mail_path]

    with open(source_csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = list(csv.reader(f))

    if not reader:
        _write_text_safe(single_mail_path, "")
        return [single_mail_path]

    header = reader[0]
    rows = reader[1:]
    if not rows:
        with open(single_mail_path, "w", encoding="utf-8-sig", newline="") as dst:
            csv.writer(dst).writerow(header)
        return [single_mail_path]

    split_paths: list[str] = []
    part_idx = 1

    def _open_part(idx: int):
        p = _posix_join(MAIL_SPLIT_DIR, f"inventory_mail_part{idx}.csv")
        fp = open(p, "w", encoding="utf-8-sig", newline="")
        wr = csv.writer(fp)
        wr.writerow(header)
        return p, fp, wr

    cur_path, cur_fp, cur_wr = _open_part(part_idx)
    has_row_in_part = False

    for row in rows:
        cur_fp.flush()
        if has_row_in_part and os.path.getsize(cur_path) >= max_bytes:
            cur_fp.close()
            split_paths.append(cur_path)
            part_idx += 1
            cur_path, cur_fp, cur_wr = _open_part(part_idx)
            has_row_in_part = False

        cur_wr.writerow(row)
        has_row_in_part = True

    cur_fp.close()
    split_paths.append(cur_path)
    _append_log("INFO", f"이메일용 분할 CSV 생성 완료: 총 {len(split_paths)}개 파일")
    return split_paths


def _format_file_size(path_str: str) -> str:
    try:
        size_bytes = os.path.getsize(path_str)
        if size_bytes < 1024:
            return f"{size_bytes} B"
        if size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    except Exception:
        return "파일 없음"


def _schedule_coroutine(page: ft.Page, coro) -> bool:
    if not inspect.iscoroutine(coro):
        return True
    if hasattr(page, "run_task"):
        async def _runner(c=coro):
            await c
        page.run_task(_runner)
        return True
    try:
        coro.close()
    except Exception:
        pass
    return False


def _safe_launch_url(page: ft.Page, url: str) -> bool:
    if not hasattr(page, "launch_url"):
        return False
    try:
        ret = page.launch_url(url)
        if inspect.iscoroutine(ret):
            return _schedule_coroutine(page, ret)
        if ret is False:
            return False
        return True
    except Exception:
        return False


def _safe_copy_text(page: ft.Page, text: str) -> bool:
    try:
        if hasattr(page, "set_clipboard"):
            ret = page.set_clipboard(text)
            if inspect.iscoroutine(ret):
                return _schedule_coroutine(page, ret)
            return True
    except Exception:
        pass
    try:
        if hasattr(page, "clipboard"):
            page.clipboard = text
            return True
    except Exception:
        pass
    return False


def _set_inline_msg(label: ft.Text, text: str, is_error: bool = False):
    label.value = text
    label.visible = bool(text)
    label.color = ft.Colors.RED_800 if is_error else ft.Colors.BLUE_900


def build_settings_page(page: ft.Page) -> ft.Control:
    _append_log("INFO", "설정 화면 진입")
    _ensure_public_dirs()
    set_meta("folder_configured", "1")
    set_meta("custom_folder_path", PUBLIC_ROOT_DIR)
    set_meta("api_keys_folder_path", PUBLIC_KEY_DIR)
    set_meta("csv_storage_folder_path", PUBLIC_CSV_DIR)

    perm_ok, perm_reason = _check_storage_permission_available()
    if not perm_ok:
        _append_log("WARN", f"저장소 권한 미허용 감지: {perm_reason}")

    latest_csv_path, latest_csv_status = _auto_generate_csv()
    csv_state = {"path": latest_csv_path, "status": latest_csv_status, "mailto_url": ""}

    def _open_key_guide_popup(title_label: str, search_keyword: str):
        _append_log("INFO", f"인증키 받는 방법 팝업 열림 ({search_keyword})")

        body_text = (
            f"1. 브라우저에서 [식품안전나라 공공데이터활용] 또는 [공공데이터포털]에 접속 후 로그인합니다.\n"
            f"2. 검색창에 '{search_keyword}'를 검색해 해당 OpenAPI를 선택합니다.\n"
            f"3. 이용/활용 신청 후 발급된 인증키를 복사합니다.\n"
            f"4. 앱 설정 화면의 인증키 입력칸에 붙여넣으면 자동으로 저장됩니다. (필요 시 [인증키 저장] 버튼도 누르실 수 있습니다.)"
        )

        dlg = ft.AlertDialog(
            modal=True,
            bgcolor=ft.Colors.WHITE,
            title=ft.Text(
                f"{title_label} 받는 방법",
                size=15,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.BLACK_87,
            ),
            content=ft.Text(body_text, size=12, color=ft.Colors.BLACK_87),
        )

        def _close_key_popup(e):
            dlg.open = False
            try:
                if hasattr(page, "close"):
                    page.close(dlg)
            except Exception:
                pass
            page.update()

        dlg.actions = [
            ft.TextButton(
                "닫기",
                style=ft.ButtonStyle(color=ft.Colors.BLUE_800),
                on_click=_close_key_popup,
            )
        ]

        try:
            if hasattr(page, "open"):
                page.open(dlg)
                return
        except Exception:
            pass
        if dlg not in page.overlay:
            page.overlay.append(dlg)
        dlg.open = True
        page.update()

    permission_denied_banner = ft.Container(
        visible=not perm_ok,
        content=ft.Row(
            [
                ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=ft.Colors.RED_800, size=20),
                ft.Text(
                    f"저장소 권한이 허용되어 있지 않습니다. CSV 저장/탐색이 제한될 수 있습니다. ({perm_reason})",
                    size=12,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.RED_900,
                    expand=True,
                ),
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=10,
        bgcolor=ft.Colors.RED_50,
        border_radius=8,
        border=ft.Border.all(1, ft.Colors.RED_300),
    )

    barcode_key_input = ft.TextField(
        label="바코드연계제품정보 인증키 (복사 후 붙여넣기)",
        hint_text="발급받은 인증키를 붙여넣으세요",
        value=_load_saved_key("barcode_api_key", "barcode_api_key.txt"),
        password=False,
        color=ft.Colors.BLACK_87,
        label_style=ft.TextStyle(color=ft.Colors.GREY_800, size=12, weight=ft.FontWeight.W_600),
        hint_style=ft.TextStyle(color=ft.Colors.GREY_500, size=11),
        text_size=12,
        content_padding=ft.Padding.symmetric(horizontal=10, vertical=8),
    )

    report_key_input = ft.TextField(
        label="식품(첨가물)품목제조보고 인증키 (복사 후 붙여넣기)",
        hint_text="발급받은 인증키를 붙여넣으세요",
        value=_load_saved_key("report_api_key", "food_report_api_key.txt"),
        password=False,
        color=ft.Colors.BLACK_87,
        label_style=ft.TextStyle(color=ft.Colors.GREY_800, size=12, weight=ft.FontWeight.W_600),
        hint_style=ft.TextStyle(color=ft.Colors.GREY_500, size=11),
        text_size=12,
        content_padding=ft.Padding.symmetric(horizontal=10, vertical=8),
    )

    barcode_save_badge = ft.Text(
        "저장됨" if (barcode_key_input.value or "").strip() else "미입력",
        size=11,
        weight=ft.FontWeight.BOLD,
        color=ft.Colors.GREEN_900 if (barcode_key_input.value or "").strip() else ft.Colors.GREY_700,
    )

    report_save_badge = ft.Text(
        "저장됨" if (report_key_input.value or "").strip() else "미입력",
        size=11,
        weight=ft.FontWeight.BOLD,
        color=ft.Colors.GREEN_900 if (report_key_input.value or "").strip() else ft.Colors.GREY_700,
    )

    # 각 버튼/영역 바로 아래에 표시되는 개별 메시지 라벨
    barcode_key_msg = ft.Text("", visible=False, size=11, weight=ft.FontWeight.W_600)
    report_key_msg = ft.Text("", visible=False, size=11, weight=ft.FontWeight.W_600)
    csv_action_msg = ft.Text("", visible=False, size=11, weight=ft.FontWeight.W_600)
    barcode_dl_msg = ft.Text("", visible=False, size=11, weight=ft.FontWeight.W_600)
    report_dl_msg = ft.Text("", visible=False, size=11, weight=ft.FontWeight.W_600)

    csv_info_text = ft.Text(
        f"상시 저장 위치: {csv_state['path']} ({_format_file_size(csv_state['path'])}) | {csv_state['status']}",
        size=11,
        weight=ft.FontWeight.W_600,
        color=ft.Colors.GREY_800,
    )

    barcode_ver_text = ft.Text(
        f"최종 다운로드(버전): {get_meta('barcode_api_updated_at', '미다운로드')}",
        size=12,
        weight=ft.FontWeight.W_600,
        color=ft.Colors.BLUE_900,
    )

    report_ver_text = ft.Text(
        f"최종 다운로드(버전): {get_meta('report_api_updated_at', '미다운로드')}",
        size=12,
        weight=ft.FontWeight.W_600,
        color=ft.Colors.BLUE_900,
    )

    log_viewer_path_text = ft.Text("", size=10, color=ft.Colors.GREY_700)
    log_viewer_content_text = ft.Text(
        "",
        size=11,
        color=ft.Colors.BLACK_87,
        selectable=True,
    )
    log_viewer_box = ft.Container(
        visible=False,
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(
                            "앱 동작 로그 (최신순 · 내림차순)",
                            size=12,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.BLUE_900,
                            expand=True,
                        ),
                        ft.TextButton(
                            "새로고침",
                            on_click=lambda _: _refresh_log_viewer(),
                            style=ft.ButtonStyle(color=ft.Colors.BLUE_800),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                log_viewer_path_text,
                ft.Container(
                    content=ft.Column(
                        [log_viewer_content_text],
                        scroll=ft.ScrollMode.AUTO,
                    ),
                    height=180,
                    bgcolor=ft.Colors.WHITE,
                    border=ft.Border.all(1, ft.Colors.GREY_300),
                    border_radius=6,
                    padding=8,
                ),
            ],
            spacing=6,
        ),
        bgcolor=ft.Colors.GREY_50,
        border=ft.Border.all(1, ft.Colors.BLUE_200),
        border_radius=8,
        padding=8,
    )

    info_popup_card = ft.Container(
        visible=False,
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.ERROR_OUTLINE, color=ft.Colors.BLUE_800, size=20),
                        ft.Text(
                            "앱 정보 및 동작 로그",
                            size=13,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.BLACK_87,
                            expand=True,
                        ),
                        ft.TextButton(
                            "닫기",
                            on_click=lambda _: _close_info_popup(),
                            style=ft.ButtonStyle(color=ft.Colors.RED_800),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Text(
                    "동작 중 발생한 기록을 확인할 수 있습니다. 문제 분석 시 [로그 보기]를 눌러 최신 로그를 확인하세요.",
                    size=11,
                    color=ft.Colors.GREY_800,
                ),
                ft.OutlinedButton(
                    "로그 보기",
                    icon=ft.Icons.ARTICLE_OUTLINED,
                    style=ft.ButtonStyle(
                        color=ft.Colors.BLUE_900,
                        icon_color=ft.Colors.BLUE_800,
                        side=ft.BorderSide(1, ft.Colors.BLUE_400),
                    ),
                    on_click=lambda _: _toggle_log_viewer(),
                ),
                log_viewer_box,
            ],
            spacing=8,
        ),
        padding=12,
        bgcolor=ft.Colors.BLUE_50,
        border_radius=10,
        border=ft.Border.all(1, ft.Colors.BLUE_300),
    )

    def _refresh_log_viewer():
        lpath, ltext = _read_logs_descending(max_lines=200)
        log_viewer_path_text.value = f"로그 파일: {lpath}"
        log_viewer_content_text.value = ltext
        page.update()

    def _toggle_log_viewer():
        next_vis = not log_viewer_box.visible
        log_viewer_box.visible = next_vis
        if next_vis:
            _refresh_log_viewer()
        else:
            page.update()

    def _open_info_popup(_=None):
        _append_log("INFO", "느낌표(!) 안내 팝업 열림")
        info_popup_card.visible = True
        log_viewer_box.visible = False
        page.update()

    def _close_info_popup():
        info_popup_card.visible = False
        log_viewer_box.visible = False
        page.update()

    mail_guide_feedback = ft.Text("", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_900)
    mail_guide_summary = ft.Text("", size=11, color=ft.Colors.BLACK_87)
    mail_file_list_col = ft.Column(spacing=6)

    def _on_click_open_mail_target(_):
        url = csv_state.get("mailto_url") or "mailto:"
        if _safe_launch_url(page, url):
            _append_log("INFO", "메일 앱/브라우저 선택 화면 호출 성공")
            mail_guide_feedback.value = "메일 앱 또는 브라우저 선택 화면을 열었습니다."
            mail_guide_feedback.color = ft.Colors.BLUE_900
        else:
            _append_log("WARN", "메일 앱/브라우저 자동 호출 실패")
            mail_guide_feedback.value = "메일 앱/브라우저를 직접 열어 위 파일명을 검색해 첨부해 주세요."
            mail_guide_feedback.color = ft.Colors.RED_800
        page.update()

    def _on_click_close_mail_card(_):
        mail_guide_card.visible = False
        mail_guide_feedback.value = ""
        page.update()

    mail_guide_card = ft.Container(
        visible=False,
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(
                            "이메일 전송용 CSV 파일 안내",
                            size=13,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.BLACK_87,
                            expand=True,
                        ),
                        ft.TextButton(
                            "닫기",
                            on_click=_on_click_close_mail_card,
                            style=ft.ButtonStyle(color=ft.Colors.RED_800),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                mail_guide_summary,
                mail_guide_feedback,
                mail_file_list_col,
                ft.OutlinedButton(
                    "메일 앱 / 브라우저 열기",
                    icon=ft.Icons.EMAIL,
                    style=ft.ButtonStyle(
                        color=ft.Colors.BLUE_900,
                        icon_color=ft.Colors.BLUE_800,
                        side=ft.BorderSide(1, ft.Colors.BLUE_400),
                    ),
                    on_click=_on_click_open_mail_target,
                ),
                ft.Text(
                    "• 파일 용량이 매우 커 메일 첨부가 어렵다면 Google Drive에 올린 뒤 공유 링크로 보내는 방법도 활용할 수 있습니다.",
                    size=11,
                    color=ft.Colors.GREY_800,
                ),
            ],
            spacing=8,
        ),
        padding=12,
        bgcolor=ft.Colors.BLUE_50,
        border_radius=10,
        border=ft.Border.all(1, ft.Colors.BLUE_300),
    )

    def _copy_filename(fname: str):
        ok = _safe_copy_text(page, fname)
        if ok:
            _append_log("INFO", f"파일명 복사: {fname}")
            mail_guide_feedback.value = f"복사됨: {fname} (메일 첨부 검색창에 붙여넣으세요)"
            mail_guide_feedback.color = ft.Colors.GREEN_900
        else:
            _append_log("WARN", f"클립보드 자동 복사 미지원: {fname}")
            mail_guide_feedback.value = f"아래 파일명 칸을 길게 눌러 복사하세요: {fname}"
            mail_guide_feedback.color = ft.Colors.RED_800
        page.update()

    def _on_move_to_folder(e):
        p_ok, p_reason = _check_storage_permission_available()
        permission_denied_banner.visible = not p_ok
        p, st = _auto_generate_csv()
        csv_state["path"], csv_state["status"] = p, st
        csv_info_text.value = f"상시 저장 위치: {p} ({_format_file_size(p)}) | {st}"
        _append_log("INFO", f"폴더이동 요청 -> 경로: {p}, 상태: {st}")

        launched = False
        for candidate_url in (
            f"file://{PUBLIC_CSV_DIR}",
            "content://com.android.externalstorage.documents/root/primary",
        ):
            if _safe_launch_url(page, candidate_url):
                launched = True
                break

        msg = (
            f"공용 저장 경로: {PUBLIC_CSV_DIR} | {st} (파일 앱에서 Download 폴더 확인)"
            if launched
            else f"공용 저장 경로: {PUBLIC_CSV_DIR} | {st} ({p_reason})"
        )
        _set_inline_msg(csv_action_msg, msg, is_error=not p_ok)
        page.update()

    def _on_send_email(e):
        p_ok, p_reason = _check_storage_permission_available()
        permission_denied_banner.visible = not p_ok
        p, st = _auto_generate_csv()
        csv_state["path"], csv_state["status"] = p, st
        csv_info_text.value = f"상시 저장 위치: {p} ({_format_file_size(p)}) | {st}"

        mail_files = _build_email_csv_files(p, EMAIL_SPLIT_LIMIT_BYTES)
        file_list_summary = "\n".join(
            f"- {os.path.basename(fp.replace(chr(92), '/'))} ({_format_file_size(fp)})" for fp in mail_files
        )
        subject = urllib.parse.quote("재고 관리 CSV 백업 파일")
        body = urllib.parse.quote(
            f"이메일 전송용 CSV 파일 목록입니다.\n{file_list_summary}\n\n"
            f"Download 폴더에서 위 파일명을 검색해 선택해 주세요."
        )
        csv_state["mailto_url"] = f"mailto:?subject={subject}&body={body}"

        _set_inline_msg(
            csv_action_msg,
            f"이메일 전송용 CSV {len(mail_files)}개 준비 완료" if p_ok else f"주의: {p_reason}",
            is_error=not p_ok,
        )

        mail_guide_summary.value = (
            f"용량 기준(10MB)에 따라 총 {len(mail_files)}개 파일이 준비되었습니다. "
            "파일명을 복사한 뒤 메일 첨부 창에서 검색해 첨부하세요."
        )
        mail_guide_feedback.value = "" if p_ok else f"주의: {p_reason}"
        mail_file_list_col.controls.clear()

        for idx, fpath in enumerate(mail_files, start=1):
            norm_path = fpath.replace("\\", "/")
            fname = os.path.basename(norm_path)
            fsize = _format_file_size(norm_path)
            exists_label = "존재함" if os.path.exists(norm_path) else "미존재"
            mail_file_list_col.controls.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text(
                                        f"{idx}. {fname} ({fsize} · {exists_label})",
                                        size=12,
                                        weight=ft.FontWeight.BOLD,
                                        color=ft.Colors.BLACK_87,
                                        expand=True,
                                    ),
                                    ft.OutlinedButton(
                                        "파일명 복사",
                                        icon=ft.Icons.COPY,
                                        style=ft.ButtonStyle(
                                            color=ft.Colors.BLUE_900,
                                            icon_color=ft.Colors.BLUE_800,
                                            side=ft.BorderSide(1, ft.Colors.BLUE_300),
                                            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                                        ),
                                        on_click=lambda _, name=fname: _copy_filename(name),
                                    ),
                                ],
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=6,
                            ),
                            ft.TextField(
                                value=fname,
                                read_only=True,
                                dense=True,
                                text_size=11,
                                color=ft.Colors.BLACK_87,
                                content_padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                            ),
                            ft.Text(f"경로: {norm_path}", size=10, color=ft.Colors.GREY_700),
                        ],
                        spacing=4,
                    ),
                    bgcolor=ft.Colors.WHITE,
                    border=ft.Border.all(1, ft.Colors.GREY_300),
                    border_radius=8,
                    padding=8,
                )
            )

        mail_guide_card.visible = True
        page.update()

    def _save_barcode_key(e=None, show_toast: bool = True):
        saved = _persist_api_key("barcode_api_key", "barcode_api_key.txt", barcode_key_input.value or "")
        barcode_save_badge.value = "저장됨" if saved else "미입력"
        barcode_save_badge.color = ft.Colors.GREEN_900 if saved else ft.Colors.GREY_700
        if show_toast:
            _set_inline_msg(
                barcode_key_msg,
                "바코드연계제품정보 인증키가 자동 저장되었습니다."
                if saved
                else "붙여넣은 바코드 인증키가 없습니다.",
                is_error=not saved,
            )
        page.update()
        return saved

    def _save_report_key(e=None, show_toast: bool = True):
        saved = _persist_api_key("report_api_key", "food_report_api_key.txt", report_key_input.value or "")
        report_save_badge.value = "저장됨" if saved else "미입력"
        report_save_badge.color = ft.Colors.GREEN_900 if saved else ft.Colors.GREY_700
        if show_toast:
            _set_inline_msg(
                report_key_msg,
                "식품(첨가물)품목제조보고 인증키가 자동 저장되었습니다."
                if saved
                else "붙여넣은 품목제조보고 인증키가 없습니다.",
                is_error=not saved,
            )
        page.update()
        return saved

    barcode_key_input.on_change = lambda e: _save_barcode_key(e, show_toast=False)
    report_key_input.on_change = lambda e: _save_report_key(e, show_toast=False)

    def _run_dataset_download(dataset_type: str, ver_label: ft.Text, dl_msg_label: ft.Text, btn: ft.Control | None = None):
        if dataset_type == "barcode":
            key_val = _save_barcode_key(show_toast=False)
            key_name = "바코드연계제품정보"
        else:
            key_val = _save_report_key(show_toast=False)
            key_name = "식품(첨가물)품목제조보고"

        if not key_val:
            _append_log("WARN", f"{key_name} 인증키 미입력으로 다운로드 중단")
            _set_inline_msg(dl_msg_label, f"붙여넣은 {key_name} 인증키가 없습니다.", is_error=True)
            page.update()
            return

        _append_log("INFO", f"{key_name} 다운로드 시작")
        if btn is not None:
            btn.disabled = True
        _set_inline_msg(dl_msg_label, f"{key_name} 다운로드 실행 중...", is_error=False)
        page.update()

        def worker():
            try:
                ok, msg = download_public_dataset(dataset_type)
            except Exception as exc:
                ok, msg = False, f"다운로드 실행 중 오류: {str(exc)}"

            _append_log("INFO" if ok else "ERROR", f"{key_name} 다운로드 결과: {msg}")
            if dataset_type == "barcode":
                ver_label.value = f"최종 다운로드(버전): {get_meta('barcode_api_updated_at', '미다운로드')}"
            else:
                ver_label.value = f"최종 다운로드(버전): {get_meta('report_api_updated_at', '미다운로드')}"

            _set_inline_msg(dl_msg_label, msg, is_error=not ok)
            if btn is not None:
                btn.disabled = False
            try:
                page.update()
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()

    return ft.Column(
        [
            ft.Row(
                [
                    ft.Text(
                        "설정 및 데이터 관리",
                        size=18,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.BLACK_87,
                        expand=True,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.ERROR_OUTLINE,
                        tooltip="안내 및 로그 보기",
                        icon_color=ft.Colors.BLUE_800,
                        on_click=_open_info_popup,
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            permission_denied_banner,
            info_popup_card,
            ft.Container(
                content=ft.Column(
                    [
                        ft.Text("공공데이터 인증키 (붙여넣기 시 자동 저장)", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK_87),
                        ft.Row(
                            [
                                ft.Text("바코드연계제품정보 키", size=12, weight=ft.FontWeight.W_600, color=ft.Colors.BLACK_87, expand=True),
                                barcode_save_badge,
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        barcode_key_input,
                        ft.Row(
                            [
                                ft.Button(
                                    "인증키 저장",
                                    icon=ft.Icons.SAVE,
                                    bgcolor=ft.Colors.GREY_800,
                                    color=ft.Colors.WHITE,
                                    on_click=lambda e: _save_barcode_key(e, show_toast=True),
                                ),
                                ft.OutlinedButton(
                                    "인증키 받는 방법",
                                    icon=ft.Icons.HELP_OUTLINE,
                                    style=ft.ButtonStyle(
                                        color=ft.Colors.BLUE_900,
                                        icon_color=ft.Colors.BLUE_800,
                                        side=ft.BorderSide(1, ft.Colors.BLUE_400),
                                    ),
                                    on_click=lambda e: _open_key_guide_popup(
                                        "바코드연계제품정보 인증키",
                                        "바코드연계제품정보",
                                    ),
                                ),
                            ],
                            spacing=8,
                            wrap=True,
                        ),
                        barcode_key_msg,
                        ft.Divider(height=8, color=ft.Colors.GREY_300),
                        ft.Row(
                            [
                                ft.Text("식품(첨가물)품목제조보고 키", size=12, weight=ft.FontWeight.W_600, color=ft.Colors.BLACK_87, expand=True),
                                report_save_badge,
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        report_key_input,
                        ft.Row(
                            [
                                ft.Button(
                                    "인증키 저장",
                                    icon=ft.Icons.SAVE,
                                    bgcolor=ft.Colors.GREY_800,
                                    color=ft.Colors.WHITE,
                                    on_click=lambda e: _save_report_key(e, show_toast=True),
                                ),
                                ft.OutlinedButton(
                                    "인증키 받는 방법",
                                    icon=ft.Icons.HELP_OUTLINE,
                                    style=ft.ButtonStyle(
                                        color=ft.Colors.BLUE_900,
                                        icon_color=ft.Colors.BLUE_800,
                                        side=ft.BorderSide(1, ft.Colors.BLUE_400),
                                    ),
                                    on_click=lambda e: _open_key_guide_popup(
                                        "식품(첨가물)품목제조보고 인증키",
                                        "식품(첨가물)품목제조보고",
                                    ),
                                ),
                            ],
                            spacing=8,
                            wrap=True,
                        ),
                        report_key_msg,
                        ft.Divider(height=8, color=ft.Colors.GREY_300),
                        ft.Text("CSV 자동 저장 (앱 삭제 후에도 공용 저장소에 보존)", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK_87),
                        csv_info_text,
                        ft.Row(
                            [
                                ft.OutlinedButton(
                                    "폴더이동",
                                    icon=ft.Icons.FOLDER_OPEN,
                                    expand=True,
                                    style=ft.ButtonStyle(
                                        color=ft.Colors.BLACK_87,
                                        icon_color=ft.Colors.BLUE_800,
                                        side=ft.BorderSide(1, ft.Colors.GREY_500),
                                    ),
                                    on_click=_on_move_to_folder,
                                ),
                                ft.OutlinedButton(
                                    "이메일 보내기",
                                    icon=ft.Icons.EMAIL,
                                    expand=True,
                                    style=ft.ButtonStyle(
                                        color=ft.Colors.BLACK_87,
                                        icon_color=ft.Colors.BLUE_800,
                                        side=ft.BorderSide(1, ft.Colors.GREY_500),
                                    ),
                                    on_click=_on_send_email,
                                ),
                            ],
                            spacing=8,
                        ),
                        csv_action_msg,
                    ],
                    spacing=8,
                ),
                padding=12,
                bgcolor=ft.Colors.WHITE,
                border_radius=10,
                border=ft.Border.all(1, ft.Colors.GREY_300),
            ),
            mail_guide_card,
            ft.Container(
                content=ft.Column(
                    [
                        ft.Button(
                            "바코드연계제품정보 다운로드",
                            icon=ft.Icons.QR_CODE,
                            bgcolor=ft.Colors.GREY_900,
                            color=ft.Colors.WHITE,
                            on_click=lambda e: _run_dataset_download("barcode", barcode_ver_text, barcode_dl_msg, e.control),
                        ),
                        barcode_dl_msg,
                        barcode_ver_text,
                    ],
                    spacing=6,
                ),
                padding=12,
                bgcolor=ft.Colors.WHITE,
                border_radius=10,
                border=ft.Border.all(1, ft.Colors.GREY_300),
            ),
            ft.Container(
                content=ft.Column(
                    [
                        ft.Button(
                            "식품(첨가물)품목제조보고 다운로드",
                            icon=ft.Icons.INVENTORY_2,
                            bgcolor=ft.Colors.GREY_900,
                            color=ft.Colors.WHITE,
                            on_click=lambda e: _run_dataset_download("report", report_ver_text, report_dl_msg, e.control),
                        ),
                        report_dl_msg,
                        report_ver_text,
                    ],
                    spacing=6,
                ),
                padding=12,
                bgcolor=ft.Colors.WHITE,
                border_radius=10,
                border=ft.Border.all(1, ft.Colors.GREY_300),
            ),
            ft.Container(height=48),
        ],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
        spacing=12,
    )