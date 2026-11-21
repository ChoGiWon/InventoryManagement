import flet as ft
from database import init_db, get_meta
from page_main import build_main_page
from page_calendar import build_calendar_page
from page_temp2 import build_temp2_page
from page_settings import build_settings_page


def main(page: ft.Page):
    init_db()

    page.title = "스마트 재고·유통기한 관리"
    page.bgcolor = ft.Colors.GREY_100
    page.padding = 0

    content_holder = ft.Container(expand=True, padding=10)

    def show_info_popup(e):
        app_ver = get_meta("app_version", "1.0.0")
        b_ver = get_meta("barcode_api_updated_at", "미다운로드")
        r_ver = get_meta("report_api_updated_at", "미다운로드")

        info_dialog = ft.AlertDialog(
            title=ft.Text("앱 및 버전 정보", weight=ft.FontWeight.BOLD),
            content=ft.Column(
                [
                    ft.Text("• 개발자: 기원 (개인 로컬 DB 기반 재고관리)", size=13),
                    ft.Text(f"• 앱 버전: v{app_ver}", size=13),
                    ft.Divider(height=10),
                    ft.Text("• 내부 DB 데이터 기준일(버전):", weight=ft.FontWeight.BOLD, size=13),
                    ft.Text(f"  - 바코드연계제품정보: {b_ver}", size=12),
                    ft.Text(f"  - 식품(첨가물)품목제조보고: {r_ver}", size=12),
                ],
                tight=True,
                spacing=6,
            ),
            actions=[ft.TextButton("닫기", on_click=lambda _: page.close(info_dialog))],
        )
        page.open(info_dialog)

    def switch_page(route_name: str):
        if route_name == "main":
            content_holder.content = build_main_page(page)
        elif route_name == "menu1":
            content_holder.content = build_calendar_page(page)
        elif route_name == "menu2":
            content_holder.content = build_temp2_page(page)
        elif route_name == "menu3":
            content_holder.content = build_settings_page(page)
        page.update()

    # 모바일 상단 상태바(시계/배터리) 여백 + 명암 배경
    status_bar_safe_area = ft.Container(
        height=32,
        bgcolor=ft.Colors.BLUE_GREY_900,
    )

    # 상단 메뉴(메인 + 1, 2, 3) 및 우측 개발자/버전 정보 버튼
    top_menu_bar = ft.Container(
        content=ft.Row(
            [
                ft.Row(
                    [
                        ft.TextButton("메인", on_click=lambda _: switch_page("main"), style=ft.ButtonStyle(color=ft.Colors.WHITE)),
                        ft.TextButton("1.달력", on_click=lambda _: switch_page("menu1"), style=ft.ButtonStyle(color=ft.Colors.WHITE)),
                        ft.TextButton("2.메뉴", on_click=lambda _: switch_page("menu2"), style=ft.ButtonStyle(color=ft.Colors.WHITE)),
                        ft.TextButton("3.설정", on_click=lambda _: switch_page("menu3"), style=ft.ButtonStyle(color=ft.Colors.WHITE)),
                    ],
                    spacing=2,
                ),
                ft.IconButton(
                    icon=ft.Icons.INFO_OUTLINE,
                    icon_color=ft.Colors.WHITE,
                    tooltip="개발자 및 버전 정보",
                    on_click=show_info_popup,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        bgcolor=ft.Colors.BLUE_GREY_800,
        padding=ft.padding.symmetric(horizontal=6, vertical=2),
    )

    page.add(
        ft.Column(
            [
                status_bar_safe_area,
                top_menu_bar,
                content_holder,
            ],
            spacing=0,
            expand=True,
        )
    )

    switch_page("main")


if __name__ == "__main__":
    ft.app(target=main)