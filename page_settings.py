import os
import threading
import flet as ft
from database import get_meta, set_meta, EXPORT_DIR
from domain_service import download_public_dataset, export_inventory_csv_for_pc


def build_settings_page(page: ft.Page) -> ft.Control:
    folder_path_text = ft.Text(f"현재 지정 폴더: {get_meta('custom_folder_path', EXPORT_DIR)}", size=12, color=ft.Colors.GREY_800)
    barcode_ver_text = ft.Text(f"최종 다운로드(버전): {get_meta('barcode_api_updated_at', '미다운로드')}", size=12, color=ft.Colors.BLUE_900)
    report_ver_text = ft.Text(f"최종 다운로드(버전): {get_meta('report_api_updated_at', '미다운로드')}", size=12, color=ft.Colors.BLUE_900)

    # 1번째 버튼: 로컬 폴더 생성 및 PC 전송용 파일 내보내기
    def on_create_folder(e):
        target_dir = get_meta("custom_folder_path", EXPORT_DIR)
        os.makedirs(target_dir, exist_ok=True)
        set_meta("custom_folder_path", target_dir)
        folder_path_text.value = f"현재 지정 폴더: {target_dir}"
        page.update()
        page.open(ft.SnackBar(ft.Text(f"모바일 전용 관리 폴더가 준비되었습니다:\n{target_dir}")))

    def on_export_for_email(e):
        csv_path = export_inventory_csv_for_pc()
        page.open(
            ft.AlertDialog(
                title=ft.Text("PC 활용용 내보내기 완료"),
                content=ft.Text(
                    f"아래 경로에 CSV 파일이 생성되었습니다.\n이메일 앱으로 첨부해 PC에서 내려받아 활용하세요.\n\n{csv_path}",
                    size=13,
                ),
                actions=[ft.TextButton("확인", on_click=lambda _: page.close(page.dialog))],
            )
        )

    # 페이지형 OpenAPI 안내 팝업 생성기
    def open_api_guide_popup(title: str, search_keyword: str, key_filename: str, dataset_type: str, target_btn: ft.ElevatedButton, ver_label: ft.Text):
        folder = get_meta("custom_folder_path", EXPORT_DIR)
        guide_pages = [
            {
                "step": "1 / 3 단계 : 공공데이터 포털 접속 및 로그인",
                "body": (
                    "1. 스마트폰 또는 PC 브라우저에서 [식품안전나라 공공데이터활용] 또는 [공공데이터포털]에 접속합니다.\n"
                    "2. 회원가입 후 로그인을 진행합니다.\n"
                    "3. 상단 메뉴의 [데이터공개] 또는 검색창으로 이동합니다."
                ),
            },
            {
                "step": "2 / 3 단계 : 검색어 입력 및 OpenAPI 신청",
                "body": (
                    f"1. 포털 검색창에 아래 검색어를 정확히 입력합니다.\n"
                    f"   ▶ 검색어: '{search_keyword}'\n"
                    "2. 검색 결과 선택 후 [Open-API 이용신청] 또는 [활용신청]을 눌러 인증키를 발급받습니다."
                ),
            },
            {
                "step": "3 / 3 단계 : 인증키 파일 저장 규칙 (필수)",
                "body": (
                    f"1. 발급받은 인증키 문자열을 메모장(텍스트 파일)에 붙여넣습니다.\n"
                    f"2. 지정된 폴더 경로:\n   {folder}\n"
                    f"3. 저장할 파일명 및 형식:\n   ▶ 파일명: {key_filename} (UTF-8 텍스트 형식)\n"
                    "4. 저장 완료 후 아래 [지금 다운로드 실행] 버튼을 눌러 내부 DB에 적재합니다."
                ),
            },
        ]

        popup_state = {"idx": 0}
        step_title = ft.Text(guide_pages[0]["step"], weight=ft.FontWeight.BOLD, size=15, color=ft.Colors.BLUE_900)
        step_body = ft.Text(guide_pages[0]["body"], size=13)

        prev_btn = ft.OutlinedButton("이전", disabled=True)
        next_btn = ft.OutlinedButton("다음", disabled=False)

        def sync_guide_ui():
            idx = popup_state["idx"]
            step_title.value = guide_pages[idx]["step"]
            step_body.value = guide_pages[idx]["body"]
            prev_btn.disabled = (idx == 0)
            next_btn.disabled = (idx == len(guide_pages) - 1)
            page.update()

        def go_prev(e):
            if popup_state["idx"] > 0:
                popup_state["idx"] -= 1
                sync_guide_ui()

        def go_next(e):
            if popup_state["idx"] < len(guide_pages) - 1:
                popup_state["idx"] += 1
                sync_guide_ui()

        prev_btn.on_click = go_prev
        next_btn.on_click = go_next

        def trigger_download(e):
            # 중복 클릭 방지 및 실행 중 상태 표시
            if target_btn.disabled:
                return
            orig_text = target_btn.text
            target_btn.disabled = True
            target_btn.text = "다운로드 실행 중... (잠시만 기다려주세요)"
            page.close(dialog)
            page.update()

            def worker():
                ok, msg = download_public_dataset(dataset_type)
                target_btn.disabled = False
                target_btn.text = orig_text
                if dataset_type == "barcode":
                    ver_label.value = f"최종 다운로드(버전): {get_meta('barcode_api_updated_at', '미다운로드')}"
                else:
                    ver_label.value = f"최종 다운로드(버전): {get_meta('report_api_updated_at', '미다운로드')}"
                page.open(ft.SnackBar(ft.Text(msg)))
                page.update()

            threading.Thread(target=worker, daemon=True).start()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"{title} 안내", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column(
                    [
                        step_title,
                        ft.Divider(height=10),
                        step_body,
                    ],
                    spacing=8,
                ),
                width=360,
                height=210,
            ),
            actions=[
                prev_btn,
                next_btn,
                ft.ElevatedButton("지금 다운로드 실행", icon=ft.Icons.DOWNLOAD, on_click=trigger_download),
                ft.TextButton("닫기", on_click=lambda _: page.close(dialog)),
            ],
        )
        page.open(dialog)

    btn_folder = ft.ElevatedButton(
        "1. 로컬 폴더 생성 (자료 저장 및 관리)",
        icon=ft.Icons.CREATE_NEW_FOLDER,
        on_click=on_create_folder,
    )

    btn_barcode_dl = ft.ElevatedButton(
        "2. 바코드연계제품정보 다운로드",
        icon=ft.Icons.QR_CODE,
    )
    btn_barcode_dl.on_click = lambda _: open_api_guide_popup(
        title="바코드연계제품정보 다운로드",
        search_keyword="바코드연계제품정보",
        key_filename="barcode_api_key.txt",
        dataset_type="barcode",
        target_btn=btn_barcode_dl,
        ver_label=barcode_ver_text,
    )

    btn_report_dl = ft.ElevatedButton(
        "3. 식품(첨가물)품목제조보고 다운로드",
        icon=ft.Icons.INVENTORY_2,
    )
    btn_report_dl.on_click = lambda _: open_api_guide_popup(
        title="식품(첨가물)품목제조보고 다운로드",
        search_keyword="식품(첨가물)품목제조보고",
        key_filename="food_report_api_key.txt",
        dataset_type="report",
        target_btn=btn_report_dl,
        ver_label=report_ver_text,
    )

    return ft.Column(
        [
            ft.Text("설정 및 로컬 데이터 관리", size=18, weight=ft.FontWeight.BOLD),

            # 1번째 버튼 카드
            ft.Container(
                content=ft.Column(
                    [
                        btn_folder,
                        folder_path_text,
                        ft.OutlinedButton(
                            "모바일 자료 CSV 생성 (이메일 전송 -> PC 활용)",
                            icon=ft.Icons.EMAIL,
                            on_click=on_export_for_email,
                        ),
                    ],
                    spacing=8,
                ),
                padding=12,
                bgcolor=ft.Colors.WHITE,
                border_radius=10,
                border=ft.border.all(1, ft.Colors.GREY_300),
            ),

            # 2번째 버튼 카드
            ft.Container(
                content=ft.Column(
                    [
                        btn_barcode_dl,
                        barcode_ver_text,
                    ],
                    spacing=6,
                ),
                padding=12,
                bgcolor=ft.Colors.WHITE,
                border_radius=10,
                border=ft.border.all(1, ft.Colors.GREY_300),
            ),

            # 3번째 버튼 카드
            ft.Container(
                content=ft.Column(
                    [
                        btn_report_dl,
                        report_ver_text,
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
        spacing=12,
    )