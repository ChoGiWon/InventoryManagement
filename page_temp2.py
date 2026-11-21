import flet as ft


def build_temp2_page(page: ft.Page) -> ft.Control:
    return ft.Container(
        content=ft.Column(
            [
                ft.Icon(ft.Icons.EXTENSION, size=48, color=ft.Colors.BLUE_GREY_400),
                ft.Text("2번 메뉴 (확장 모듈 영역)", size=18, weight=ft.FontWeight.BOLD),
                ft.Text(
                    "추후 통계, 유통기한 임박 알림 목록, 또는 추가 기능을 독립적으로 연결할 수 있는 페이지입니다.",
                    size=13,
                    color=ft.Colors.GREY_700,
                    text_align=ft.TextAlign.CENTER,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=10,
        ),
        expand=True,
        padding=20,
        bgcolor=ft.Colors.WHITE,
        border_radius=10,
        alignment=ft.alignment.center,
    )