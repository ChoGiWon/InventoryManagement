from datetime import datetime
import flet as ft
from database import set_meta
from domain_service import (
    lookup_and_compare_barcode,
    save_uploaded_product_photo,
    get_checked_extra_fields,
    update_option_preference,
    get_all_option_preferences,
    add_inventory_item,
)


def build_main_page(page: ft.Page) -> ft.Control:
    today_str = datetime.now().strftime("%Y-%m-%d")
    category_options = ["과자", "아이스크림", "음료수", "기타"]

    barcode_input = ft.TextField(
        label="바코드 번호",
        hint_text="바코드 입력/스캔",
        value="",
        color=ft.Colors.BLACK_87,
        label_style=ft.TextStyle(color=ft.Colors.GREY_800, size=12, weight=ft.FontWeight.W_600),
        hint_style=ft.TextStyle(color=ft.Colors.GREY_500, size=12),
        expand=True,
        text_size=14,
        content_padding=ft.Padding.symmetric(horizontal=10, vertical=8),
    )
    scanned_name_input = ft.TextField(
        label="스캔 수신 제품명",
        hint_text="제품명 입력",
        value="",
        color=ft.Colors.BLACK_87,
        label_style=ft.TextStyle(color=ft.Colors.GREY_800, size=12, weight=ft.FontWeight.W_600),
        hint_style=ft.TextStyle(color=ft.Colors.GREY_500, size=12),
        expand=True,
        text_size=14,
        content_padding=ft.Padding.symmetric(horizontal=10, vertical=8),
    )
    photo_path_input = ft.TextField(
        label="로컬 사진 파일 경로",
        hint_text="예: /storage/emulated/0/...",
        value="",
        color=ft.Colors.BLACK_87,
        label_style=ft.TextStyle(color=ft.Colors.GREY_800, size=12),
        expand=True,
        text_size=13,
        visible=False,
        content_padding=ft.Padding.symmetric(horizontal=8, vertical=6),
    )

    photo_preview = ft.Image(
        src="",
        width=76,
        height=76,
        fit=ft.BoxFit.CONTAIN,
        border_radius=8,
        visible=False,
    )
    no_photo_box = ft.Container(
        content=ft.Column(
            [
                ft.Icon(ft.Icons.HIDE_IMAGE_OUTLINED, size=20, color=ft.Colors.GREY_700),
                ft.Text("사진 없음", size=11, weight=ft.FontWeight.W_500, color=ft.Colors.GREY_700, text_align=ft.TextAlign.CENTER),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=2,
        ),
        width=76,
        height=76,
        bgcolor=ft.Colors.GREY_200,
        border_radius=8,
        alignment=ft.Alignment.CENTER,
    )

    comparison_list = ft.Column(spacing=4)
    option_panel = ft.Column(spacing=2, visible=False)
    extra_fields_box = ft.Column(spacing=4)
    status_text = ft.Text(
        "바코드 번호 또는 제품명을 입력하고 [DB 비교]를 누르세요.",
        size=12,
        weight=ft.FontWeight.W_600,
        color=ft.Colors.BLUE_900,
    )

    category_dropdown = ft.Dropdown(
        label="분류",
        value="과자",
        width=116,
        text_size=13,
        color=ft.Colors.BLACK_87,
        label_style=ft.TextStyle(color=ft.Colors.GREY_800, size=12, weight=ft.FontWeight.W_600),
        options=[ft.dropdown.Option(c) for c in category_options],
        content_padding=ft.Padding.symmetric(horizontal=8, vertical=6),
    )
    expiry_input = ft.TextField(
        label="유통기한",
        hint_text="YYYY-MM-DD",
        value=today_str,
        color=ft.Colors.BLACK_87,
        label_style=ft.TextStyle(color=ft.Colors.GREY_800, size=12, weight=ft.FontWeight.W_600),
        hint_style=ft.TextStyle(color=ft.Colors.GREY_500, size=11),
        expand=True,
        text_size=13,
        content_padding=ft.Padding.symmetric(horizontal=8, vertical=7),
    )
    qty_input = ft.TextField(
        label="수량",
        value="1",
        color=ft.Colors.BLACK_87,
        label_style=ft.TextStyle(color=ft.Colors.GREY_800, size=12, weight=ft.FontWeight.W_600),
        width=56,
        text_size=13,
        content_padding=ft.Padding.symmetric(horizontal=6, vertical=7),
    )
    location_input = ft.TextField(
        label="위치",
        hint_text="보관위치",
        value="냉장고",
        color=ft.Colors.BLACK_87,
        label_style=ft.TextStyle(color=ft.Colors.GREY_800, size=12, weight=ft.FontWeight.W_600),
        hint_style=ft.TextStyle(color=ft.Colors.GREY_500, size=11),
        expand=True,
        text_size=13,
        content_padding=ft.Padding.symmetric(horizontal=8, vertical=7),
    )
    supplier_input = ft.TextField(
        label="거래처 정보",
        hint_text="거래처명 입력 (선택)",
        value="",
        color=ft.Colors.BLACK_87,
        label_style=ft.TextStyle(color=ft.Colors.GREY_800, size=12, weight=ft.FontWeight.W_600),
        hint_style=ft.TextStyle(color=ft.Colors.GREY_500, size=11),
        expand=True,
        text_size=13,
        content_padding=ft.Padding.symmetric(horizontal=8, vertical=7),
    )

    state = {
        "show_options": False,
        "last_result": None,
        "has_scanned_data": False,
    }

    def _sync_register_card_visibility():
        has_input = bool((barcode_input.value or "").strip() or (scanned_name_input.value or "").strip())
        register_card.visible = bool(state["has_scanned_data"] or has_input)

    def _on_input_changed(e):
        _sync_register_card_visibility()
        page.update()

    barcode_input.on_change = _on_input_changed
    scanned_name_input.on_change = _on_input_changed

    def _notify(msg: str, is_error: bool = False):
        status_text.value = msg
        status_text.color = ft.Colors.RED_800 if is_error else ft.Colors.BLUE_900
        snack = ft.SnackBar(
            ft.Text(msg, color=ft.Colors.WHITE),
            bgcolor=ft.Colors.RED_700 if is_error else ft.Colors.BLUE_800,
        )
        if snack not in page.overlay:
            page.overlay.append(snack)
        snack.open = True
        page.update()

    def _update_photo_ui(photo_path: str):
        if photo_path:
            photo_preview.src = photo_path
            photo_preview.visible = True
            no_photo_box.visible = False
        else:
            photo_preview.src = ""
            photo_preview.visible = False
            no_photo_box.visible = True

    def _make_status_line(status_label: str, is_mismatch: bool):
        return ft.Row(
            [
                ft.Container(
                    content=ft.Text(
                        f"상태: {status_label}",
                        size=11,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.RED_900 if is_mismatch else ft.Colors.GREEN_900,
                        max_lines=1,
                        no_wrap=True,
                    ),
                    bgcolor=ft.Colors.RED_100 if is_mismatch else ft.Colors.GREEN_100,
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                    border_radius=6,
                ),
            ],
            spacing=4,
        )

    def _make_row(field_label: str, value_text: str, status_label: str, is_mismatch: bool):
        return ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(
                                field_label,
                                size=12,
                                weight=ft.FontWeight.BOLD,
                                width=84,
                                color=ft.Colors.BLACK_87,
                            ),
                            ft.Text(
                                str(value_text or "-"),
                                size=13,
                                weight=ft.FontWeight.W_500,
                                expand=True,
                                color=ft.Colors.BLACK_87,
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.START,
                        spacing=6,
                    ),
                    _make_status_line(status_label, is_mismatch),
                ],
                spacing=4,
            ),
            padding=ft.Padding.symmetric(vertical=7, horizontal=4),
            border=ft.Border.only(bottom=ft.BorderSide(1, ft.Colors.GREY_200)),
        )

    def _refresh_extra_fields(db_record: dict):
        extra_fields_box.controls.clear()
        checked_items = get_checked_extra_fields(db_record)
        for item in checked_items:
            extra_fields_box.controls.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Text(item["label"], size=12, weight=ft.FontWeight.BOLD, width=92, color=ft.Colors.BLUE_900),
                            ft.Text(str(item["value"]), size=12, expand=True, color=ft.Colors.BLACK_87),
                        ],
                        spacing=6,
                    ),
                    bgcolor=ft.Colors.BLUE_50,
                    padding=ft.Padding.symmetric(horizontal=8, vertical=6),
                    border_radius=6,
                )
            )

    def _rebuild_option_checkboxes():
        option_panel.controls.clear()
        prefs = get_all_option_preferences()
        for pref in prefs:
            f_key = pref["field_key"]
            f_label = pref["field_label"]
            checked = bool(pref["is_checked"])

            def make_change_handler(key_target):
                def on_change(e):
                    update_option_preference(key_target, bool(e.control.value))
                    last_res = state.get("last_result") or {}
                    _refresh_extra_fields(last_res.get("db_record") or {})
                    page.update()
                return on_change

            option_panel.controls.append(
                ft.Checkbox(
                    label=f_label,
                    label_style=ft.TextStyle(color=ft.Colors.BLACK_87, size=13, weight=ft.FontWeight.W_500),
                    value=checked,
                    on_change=make_change_handler(f_key),
                )
            )

    def on_compare_click(e=None):
        bar_cd = (barcode_input.value or "").strip()
        scanned_name = (scanned_name_input.value or "").strip()
        checked_at = datetime.now().strftime("%H:%M:%S")

        if not bar_cd and not scanned_name:
            state["has_scanned_data"] = False
            _sync_register_card_visibility()
            _notify(f"[{checked_at}] 비교할 내용이 없습니다. 바코드 번호 또는 제품명을 입력하세요.", is_error=True)
            return

        scanned_payload = {
            "bar_cd": bar_cd,
            "prdlst_nm": scanned_name,
        }
        result = lookup_and_compare_barcode(scanned_payload)
        state["last_result"] = result
        state["has_scanned_data"] = True
        _sync_register_card_visibility()

        comparison_list.controls.clear()
        for comp in result.get("comparisons", []):
            comparison_list.controls.append(
                _make_row(
                    comp.get("label", ""),
                    comp.get("scanned_val", "-"),
                    comp.get("status", "일치"),
                    bool(comp.get("is_mismatch", False)),
                )
            )

        _update_photo_ui(result.get("photo_path", ""))
        _refresh_extra_fields(result.get("db_record") or {})

        if result.get("found_in_db"):
            db_name = (result.get("db_record") or {}).get("prdlst_nm", "")
            _notify(f"[{checked_at}] DB 비교 완료: {db_name or bar_cd}", is_error=False)
        else:
            _notify(f"[{checked_at}] DB 미등록({bar_cd or scanned_name}) — 확인 후 재고 추가 가능", is_error=False)

    def on_camera_scan_click(e):
        set_meta("camera_permission_status", "granted")

        scan_field = ft.TextField(
            label="스캔/인식된 바코드 번호",
            hint_text="바코드 숫자 입력",
            value=(barcode_input.value or "").strip(),
            color=ft.Colors.BLACK_87,
            label_style=ft.TextStyle(color=ft.Colors.GREY_800, size=12, weight=ft.FontWeight.W_600),
            text_size=14,
        )

        def apply_scanned_code(_):
            code = (scan_field.value or "").strip()
            scan_dialog.open = False
            if code:
                barcode_input.value = code
                on_compare_click()
            else:
                _notify("바코드 번호를 입력한 뒤 [인식 완료 및 DB 비교]를 누르세요.", is_error=True)
                page.update()

        def close_scan_dialog(_):
            scan_dialog.open = False
            page.update()

        scan_dialog = ft.AlertDialog(
            modal=True,
            bgcolor=ft.Colors.WHITE,
            title=ft.Text("바코드 스캔 입력", weight=ft.FontWeight.BOLD, size=16, color=ft.Colors.BLACK_87),
            content=ft.Column(
                [
                    ft.Text(
                        "Flet 모바일 클라이언트에서는 기본 카메라 렌즈 화면이 직접 열리지 않습니다.\n"
                        "기기 카메라/스캐너로 확인한 바코드 번호를 입력해 DB와 비교하세요.",
                        size=12,
                        color=ft.Colors.GREY_800,
                    ),
                    scan_field,
                ],
                tight=True,
                spacing=10,
            ),
            actions=[
                ft.TextButton("닫기", style=ft.ButtonStyle(color=ft.Colors.GREY_800), on_click=close_scan_dialog),
                ft.Button(
                    "인식 완료 및 DB 비교",
                    icon=ft.Icons.QR_CODE_SCANNER,
                    bgcolor=ft.Colors.BLUE_700,
                    color=ft.Colors.WHITE,
                    on_click=apply_scanned_code,
                ),
            ],
        )
        if scan_dialog not in page.overlay:
            page.overlay.append(scan_dialog)
        scan_dialog.open = True
        page.update()

    def toggle_options(e):
        state["show_options"] = not state["show_options"]
        option_panel.visible = state["show_options"]
        if state["show_options"]:
            _rebuild_option_checkboxes()
        page.update()

    def on_upload_photo_click(e):
        if not photo_path_input.visible:
            photo_path_input.visible = True
            _notify("로컬 사진 파일 경로를 입력한 뒤 [사진 업로드]를 다시 누르세요.", is_error=False)
            return

        src_path = (photo_path_input.value or "").strip().strip('"')
        bar_cd = (barcode_input.value or "").strip()
        if not bar_cd:
            _notify("사진을 연결할 바코드 번호를 입력하세요.", is_error=True)
            return
        if not src_path:
            _notify("사진 파일 경로를 입력하세요.", is_error=True)
            return

        try:
            saved_path = save_uploaded_product_photo(bar_cd, src_path)
            _update_photo_ui(saved_path)
            photo_path_input.visible = False
            _notify(f"사진 저장 완료: {saved_path}", is_error=False)
        except Exception as err:
            _notify(f"사진 저장 오류: {str(err)}", is_error=True)

    def on_add_inventory(e):
        bar_cd = (barcode_input.value or "").strip()
        scanned_name = (scanned_name_input.value or "").strip()
        res = state.get("last_result") or {}
        db_rec = res.get("db_record") or {}
        prdlst_nm = (db_rec.get("prdlst_nm") or scanned_name).strip()

        if not bar_cd and not prdlst_nm:
            _notify("추가할 내용이 없습니다. 바코드 번호 또는 제품명을 입력하세요.", is_error=True)
            return

        final_bar_cd = bar_cd or f"NO_BARCODE_{datetime.now().strftime('%H%M%S')}"
        final_name = prdlst_nm or f"미등록상품({final_bar_cd})"
        cat_val = category_dropdown.value or "과자"
        expiry_date = (expiry_input.value or today_str).strip()
        try:
            qty = max(1, int((qty_input.value or "1").strip()))
        except ValueError:
            qty = 1
        loc = (location_input.value or "냉장고").strip() or "냉장고"
        supp = (supplier_input.value or "").strip()

        add_inventory_item(
            bar_cd=final_bar_cd,
            prdlst_nm=final_name,
            expiry_date=expiry_date,
            quantity=qty,
            location=loc,
            supplier=supp,
            category=cat_val,
        )
        supp_msg = f" | 거래처: {supp}" if supp else ""
        _notify(f"재고 등록 완료: [{cat_val}] {final_name} ({expiry_date}, {qty}개, {loc}{supp_msg})", is_error=False)

    register_card = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        category_dropdown,
                        expiry_input,
                        qty_input,
                    ],
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row(
                    [
                        location_input,
                        supplier_input,
                    ],
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Button(
                    "재고 추가",
                    icon=ft.Icons.ADD,
                    bgcolor=ft.Colors.GREEN_600,
                    color=ft.Colors.WHITE,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=14)),
                    on_click=on_add_inventory,
                ),
            ],
            spacing=8,
        ),
        bgcolor=ft.Colors.WHITE,
        padding=10,
        border_radius=12,
        border=ft.Border.all(1, ft.Colors.GREY_300),
        visible=False,
    )

    _sync_register_card_visibility()

    return ft.Column(
        [
            ft.Container(
                content=ft.Column(
                    [
                        ft.Row([barcode_input, scanned_name_input], spacing=8),
                        ft.Row(
                            [
                                ft.Button(
                                    "바코드 스캔",
                                    icon=ft.Icons.CAMERA_ALT,
                                    bgcolor=ft.Colors.BLUE_700,
                                    color=ft.Colors.WHITE,
                                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=14)),
                                    on_click=on_camera_scan_click,
                                ),
                                ft.Button(
                                    "DB 비교",
                                    icon=ft.Icons.QR_CODE_SCANNER,
                                    bgcolor=ft.Colors.GREY_900,
                                    color=ft.Colors.WHITE,
                                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=14)),
                                    on_click=on_compare_click,
                                ),
                                ft.OutlinedButton(
                                    "옵션",
                                    icon=ft.Icons.TUNE,
                                    style=ft.ButtonStyle(
                                        color=ft.Colors.BLACK_87,
                                        shape=ft.RoundedRectangleBorder(radius=14),
                                    ),
                                    on_click=toggle_options,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            spacing=6,
                        ),
                        option_panel,
                    ],
                    spacing=8,
                ),
                bgcolor=ft.Colors.WHITE,
                padding=10,
                border_radius=12,
                border=ft.Border.all(1, ft.Colors.GREY_300),
            ),
            ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Column(
                                    [
                                        no_photo_box,
                                        photo_preview,
                                        ft.TextButton(
                                            "사진 업로드",
                                            icon=ft.Icons.UPLOAD_FILE,
                                            style=ft.ButtonStyle(color=ft.Colors.BLUE_800),
                                            on_click=on_upload_photo_click,
                                        ),
                                    ],
                                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                    spacing=2,
                                ),
                                ft.Column([comparison_list], expand=True, spacing=0),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.START,
                            spacing=8,
                        ),
                        ft.Button(
                            "재고 추가 (바로 등록)",
                            icon=ft.Icons.ADD_CIRCLE_OUTLINE,
                            bgcolor=ft.Colors.GREEN_600,
                            color=ft.Colors.WHITE,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=14)),
                            on_click=on_add_inventory,
                        ),
                        photo_path_input,
                        extra_fields_box,
                        status_text,
                    ],
                    spacing=8,
                ),
                bgcolor=ft.Colors.WHITE,
                padding=10,
                border_radius=12,
                border=ft.Border.all(1, ft.Colors.GREY_300),
            ),
            register_card,
            ft.Container(height=48),
        ],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
        spacing=8,
    )