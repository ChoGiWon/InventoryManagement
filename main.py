import os
import flet as ft
from database import init_db, get_meta, set_meta
from page_main import build_main_page
from page_calendar import build_calendar_page
from page_temp2 import build_temp2_page
from page_inventory import build_inventory_page
from page_settings import build_settings_page


def _configure_fonts(page: ft.Page) -> str:
    fonts = {}
    malgun_regular = "C:/Windows/Fonts/malgun.ttf"
    malgun_bold = "C:/Windows/Fonts/malgunbd.ttf"
    if os.path.exists(malgun_regular):
        fonts["MalgunGothic"] = malgun_regular
    if os.path.exists(malgun_bold):
        fonts["MalgunGothicBold"] = malgun_bold

    font_family = "MalgunGothic" if fonts else ""
    if fonts:
        page.fonts = fonts

    page.theme = ft.Theme(
        font_family=font_family if font_family else None,
        color_scheme_seed=ft.Colors.BLUE,
    )
    return font_family


def _open_dialog(page: ft.Page, dialog: ft.AlertDialog):
    if dialog not in page.overlay:
        page.overlay.append(dialog)
    dialog.open = True
    page.update()


def _check_camera_permission_if_needed(page: ft.Page):
    # 이미 카메라 권한 설정이 저장되어 있으면 다시 묻지 않음
    configured = get_meta("camera_permission_status", "")
    if configured in ("granted", "denied"):
        return

    def set_choice(status_value: str):
        set_meta("camera_permission_status", status_value)
        perm_dialog.open = False
        snack_msg = (
            "카메라 사용이 허용되었습니다. 바코드 스캔을 사용할 수 있습니다."
            if status_value == "granted"
            else "카메라 권한이 미허용으로 저장되었습니다. (설정에서 변경 가능)"
        )
        snack = ft.SnackBar(ft.Text(snack_msg, color=ft.Colors.WHITE), bgcolor=ft.Colors.GREY_900)
        if snack not in page.overlay:
            page.overlay.append(snack)
        snack.open = True
        page.update()

    perm_dialog = ft.AlertDialog(
        modal=True,
        bgcolor=ft.Colors.WHITE,
        title=ft.Text("카메라 접근 권한 안내", weight=ft.FontWeight.BOLD, size=16, color=ft.Colors.BLACK_87),
        content=ft.Text(
            "제품 바코드를 카메라로 인식하기 위해 카메라 접근 허용이 필요합니다.\n"
            "설정을 저장하면 다음 실행부터는 다시 묻지 않습니다.",
            size=13,
            color=ft.Colors.BLACK_87,
        ),
        actions=[
            ft.TextButton(
                "허용 안 함",
                style=ft.ButtonStyle(color=ft.Colors.GREY_800),
                on_click=lambda _: set_choice("denied"),
            ),
            ft.Button(
                "카메라 허용",
                bgcolor=ft.Colors.BLUE_700,
                color=ft.Colors.WHITE,
                on_click=lambda _: set_choice("granted"),
            ),
        ],
    )
    _open_dialog(page, perm_dialog)


