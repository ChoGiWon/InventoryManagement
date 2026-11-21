import calendar
from datetime import datetime
import flet as ft
from domain_service import get_calendar_month_summary


def build_calendar_page(page: ft.Page) -> ft.Control:
    now = datetime.now()
    cal_state = {
        "year": now.year,
        "month": now.month,
        "selected_date": now.strftime("%Y-%m-%d"),
        "summary": {},
    }

    month_title = ft.Text("", size=18, weight=ft.FontWeight.BOLD)
    grid_col = ft.Column(spacing=4)
    detail_title = ft.Text("", size=15, weight=ft.FontWeight.BOLD)
    detail_list = ft.Column(spacing=6)

    def render_selected_day_details():
        sel = cal_state["selected_date"]
        detail_title.value = f"📅 {sel} 재고 상세 내역"
        detail_list.controls.clear()

        day_info = cal_state["summary"].get(sel)
        if not day_info or not day_info["items"]:
            detail_list.controls.append(
                ft.Text("해당 날짜에 마감되는 재고 품목이 없습니다.", size=13, color=ft.Colors.GREY_600)
            )
        else:
            for item in day_info["items"]:
                detail_list.controls.append(
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Column(
                                    [
                                        ft.Text(item["prdlst_nm"], weight=ft.FontWeight.BOLD, size=14),
                                        ft.Text(f"바코드: {item['bar_cd']} | 위치: {item['location']}", size=12, color=ft.Colors.GREY_700),
                                    ],
                                    expand=True,
                                    spacing=2,
                                ),
                                ft.Container(
                                    content=ft.Text(f"수량 {item['quantity']}개", weight=ft.FontWeight.BOLD, size=13, color=ft.Colors.BLUE_900),
                                    padding=ft.padding.symmetric(horizontal=10, vertical=6),
                                    bgcolor=ft.Colors.BLUE_50,
                                    border_radius=8,
                                ),
                            ]
                        ),
                        padding=10,
                        bgcolor=ft.Colors.WHITE,
                        border=ft.border.all(1, ft.Colors.GREY_300),
                        border_radius=8,
                    )
                )
        page.update()

    def render_calendar():
        y, m = cal_state["year"], cal_state["month"]
        month_title.value = f"{y}년 {m:02d}월 재고관리 달력"
        cal_state["summary"] = get_calendar_month_summary(y, m)

        grid_col.controls.clear()
        weekdays = ["일", "월", "화", "수", "목", "금", "토"]
        header_row = ft.Row(
            [
                ft.Container(
                    content=ft.Text(
                        w,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.RED_600 if i == 0 else (ft.Colors.BLUE_600 if i == 6 else ft.Colors.BLACK87),
                    ),
                    expand=True,
                    alignment=ft.alignment.center,
                )
                for i, w in enumerate(weekdays)
            ],
            spacing=2,
        )
        grid_col.controls.append(header_row)

        cal = calendar.Calendar(firstweekday=6)  # 일요일 시작
        for week in cal.monthdayscalendar(y, m):
            week_cells = []
            for day in week:
                if day == 0:
                    week_cells.append(ft.Container(expand=True, height=62))
                else:
                    date_str = f"{y:04d}-{m:02d}-{day:02d}"
                    info = cal_state["summary"].get(date_str)
                    is_selected = (date_str == cal_state["selected_date"])

                    badges = []
                    if info:
                        if info["expired"] > 0:
                            badges.append(ft.Text(f"만료 {info['expired']}", size=10, color=ft.Colors.RED_700, weight=ft.FontWeight.BOLD))
                        if info["soon"] > 0:
                            badges.append(ft.Text(f"임박 {info['soon']}", size=10, color=ft.Colors.ORANGE_800, weight=ft.FontWeight.BOLD))
                        badges.append(ft.Text(f"총 {info['total_qty']}개", size=10, color=ft.Colors.BLUE_800))

                    def make_day_click(d_target):
                        def on_click(e):
                            cal_state["selected_date"] = d_target
                            render_calendar()
                        return on_click

                    week_cells.append(
                        ft.Container(
                            content=ft.Column(
                                [ft.Text(str(day), size=12, weight=ft.FontWeight.BOLD)] + badges,
                                spacing=1,
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            expand=True,
                            height=62,
                            padding=3,
                            bgcolor=ft.Colors.BLUE_100 if is_selected else (ft.Colors.AMBER_50 if info else ft.Colors.WHITE),
                            border=ft.border.all(2 if is_selected else 1, ft.Colors.BLUE_700 if is_selected else ft.Colors.GREY_300),
                            border_radius=6,
                            on_click=make_day_click(date_str),
                        )
                    )
            grid_col.controls.append(ft.Row(week_cells, spacing=2))

        render_selected_day_details()

    def move_month(delta: int):
        m = cal_state["month"] + delta
        y = cal_state["year"]
        if m < 1:
            m = 12
            y -= 1
        elif m > 12:
            m = 1
            y += 1
        cal_state["year"] = y
        cal_state["month"] = m
        render_calendar()

    render_calendar()

    return ft.Column(
        [
            ft.Container(
                content=ft.Row(
                    [
                        ft.IconButton(ft.Icons.CHEVRON_LEFT, on_click=lambda _: move_month(-1)),
                        month_title,
                        ft.IconButton(ft.Icons.CHEVRON_RIGHT, on_click=lambda _: move_month(1)),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                bgcolor=ft.Colors.WHITE,
                border_radius=8,
                padding=ft.padding.symmetric(horizontal=8, vertical=2),
            ),
            ft.Container(
                content=grid_col,
                bgcolor=ft.Colors.WHITE,
                border_radius=8,
                padding=8,
                border=ft.border.all(1, ft.Colors.GREY_300),
            ),
            ft.Container(
                content=ft.Column([detail_title, detail_list], spacing=8),
                bgcolor=ft.Colors.GREY_50,
                border_radius=8,
                padding=10,
                border=ft.border.all(1, ft.Colors.GREY_300),
            ),
        ],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
        spacing=10,
    )