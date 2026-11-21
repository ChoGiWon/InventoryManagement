import calendar
from datetime import datetime
import flet as ft
from domain_service import get_calendar_month_summary, delete_inventory_item


FIXED_SOLAR_HOLIDAYS = {
    "01-01": "신정",
    "03-01": "삼일절",
    "05-05": "어린이날",
    "06-06": "현충일",
    "08-15": "광복절",
    "10-03": "개천절",
    "10-09": "한글날",
    "12-25": "성탄절",
}

HOLIDAYS_BY_DATE = {
    "2026-01-01": "신정",
    "2026-02-16": "설날연휴",
    "2026-02-17": "설날",
    "2026-02-18": "설날연휴",
    "2026-03-01": "삼일절",
    "2026-03-02": "대체공휴일(삼일절)",
    "2026-05-05": "어린이날",
    "2026-05-24": "부처님오신날",
    "2026-05-25": "대체공휴일(부처님오신날)",
    "2026-06-06": "현충일",
    "2026-08-15": "광복절",
    "2026-08-17": "대체공휴일(광복절)",
    "2026-09-24": "추석연휴",
    "2026-09-25": "추석",
    "2026-09-26": "추석연휴",
    "2026-10-03": "개천절",
    "2026-10-05": "대체공휴일(개천절)",
    "2026-10-09": "한글날",
    "2026-12-25": "성탄절",
}


def _get_holiday_name(d_str: str) -> str:
    if d_str in HOLIDAYS_BY_DATE:
        return HOLIDAYS_BY_DATE[d_str]
    mm_dd = d_str[5:]
    return FIXED_SOLAR_HOLIDAYS.get(mm_dd, "")