def main(page: ft.Page):
    init_db()

    page.title = "스마트 재고·유통기한 관리"
    page.bgcolor = ft.Colors.GREY_100
    page.padding = 0

    page.window.width = 412
    page.window.height = 915
    page.window.resizable = True

    _configure_fonts(page)
    content_holder = ft.Container(
        expand=True,
        padding=ft.Padding.only(left=8, right=8, top=8, bottom=44),
    )
    nav_buttons: dict[str, ft.Container] = {}
    nav_labels: dict[str, ft.Text] = {}

    def show_info_popup(e):
        app_ver = get_meta("app_version", "1.0.0")
        b_ver = get_meta("barcode_api_updated_at", "미다운로드")
        r_ver = get_meta("report_api_updated_at", "미다운로드")

        def close_popup(_):
            info_dialog.open = False
            page.update()

        info_dialog = ft.AlertDialog(
            modal=False,
            bgcolor=ft.Colors.WHITE,
            title=ft.Text("앱 및 버전 정보", weight=ft.FontWeight.BOLD, size=16, color=ft.Colors.BLACK_87),
            content=ft.Column(
                [
                    ft.Text("• 개발자: 기원 (개인 로컬 DB 기반 재고관리)", size=13, color=ft.Colors.BLACK_87),
                    ft.Text(f"• 앱 버전: v{app_ver}", size=13, color=ft.Colors.BLACK_87),
                    ft.Divider(height=10, color=ft.Colors.GREY_300),
                    ft.Text("• 내부 DB 데이터 기준일(버전):", weight=ft.FontWeight.BOLD, size=13, color=ft.Colors.BLACK_87),
                    ft.Text(f"  - 바코드연계제품정보: {b_ver}", size=12, color=ft.Colors.GREY_800),
                    ft.Text(f"  - 식품(첨가물)품목제조보고: {r_ver}", size=12, color=ft.Colors.GREY_800),
                ],
                tight=True,
                spacing=6,
            ),
            actions=[
                ft.TextButton(
                    "닫기",
                    style=ft.ButtonStyle(color=ft.Colors.BLUE_800),
                    on_click=close_popup,
                )
            ],
        )
        _open_dialog(page, info_dialog)

    def _sync_menu_styles(active_route: str):
        for route, cell in nav_buttons.items():
            is_active = route == active_route
            cell.bgcolor = ft.Colors.BLUE_600 if is_active else ft.Colors.GREY_100
            cell.border = ft.Border.all(
                1,
                ft.Colors.BLUE_700 if is_active else ft.Colors.GREY_300,
            )
            lbl = nav_labels.get(route)
            if lbl:
                lbl.color = ft.Colors.WHITE if is_active else ft.Colors.BLACK_87
                lbl.weight = ft.FontWeight.BOLD if is_active else ft.FontWeight.W_600

    def switch_page(route_name: str):
        if route_name == "main":
            content_holder.content = build_main_page(page)
        elif route_name == "calendar":
            content_holder.content = build_calendar_page(page)
        elif route_name == "alerts_stats":
            content_holder.content = build_temp2_page(page)
        elif route_name == "inventory":
            content_holder.content = build_inventory_page(page)
        elif route_name == "settings":
            content_holder.content = build_settings_page(page)
        _sync_menu_styles(route_name)
        page.update()

    def _build_menu_pill(route_name: str, title: str) -> ft.Container:
        txt = ft.Text(
            title,
            size=11,
            weight=ft.FontWeight.W_600,
            color=ft.Colors.BLACK_87,
            max_lines=1,
            no_wrap=True,
        )
        nav_labels[route_name] = txt
        cell = ft.Container(
            content=txt,
            expand=True,
            height=34,
            alignment=ft.Alignment.CENTER,
            bgcolor=ft.Colors.GREY_100,
            border=ft.Border.all(1, ft.Colors.GREY_300),
            border_radius=17,
            padding=ft.Padding.symmetric(horizontal=2),
            on_click=lambda _, r=route_name: switch_page(r),
        )
        nav_buttons[route_name] = cell
        return cell

    status_bar_safe_area = ft.Container(
        height=30,
        bgcolor=ft.Colors.GREY_900,
    )

    top_menu_bar = ft.Container(
        content=ft.Row(
            [
                _build_menu_pill("main", "메인"),
                _build_menu_pill("calendar", "달력"),
                _build_menu_pill("alerts_stats", "알림·통계"),
                _build_menu_pill("inventory", "재고"),
                _build_menu_pill("settings", "설정"),
                ft.Container(
                    content=ft.IconButton(
                        icon=ft.Icons.INFO_OUTLINE,
                        icon_color=ft.Colors.BLUE_800,
                        icon_size=18,
                        padding=0,
                        tooltip="개발자 및 버전 정보",
                        on_click=show_info_popup,
                    ),
                    width=32,
                    height=34,
                    alignment=ft.Alignment.CENTER,
                    bgcolor=ft.Colors.BLUE_50,
                    border_radius=17,
                ),
            ],
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=ft.Colors.WHITE,
        padding=ft.Padding.symmetric(horizontal=6, vertical=6),
        border=ft.Border.only(bottom=ft.BorderSide(1, ft.Colors.GREY_300)),
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

    page.update()
    switch_page("main")
    _check_camera_permission_if_needed(page)


if __name__ == "__main__":
    ft.run(main)