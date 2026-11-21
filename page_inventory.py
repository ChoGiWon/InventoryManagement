import os
from datetime import datetime
import flet as ft
from domain_service import (
    get_all_inventory_items,
    delete_inventory_item,
    add_inventory_item,
)


def _detect_category(item: dict) -> str:
    saved_cat = str(item.get("category") or "").strip()
    if saved_cat in ("아이스크림", "음료수", "과자", "기타"):
        return saved_cat

    text = f"{item.get('prdlst_nm', '')} {item.get('prdlst_dcnm', '')}".lower()
    if any(k in text for k in ["아이스", "빙과", "젤라또", "ice"]):
        return "아이스크림"
    if any(k in text for k in ["음료", "주스", "콜라", "사이다", "커피", "차", "우유", "두유", "생수", "물"]):
        return "음료수"
    if any(k in text for k in ["과자", "스낵", "비스킷", "쿠키", "초코", "캔디", "사탕", "칩", "웨이퍼"]):
        return "과자"
    return "기타"


def build_inventory_page(page: ft.Page) -> ft.Control:
    today_str = datetime.now().strftime("%Y-%m-%d")

    state = {
        "search": "",
        "category": "전체",
        "ascending": True,
        "selected_id": None,
        "show_add_form": False,
    }

    categories = ["전체", "아이스크림", "음료수", "과자", "기타"]
    register_categories = ["과자", "아이스크림", "음료수", "기타"]

    search_input = ft.TextField(
        label="제품·바코드·거래처 검색",
        hint_text="검색어 입력",
        value="",
        color=ft.Colors.BLACK_87,
        label_style=ft.TextStyle(color=ft.Colors.GREY_800, size=12, weight=ft.FontWeight.W_600),
        hint_style=ft.TextStyle(color=ft.Colors.GREY_500, size=12),
        expand=True,
        text_size=13,
        content_padding=ft.Padding.symmetric(horizontal=10, vertical=7),
    )

    new_category_dropdown = ft.Dropdown(
        label="분류",
        value="과자",
        width=116,
        text_size=13,
        color=ft.Colors.BLACK_87,
        label_style=ft.TextStyle(color=ft.Colors.GREY_800, size=12, weight=ft.FontWeight.W_600),
        options=[ft.dropdown.Option(c) for c in register_categories],
        content_padding=ft.Padding.symmetric(horizontal=8, vertical=6),
    )
    new_name_input = ft.TextField(
        label="제품명",
        hint_text="예: 감자면 / 아이스크림",
        value="",
        color=ft.Colors.BLACK_87,
        label_style=ft.TextStyle(color=ft.Colors.GREY_800, size=12, weight=ft.FontWeight.W_600),
        expand=True,
        text_size=13,
        content_padding=ft.Padding.symmetric(horizontal=8, vertical=6),
    )
    new_barcode_input = ft.TextField(
        label="바코드",
        hint_text="바코드 번호",
        value="",
        color=ft.Colors.BLACK_87,
        label_style=ft.TextStyle(color=ft.Colors.GREY_800, size=12, weight=ft.FontWeight.W_600),
        width=130,
        text_size=13,
        content_padding=ft.Padding.symmetric(horizontal=8, vertical=6),
    )
    new_supplier_input = ft.TextField(
        label="거래처 정보",
        hint_text="거래처명 입력",
        value="",
        color=ft.Colors.BLACK_87,
        label_style=ft.TextStyle(color=ft.Colors.GREY_800, size=12, weight=ft.FontWeight.W_600),
        expand=True,
        text_size=13,
        content_padding=ft.Padding.symmetric(horizontal=8, vertical=6),
    )
    new_expiry_input = ft.TextField(
        label="유통기한",
        value=today_str,
        color=ft.Colors.BLACK_87,
        label_style=ft.TextStyle(color=ft.Colors.GREY_800, size=12, weight=ft.FontWeight.W_600),
        width=112,
        text_size=13,
        content_padding=ft.Padding.symmetric(horizontal=8, vertical=6),
    )
    new_qty_input = ft.TextField(
        label="수량",
        value="1",
        color=ft.Colors.BLACK_87,
        label_style=ft.TextStyle(color=ft.Colors.GREY_800, size=12, weight=ft.FontWeight.W_600),
        width=56,
        text_size=13,
        content_padding=ft.Padding.symmetric(horizontal=6, vertical=6),
    )
    new_loc_input = ft.TextField(
        label="위치",
        value="창고A",
        color=ft.Colors.BLACK_87,
        label_style=ft.TextStyle(color=ft.Colors.GREY_800, size=12, weight=ft.FontWeight.W_600),
        expand=True,
        text_size=13,
        content_padding=ft.Padding.symmetric(horizontal=8, vertical=6),
    )

    add_form_panel = ft.Container(
        content=ft.Column(
            [
                ft.Text("새 재고 및 거래처 등록", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK_87),
                ft.Row([new_category_dropdown, new_name_input], spacing=8),
                ft.Row([new_barcode_input, new_supplier_input], spacing=8),
                ft.Row([new_expiry_input, new_qty_input, new_loc_input], spacing=8),
                ft.Button(
                    "목록에 추가",
                    icon=ft.Icons.ADD,
                    bgcolor=ft.Colors.GREEN_600,
                    color=ft.Colors.WHITE,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
                    on_click=lambda _: _on_save_new_item(),
                ),
            ],
            spacing=8,
        ),
        bgcolor=ft.Colors.GREY_50,
        padding=10,
        border_radius=10,
        border=ft.Border.all(1, ft.Colors.GREY_300),
        visible=False,
    )

    filter_row = ft.Row(spacing=6, scroll=ft.ScrollMode.AUTO)
    sort_label = ft.Text("정렬: 오름차순 (유통기한)", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK_87)
    summary_label = ft.Text("", size=12, weight=ft.FontWeight.W_600, color=ft.Colors.BLUE_900)
    detail_column = ft.Column(spacing=6)
    list_column = ft.Column(spacing=8)

    def _show_snack(msg: str, is_error: bool = False):
        snack = ft.SnackBar(
            ft.Text(msg, color=ft.Colors.WHITE),
            bgcolor=ft.Colors.RED_700 if is_error else ft.Colors.BLUE_800,
        )
        if snack not in page.overlay:
            page.overlay.append(snack)
        snack.open = True
        page.update()

    def _on_save_new_item():
        cat_val = new_category_dropdown.value or "과자"
        name_val = (new_name_input.value or "").strip()
        bar_val = (new_barcode_input.value or "").strip()
        supp_val = (new_supplier_input.value or "").strip()
        exp_val = (new_expiry_input.value or today_str).strip()
        loc_val = (new_loc_input.value or "창고A").strip() or "창고A"
        try:
            qty_val = max(1, int((new_qty_input.value or "1").strip()))
        except ValueError:
            qty_val = 1

        if not name_val and not bar_val:
            _show_snack("제품명 또는 바코드를 입력하세요.", is_error=True)
            return

        final_bar = bar_val or f"NO_BARCODE_{datetime.now().strftime('%H%M%S')}"
        final_name = name_val or f"미등록상품({final_bar})"
        add_inventory_item(
            bar_cd=final_bar,
            prdlst_nm=final_name,
            expiry_date=exp_val,
            quantity=qty_val,
            location=loc_val,
            supplier=supp_val,
            category=cat_val,
        )
        new_name_input.value = ""
        new_barcode_input.value = ""
        new_supplier_input.value = ""
        state["show_add_form"] = False
        add_form_panel.visible = False
        _show_snack(f"등록 완료: [{cat_val}] {final_name}", is_error=False)
        refresh_view()

    def _toggle_add_form(e):
        state["show_add_form"] = not state["show_add_form"]
        add_form_panel.visible = state["show_add_form"]
        page.update()

    def _on_search_change(e):
        state["search"] = (e.control.value or "").strip().lower()
        refresh_view()

    search_input.on_change = _on_search_change

    def _on_delete(item_id: int):
        delete_inventory_item(item_id)
        if state["selected_id"] == item_id:
            state["selected_id"] = None
        refresh_view()

    def _on_close_detail(e=None):
        state["selected_id"] = None
        refresh_view()

    def _on_select(item_id: int):
        state["selected_id"] = item_id
        refresh_view()

    def _toggle_sort(e):
        state["ascending"] = not state["ascending"]
        refresh_view()

    def _set_category(cat: str):
        state["category"] = cat
        state["selected_id"] = None
        refresh_view()

    def _render_filter_buttons():
        filter_row.controls.clear()
        for cat in categories:
            active = state["category"] == cat
            filter_row.controls.append(
                ft.Container(
                    content=ft.Text(
                        cat,
                        size=12,
                        weight=ft.FontWeight.BOLD if active else ft.FontWeight.W_600,
                        color=ft.Colors.WHITE if active else ft.Colors.BLACK_87,
                        max_lines=1,
                        no_wrap=True,
                    ),
                    bgcolor=ft.Colors.BLUE_600 if active else ft.Colors.GREY_100,
                    border=ft.Border.all(1, ft.Colors.BLUE_700 if active else ft.Colors.GREY_300),
                    border_radius=16,
                    padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                    on_click=lambda _, c=cat: _set_category(c),
                )
            )

    def _build_thumb(item: dict) -> ft.Container:
        p_path = str(item.get("photo_path") or "").strip()
        if p_path and os.path.exists(p_path):
            content = ft.Image(
                src=p_path,
                width=58,
                height=58,
                fit=ft.BoxFit.CONTAIN,
                border_radius=6,
            )
        else:
            content = ft.Column(
                [
                    ft.Icon(ft.Icons.INVENTORY_2_OUTLINED, size=20, color=ft.Colors.GREY_600),
                    ft.Text("사진 없음", size=9, color=ft.Colors.GREY_600),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=2,
            )
        return ft.Container(
            content=content,
            width=62,
            height=62,
            bgcolor=ft.Colors.GREY_100,
            border=ft.Border.all(1, ft.Colors.GREY_300),
            border_radius=8,
            alignment=ft.Alignment.CENTER,
        )

    def _render_detail(filtered_items: list[dict]):
        detail_column.controls.clear()
        chosen = next((it for it in filtered_items if it.get("id") == state["selected_id"]), None)
        if not chosen:
            return

        cat_name = _detect_category(chosen)
        supp_val = chosen.get("supplier") or "-"
        detail_column.controls.append(
            ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text("선택한 제품 상세 정보", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_900, expand=True),
                                ft.TextButton(
                                    "닫기",
                                    icon=ft.Icons.CLOSE,
                                    style=ft.ButtonStyle(color=ft.Colors.GREY_800),
                                    on_click=_on_close_detail,
                                ),
                                ft.TextButton(
                                    "삭제",
                                    icon=ft.Icons.DELETE_OUTLINE,
                                    style=ft.ButtonStyle(color=ft.Colors.RED_700),
                                    on_click=lambda _, iid=chosen.get("id"): _on_delete(iid),
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            spacing=2,
                        ),
                        ft.Text(f"• 제품명: {chosen.get('prdlst_nm', '-')}", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK_87),
                        ft.Text(f"• 분류: {cat_name}  |  식품유형: {chosen.get('prdlst_dcnm') or '-'}", size=12, color=ft.Colors.BLACK_87),
                        ft.Text(f"• 바코드: {chosen.get('bar_cd', '-')}", size=12, color=ft.Colors.BLACK_87),
                        ft.Text(f"• 거래처: {supp_val}", size=12, weight=ft.FontWeight.W_600, color=ft.Colors.BLACK_87),
                        ft.Text(f"• 유통기한: {chosen.get('expiry_date', '-')}  |  수량: {chosen.get('quantity', 0)}개", size=12, color=ft.Colors.BLACK_87),
                        ft.Text(f"• 보관위치: {chosen.get('location', '-')}  |  등록일: {chosen.get('created_at') or '-'}", size=12, color=ft.Colors.BLACK_87),
                        ft.Text(f"• 메모: {chosen.get('memo') or '-'}", size=12, color=ft.Colors.GREY_800),
                    ],
                    spacing=4,
                ),
                bgcolor=ft.Colors.BLUE_50,
                padding=10,
                border_radius=10,
                border=ft.Border.all(1, ft.Colors.BLUE_200),
            )
        )

    def refresh_view():
        _render_filter_buttons()
        sort_label.value = f"정렬: {'오름차순' if state['ascending'] else '내림차순'} (유통기한)"

        all_items = get_all_inventory_items()
        q = state["search"]
        filtered = []
        for it in all_items:
            if state["category"] != "전체" and _detect_category(it) != state["category"]:
                continue
            if q:
                haystack = f"{it.get('prdlst_nm', '')} {it.get('bar_cd', '')} {it.get('supplier', '')} {it.get('location', '')} {_detect_category(it)}".lower()
                if q not in haystack:
                    continue
            filtered.append(it)

        filtered = sorted(
            filtered,
            key=lambda x: (str(x.get("expiry_date") or ""), int(x.get("id") or 0)),
            reverse=not state["ascending"],
        )

        total_qty = sum(int(it.get("quantity") or 0) for it in filtered)
        summary_label.value = f"{len(filtered)} 품목수  ·  {total_qty} 총수량"

        list_column.controls.clear()
        if not filtered:
            list_column.controls.append(
                ft.Text("검색 또는 분류 조건에 맞는 재고 품목이 없습니다.", size=13, color=ft.Colors.GREY_800)
            )
        else:
            for it in filtered:
                iid = it.get("id")
                is_sel = iid == state["selected_id"]
                cat_badge = _detect_category(it)
                supp_text = f"거래처: {it['supplier']}" if it.get("supplier") else "거래처: 미지정"

                card_body = ft.Row(
                    [
                        _build_thumb(it),
                        ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Text(
                                            f"{cat_badge} · {it.get('expiry_date', '-')}",
                                            size=11,
                                            weight=ft.FontWeight.W_600,
                                            color=ft.Colors.GREY_700,
                                        ),
                                        ft.Container(
                                            content=ft.Text(
                                                f"▦ {it.get('bar_cd', '-')}",
                                                size=10,
                                                color=ft.Colors.GREY_800,
                                                max_lines=1,
                                                no_wrap=True,
                                            ),
                                            bgcolor=ft.Colors.GREY_100,
                                            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                            border_radius=4,
                                        ),
                                    ],
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                ),
                                ft.Text(
                                    f"{'✔ ' if is_sel else ''}{it.get('prdlst_nm', '-')}",
                                    size=14,
                                    weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.BLUE_900 if is_sel else ft.Colors.BLACK_87,
                                ),
                                ft.Text(
                                    f"📍 {it.get('location', '-')}  |  {supp_text}",
                                    size=11,
                                    color=ft.Colors.GREY_800,
                                ),
                                ft.Row(
                                    [
                                        ft.Text(
                                            f"{it.get('quantity', 0)} 개",
                                            size=13,
                                            weight=ft.FontWeight.BOLD,
                                            color=ft.Colors.BLUE_800,
                                        ),
                                        ft.IconButton(
                                            icon=ft.Icons.DELETE_OUTLINE,
                                            icon_color=ft.Colors.RED_700,
                                            icon_size=18,
                                            padding=0,
                                            tooltip="삭제",
                                            on_click=lambda _, item_id=iid: _on_delete(item_id),
                                        ),
                                    ],
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                ),
                            ],
                            expand=True,
                            spacing=3,
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.START,
                    spacing=10,
                )

                list_column.controls.append(
                    ft.Container(
                        content=card_body,
                        bgcolor=ft.Colors.BLUE_50 if is_sel else ft.Colors.WHITE,
                        border=ft.Border.all(2 if is_sel else 1, ft.Colors.BLUE_600 if is_sel else ft.Colors.GREY_300),
                        border_radius=10,
                        padding=10,
                        on_click=lambda _, item_id=iid: _on_select(item_id),
                    )
                )

        _render_detail(filtered)
        page.update()

    refresh_view()

    return ft.Column(
        [
            ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text("전체 재고 관리", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK_87, expand=True),
                                ft.Button(
                                    "재고·거래처 등록",
                                    icon=ft.Icons.ADD,
                                    bgcolor=ft.Colors.BLUE_700,
                                    color=ft.Colors.WHITE,
                                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=12)),
                                    on_click=_toggle_add_form,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        search_input,
                        filter_row,
                        add_form_panel,
                        ft.Row(
                            [
                                sort_label,
                                ft.OutlinedButton(
                                    "오름/내림차순",
                                    icon=ft.Icons.SORT,
                                    style=ft.ButtonStyle(
                                        color=ft.Colors.BLACK_87,
                                        shape=ft.RoundedRectangleBorder(radius=12),
                                    ),
                                    on_click=_toggle_sort,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        summary_label,
                    ],
                    spacing=8,
                ),
                bgcolor=ft.Colors.WHITE,
                padding=10,
                border_radius=12,
                border=ft.Border.all(1, ft.Colors.GREY_300),
            ),
            detail_column,
            ft.Container(
                content=ft.Column(
                    [
                        ft.Text("재고 품목 목록 (카드 선택 시 위 상세 갱신)", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK_87),
                        list_column,
                    ],
                    spacing=8,
                ),
                bgcolor=ft.Colors.WHITE,
                padding=10,
                border_radius=12,
                border=ft.Border.all(1, ft.Colors.GREY_300),
            ),
            ft.Container(height=48),
        ],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
        spacing=10,
    )