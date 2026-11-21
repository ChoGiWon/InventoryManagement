import os
import flet as ft
from domain_service import (
    lookup_and_compare_barcode,
    save_uploaded_product_photo,
    get_checked_extra_fields,
    get_all_option_preferences,
    update_option_preference,
    add_inventory_item,
)


def build_main_page(page: ft.Page) -> ft.Control:
    state = {
        "current_bar_cd": "8801062000012",
        "current_db_record": {},
        "option_panel_open": False,
    }

    barcode_input = ft.TextField(
        label="바코드 번호 (스캔 또는 직접 입력)",
        value="8801062000012",
        expand=True,
        dense=True,
    )
    scanned_name_input = ft.TextField(
        label="스캔 수신 제품명 (비교 테스트용)",
        value="쵸코카라멜",
        expand=True,
        dense=True,
    )

    photo_preview = ft.Image(
        src="",
        width=110,
        height=110,
        fit=ft.ImageFit.CONTAIN,
        visible=False,
    )
    no_photo_box = ft.Container(
        content=ft.Column(
            [
                ft.Icon(ft.Icons.IMAGE_NOT_SUPPORTED, size=32, color=ft.Colors.GREY_500),
                ft.Text("DB 사진 없음", size=11, color=ft.Colors.GREY_600),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=4,
        ),
        width=110,
        height=110,
        bgcolor=ft.Colors.GREY_200,
        border_radius=8,
        alignment=ft.alignment.center,
        visible=True,
    )

    comparison_list_col = ft.Column(spacing=6)
    extra_bottom_col = ft.Column(spacing=4)
    option_drawer_container = ft.Container(visible=False)

    # 재고 빠른 등록 입력 필드
    expiry_input = ft.TextField(label="유통기한 (YYYY-MM-DD)", value="2026-12-31", width=150, dense=True)
    qty_input = ft.TextField(label="수량", value="1", width=70, dense=True)
    loc_input = ft.TextField(label="보관위치", value="냉장고", width=110, dense=True)

    def on_photo_picked(e: ft.FilePickerResultEvent):
        if e.files and len(e.files) > 0:
            picked_path = e.files[0].path
            bar_cd = barcode_input.value.strip()
            if bar_cd and picked_path:
                saved_path = save_uploaded_product_photo(bar_cd, picked_path)
                refresh_scan_view()
                page.open(ft.SnackBar(ft.Text(f"제품 사진이 내부 DB에 저장되었습니다: {os.path.basename(saved_path)}")))

    file_picker = ft.FilePicker(on_result=on_photo_picked)
    page.overlay.append(file_picker)

    def render_extra_bottom():
        extra_bottom_col.controls.clear()
        extras = get_checked_extra_fields(state["current_db_record"])
        if not extras:
            extra_bottom_col.controls.append(
                ft.Text("우측 [옵션] 버튼에서 추가 표시할 항목을 체크하세요.", size=12, color=ft.Colors.GREY_600)
            )
        else:
            for item in extras:
                extra_bottom_col.controls.append(
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Text(f"• {item['label']}:", weight=ft.FontWeight.BOLD, size=13, width=145),
                                ft.Text(str(item["value"]), size=13, expand=True),
                            ]
                        ),
                        padding=ft.padding.symmetric(vertical=4, horizontal=8),
                        bgcolor=ft.Colors.BLUE_50,
                        border_radius=6,
                    )
                )
        page.update()

    def build_option_panel():
        prefs = get_all_option_preferences()
        checkbox_controls = [
            ft.Text("추가 표시 항목 선택", weight=ft.FontWeight.BOLD, size=14),
            ft.Divider(height=8),
        ]
        for p in prefs:
            def make_handler(k):
                def on_change(ev):
                    update_option_preference(k, ev.control.value)
                    render_extra_bottom()
                return on_change

            checkbox_controls.append(
                ft.Checkbox(
                    label=p["field_label"],
                    value=(p["is_checked"] == 1),
                    on_change=make_handler(p["field_key"]),
                )
            )

        option_drawer_container.content = ft.Container(
            content=ft.Column(checkbox_controls, spacing=2),
            padding=10,
            bgcolor=ft.Colors.GREY_100,
            border=ft.border.all(1, ft.Colors.GREY_400),
            border_radius=8,
            width=210,
        )

    def toggle_option_panel(e):
        state["option_panel_open"] = not state["option_panel_open"]
        if state["option_panel_open"]:
            build_option_panel()
        option_drawer_container.visible = state["option_panel_open"]
        page.update()

    def refresh_scan_view(e=None):
        bar_cd = barcode_input.value.strip()
        state["current_bar_cd"] = bar_cd
        scanned = {
            "bar_cd": bar_cd,
            "prdlst_nm": scanned_name_input.value.strip(),
        }
        result = lookup_and_compare_barcode(scanned)
        state["current_db_record"] = result["db_record"]

        # 사진 표시 처리 (DB 우선 / 없으면 업로드 버튼 유도)
        if result["photo_path"]:
            photo_preview.src = result["photo_path"]
            photo_preview.visible = True
            no_photo_box.visible = False
        else:
            photo_preview.visible = False
            no_photo_box.visible = True

        # 항목별 비교 및 불일치 표시
        comparison_list_col.controls.clear()
        for comp in result["comparisons"]:
            badge_color = ft.Colors.RED_600 if comp["is_mismatch"] else ft.Colors.GREEN_700
            badge_bg = ft.Colors.RED_50 if comp["is_mismatch"] else ft.Colors.GREEN_50
            comparison_list_col.controls.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Text(comp["label"], weight=ft.FontWeight.BOLD, size=13, width=115),
                            ft.Text(comp["scanned_val"], size=13, expand=True),
                            ft.Container(
                                content=ft.Text(comp["status"], size=11, color=badge_color, weight=ft.FontWeight.BOLD),
                                padding=ft.padding.symmetric(horizontal=8, vertical=3),
                                bgcolor=badge_bg,
                                border_radius=12,
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.padding.symmetric(vertical=4, horizontal=6),
                    border=ft.border.only(bottom=ft.BorderSide(1, ft.Colors.GREY_200)),
                )
            )

        render_extra_bottom()

    def on_save_to_inventory(e):
        bar_cd = barcode_input.value.strip()
        nm = scanned_name_input.value.strip() or (state["current_db_record"].get("prdlst_nm") or "미지정 제품")
        exp = expiry_input.value.strip()
        try:
            qty = int(qty_input.value.strip())
        except ValueError:
            qty = 1
        loc = loc_input.value.strip() or "기본보관함"
        add_inventory_item(bar_cd, nm, exp, qty, loc)
        page.open(ft.SnackBar(ft.Text(f"[{nm}] 재고 및 달력에 등록되었습니다 ({exp})")))

    refresh_scan_view()

    return ft.Column(
        [
            # 바코드 인식 입력 영역
            ft.Container(
                content=ft.Column(
                    [
                        ft.Row([barcode_input, scanned_name_input]),
                        ft.Row(
                            [
                                ft.ElevatedButton(
                                    "바코드 인식 / DB 비교",
                                    icon=ft.Icons.QR_CODE_SCANNER,
                                    on_click=refresh_scan_view,
                                ),
                                ft.OutlinedButton(
                                    "옵션",
                                    icon=ft.Icons.TUNE,
                                    on_click=toggle_option_panel,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                    ],
                    spacing=8,
                ),
                padding=12,
                bgcolor=ft.Colors.WHITE,
                border_radius=10,
                border=ft.border.all(1, ft.Colors.GREY_300),
            ),

            # 본문: 좌측 제품 정보 & 사진 / 우측 옵션 패널
            ft.Row(
                [
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Column(
                                            [
                                                photo_preview,
                                                no_photo_box,
                                                ft.TextButton(
                                                    "사진 업로드",
                                                    icon=ft.Icons.UPLOAD_FILE,
                                                    on_click=lambda _: file_picker.pick_files(
                                                        allow_multiple=False,
                                                        file_type=ft.FilePickerFileType.IMAGE,
                                                    ),
                                                ),
                                            ],
                                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                        ),
                                        ft.Container(content=comparison_list_col, expand=True),
                                    ],
                                    vertical_alignment=ft.CrossAxisAlignment.START,
                                    spacing=12,
                                ),
                                ft.Divider(height=12),
                                ft.Text("옵션 선택 추가 정보 (내부 DB)", weight=ft.FontWeight.BOLD, size=13, color=ft.Colors.BLUE_900),
                                extra_bottom_col,
                            ],
                            spacing=8,
                        ),
                        padding=12,
                        bgcolor=ft.Colors.WHITE,
                        border_radius=10,
                        border=ft.border.all(1, ft.Colors.GREY_300),
                        expand=True,
                    ),
                    option_drawer_container,
                ],
                vertical_alignment=ft.CrossAxisAlignment.START,
                spacing=8,
            ),

            # 달력 연동 빠른 재고 등록 바
            ft.Container(
                content=ft.Column(
                    [
                        ft.Text("재고 및 달력 등록", weight=ft.FontWeight.BOLD, size=13),
                        ft.Row(
                            [
                                expiry_input,
                                qty_input,
                                loc_input,
                                ft.ElevatedButton("재고 추가", icon=ft.Icons.ADD, on_click=on_save_to_inventory),
                            ],
                            wrap=True,
                        ),
                    ],
                    spacing=6,
                ),
                padding=12,
                bgcolor=ft.Colors.WHITE,
                border_radius=10,
                border=ft.border.all(1, ft.Colors.GREY_300),
            ),
        ],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
        spacing=10,
    )