def build_calendar_page(page: ft.Page) -> ft.Control:
    today_dt = datetime.now().date()
    today_str = today_dt.strftime("%Y-%m-%d")

    state = {
        "year": today_dt.year,
        "month": today_dt.month,
        "selected_date": today_str,
        "selected_item_id": None,
    }

    title_text = ft.Text("", size=17, weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK_87)
    grid_column = ft.Column(spacing=5)
    selected_date_title = ft.Text(
        "",
        size=13,
        weight=ft.FontWeight.BOLD,
        color=ft.Colors.BLUE_900,
        expand=True,
    )
    day_items_column = ft.Column(spacing=6)
    item_detail_column = ft.Column(spacing=6)

    def _on_delete_item(item_id: int):
        delete_inventory_item(item_id)
        if state["selected_item_id"] == item_id:
            state["selected_item_id"] = None
        refresh_calendar()

    def _on_select_day(d_str: str):
        state["selected_date"] = d_str
        state["selected_item_id"] = None
        refresh_calendar()

    def _on_select_item(item_id: int):
        state["selected_item_id"] = item_id
        refresh_calendar()

    def _prev_month(e):
        y, m = state["year"], state["month"]
        if m == 1:
            state["year"], state["month"] = y - 1, 12
        else:
            state["month"] = m - 1
        state["selected_date"] = f"{state['year']:04d}-{state['month']:02d}-01"
        state["selected_item_id"] = None
        refresh_calendar()

    def _next_month(e):
        y, m = state["year"], state["month"]
        if m == 12:
            state["year"], state["month"] = y + 1, 1
        else:
            state["month"] = m + 1
        state["selected_date"] = f"{state['year']:04d}-{state['month']:02d}-01"
        state["selected_item_id"] = None
        refresh_calendar()

    def _render_item_detail(day_items: list[dict]):
        item_detail_column.controls.clear()
        chosen = next((it for it in day_items if it.get("id") == state["selected_item_id"]), None)
        if not chosen:
            return

        item_detail_column.controls.append(
            ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text("선택한 제품 상세 정보", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_900, expand=True),
                                ft.TextButton(
                                    "삭제",
                                    icon=ft.Icons.DELETE_OUTLINE,
                                    style=ft.ButtonStyle(color=ft.Colors.RED_700),
                                    on_click=lambda _, iid=chosen.get("id"): _on_delete_item(iid),
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        ft.Text(f"• 제품명: {chosen.get('prdlst_nm', '-')}", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK_87),
                        ft.Text(f"• 바코드: {chosen.get('bar_cd', '-')}", size=12, color=ft.Colors.BLACK_87),
                        ft.Text(f"• 유통기한: {chosen.get('expiry_date', '-')}  |  수량: {chosen.get('quantity', 0)}개", size=12, color=ft.Colors.BLACK_87),
                        ft.Text(f"• 보관위치: {chosen.get('location', '-')}", size=12, color=ft.Colors.BLACK_87),
                        ft.Text(f"• 메모: {chosen.get('memo') or '-'}", size=12, color=ft.Colors.GREY_800),
                    ],
                    spacing=4,
                ),
                bgcolor=ft.Colors.BLUE_50,
                border=ft.Border.all(1, ft.Colors.BLUE_200),
                border_radius=10,
                padding=10,
            )
        )

    def refresh_calendar():
        y, m = state["year"], state["month"]
        title_text.value = f"{y}년 {m}월 재고관리 달력"
        summary = get_calendar_month_summary(y, m)

        grid_column.controls.clear()
        weekday_names = ["일", "월", "화", "수", "목", "금", "토"]
        header_cells = []
        for idx, w_name in enumerate(weekday_names):
            w_color = ft.Colors.RED_700 if idx == 0 else (ft.Colors.BLUE_700 if idx == 6 else ft.Colors.BLACK_87)
            header_cells.append(
                ft.Container(
                    content=ft.Text(w_name, size=12, weight=ft.FontWeight.BOLD, color=w_color),
                    expand=True,
                    alignment=ft.Alignment.CENTER,
                    padding=ft.Padding.symmetric(vertical=4),
                )
            )
        grid_column.controls.append(ft.Row(header_cells, spacing=4))

        cal = calendar.Calendar(firstweekday=6)
        month_weeks = cal.monthdatescalendar(y, m)

        for week in month_weeks:
            week_cells = []
            for d_obj in week:
                in_month = (d_obj.month == m)
                d_str = d_obj.strftime("%Y-%m-%d")
                is_today = (d_obj == today_dt)
                is_selected = (d_str == state["selected_date"])
                holiday_name = _get_holiday_name(d_str)
                is_sunday = (d_obj.weekday() == 6)
                is_saturday = (d_obj.weekday() == 5)
                day_info = summary.get(d_str)

                if not in_month:
                    week_cells.append(ft.Container(expand=True, height=62))
                    continue

                if is_today:
                    bg_col = ft.Colors.AMBER_100
                    border_col = ft.Colors.AMBER_700 if not is_selected else ft.Colors.BLUE_700
                    border_w = 2
                elif is_selected:
                    bg_col = ft.Colors.BLUE_50
                    border_col = ft.Colors.BLUE_700
                    border_w = 2
                else:
                    bg_col = ft.Colors.WHITE
                    border_col = ft.Colors.GREY_200
                    border_w = 1

                if is_sunday or bool(holiday_name):
                    num_color = ft.Colors.RED_700
                elif is_saturday:
                    num_color = ft.Colors.BLUE_700
                else:
                    num_color = ft.Colors.BLACK_87

                cell_children = [
                    ft.Text(
                        str(d_obj.day),
                        size=13,
                        weight=ft.FontWeight.BOLD,
                        color=num_color,
                    )
                ]

                if holiday_name:
                    cell_children.append(
                        ft.Text(
                            holiday_name,
                            size=9,
                            weight=ft.FontWeight.W_600,
                            color=ft.Colors.RED_700,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        )
                    )

                if day_info:
                    badge_txt = f"{day_info['count']}건({day_info['total_qty']})"
                    badge_bg = ft.Colors.RED_100 if day_info["expired"] > 0 else (ft.Colors.AMBER_100 if day_info["soon"] > 0 else ft.Colors.BLUE_100)
                    badge_fg = ft.Colors.RED_900 if day_info["expired"] > 0 else (ft.Colors.ORANGE_900 if day_info["soon"] > 0 else ft.Colors.BLUE_900)
                    cell_children.append(
                        ft.Container(
                            content=ft.Text(badge_txt, size=9, weight=ft.FontWeight.BOLD, color=badge_fg, max_lines=1, no_wrap=True),
                            bgcolor=badge_bg,
                            border_radius=4,
                            padding=ft.Padding.symmetric(horizontal=3, vertical=1),
                        )
                    )

                week_cells.append(
                    ft.Container(
                        content=ft.Column(cell_children, spacing=2, alignment=ft.MainAxisAlignment.START),
                        expand=True,
                        height=62,
                        bgcolor=bg_col,
                        border=ft.Border.all(border_w, border_col),
                        border_radius=8,
                        padding=4,
                        on_click=lambda _, ds=d_str: _on_select_day(ds),
                    )
                )
            grid_column.controls.append(ft.Row(week_cells, spacing=4))

        sel_str = state["selected_date"]
        sel_holiday = _get_holiday_name(sel_str)
        holiday_suffix = f" ({sel_holiday})" if sel_holiday else ""
        selected_date_title.value = f"{sel_str}{holiday_suffix} 재고 목록 (제품 선택 시 아래 상세 표시)"

        day_items = (summary.get(sel_str) or {}).get("items") or []
        day_items_column.controls.clear()
        if not day_items:
            day_items_column.controls.append(
                ft.Text("해당 날짜에 마감되는 재고 품목이 없습니다.", size=13, color=ft.Colors.GREY_800)
            )
        else:
            for it in day_items:
                iid = it.get("id")
                is_sel = iid == state["selected_item_id"]
                day_items_column.controls.append(
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Column(
                                    [
                                        ft.Text(
                                            f"{'✔ ' if is_sel else ''}{it.get('prdlst_nm', '-')}",
                                            size=13,
                                            weight=ft.FontWeight.BOLD,
                                            color=ft.Colors.BLUE_900 if is_sel else ft.Colors.BLACK_87,
                                        ),
                                        ft.Text(
                                            f"수량: {it.get('quantity', 0)}개 | 위치: {it.get('location', '-')} | 바코드: {it.get('bar_cd', '-')}",
                                            size=11,
                                            color=ft.Colors.GREY_800,
                                        ),
                                    ],
                                    spacing=2,
                                    expand=True,
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.DELETE_OUTLINE,
                                    icon_color=ft.Colors.RED_700,
                                    tooltip="삭제",
                                    on_click=lambda _, item_id=iid: _on_delete_item(item_id),
                                ),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        bgcolor=ft.Colors.BLUE_50 if is_sel else ft.Colors.WHITE,
                        border=ft.Border.all(2 if is_sel else 1, ft.Colors.BLUE_600 if is_sel else ft.Colors.GREY_300),
                        border_radius=8,
                        padding=ft.Padding.only(left=10, right=4, top=6, bottom=6),
                        on_click=lambda _, item_id=iid: _on_select_item(item_id),
                    )
                )

        _render_item_detail(day_items)
        page.update()

    refresh_calendar()

    return ft.Column(
        [
            ft.Container(
                content=ft.Row(
                    [
                        ft.IconButton(icon=ft.Icons.CHEVRON_LEFT, icon_color=ft.Colors.BLACK_87, on_click=_prev_month),
                        title_text,
                        ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT, icon_color=ft.Colors.BLACK_87, on_click=_next_month),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                bgcolor=ft.Colors.WHITE,
                padding=ft.Padding.symmetric(horizontal=6, vertical=4),
                border_radius=12,
                border=ft.Border.all(1, ft.Colors.GREY_300),
            ),
            ft.Container(
                content=grid_column,
                bgcolor=ft.Colors.WHITE,
                padding=8,
                border_radius=12,
                border=ft.Border.all(1, ft.Colors.GREY_300),
            ),
            ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Icon(ft.Icons.EVENT_NOTE, size=18, color=ft.Colors.BLUE_800),
                                selected_date_title,
                            ],
                            spacing=6,
                            vertical_alignment=ft.CrossAxisAlignment.START,
                        ),
                        day_items_column,
                    ],
                    spacing=8,
                ),
                bgcolor=ft.Colors.WHITE,
                padding=10,
                border_radius=12,
                border=ft.Border.all(1, ft.Colors.GREY_300),
            ),
            item_detail_column,
            ft.Container(height=48),
        ],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
        spacing=10,
    )