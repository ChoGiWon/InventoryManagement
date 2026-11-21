from datetime import datetime
import flet as ft
from domain_service import get_all_inventory_items


def _classify_category(item: dict) -> str:
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


def build_temp2_page(page: ft.Page) -> ft.Control:
    today = datetime.now().date()
    items = get_all_inventory_items()

    total_qty = sum(int(it.get("quantity") or 0) for it in items)
    expiring_soon = []
    expired_items = []
    cat_counts = {"아이스크림": 0, "음료수": 0, "과자": 0, "기타": 0}

    for it in items:
        cat = _classify_category(it)
        cat_counts[cat] = cat_counts.get(cat, 0) + int(it.get("quantity") or 0)

        exp_str = str(it.get("expiry_date") or "").strip()
        try:
            exp_dt = datetime.strptime(exp_str, "%Y-%m-%d").date()
            diff_days = (exp_dt - today).days
            enriched = dict(it)
            enriched["diff_days"] = diff_days
            enriched["category_label"] = cat
            if diff_days < 0:
                expired_items.append(enriched)
            elif diff_days <= 7:
                expiring_soon.append(enriched)
        except ValueError:
            pass

    expiring_soon.sort(key=lambda x: x.get("diff_days", 999))
    expired_items.sort(key=lambda x: x.get("diff_days", 0))
    alert_entries = expired_items + expiring_soon

    state = {
        "selected_id": alert_entries[0]["id"] if alert_entries else None,
    }

    alerts_column = ft.Column(spacing=8)
    selected_detail_column = ft.Column(spacing=6)

    def _on_select_alert(item_id: int):
        state["selected_id"] = item_id
        _render_alerts_and_detail()
        page.update()

    def _render_selected_detail():
        selected_detail_column.controls.clear()
        chosen = next((it for it in alert_entries if it.get("id") == state["selected_id"]), None)
        if not chosen:
            return

        dd = chosen.get("diff_days", 0)
        if dd < 0:
            dd_text = f"유통기한 {abs(dd)}일 경과 (만료)"
        elif dd == 0:
            dd_text = "오늘 마감 (D-Day)"
        else:
            dd_text = f"만료까지 {dd}일 남음 (D-{dd})"

        selected_detail_column.controls.append(
            ft.Container(
                content=ft.Column(
                    [
                        ft.Text("선택한 알림 제품 상세 정보", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_900),
                        ft.Text(f"• 제품명: {chosen.get('prdlst_nm', '-')}", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK_87),
                        ft.Text(f"• 상태: {dd_text}", size=12, weight=ft.FontWeight.W_600, color=ft.Colors.RED_800 if dd < 0 else ft.Colors.ORANGE_900),
                        ft.Text(f"• 분류: {chosen.get('category_label', '기타')}  |  바코드: {chosen.get('bar_cd', '-')}", size=12, color=ft.Colors.BLACK_87),
                        ft.Text(f"• 유통기한: {chosen.get('expiry_date', '-')}  |  수량: {chosen.get('quantity', 0)}개", size=12, color=ft.Colors.BLACK_87),
                        ft.Text(f"• 보관위치: {chosen.get('location', '-')}  |  거래처: {chosen.get('supplier') or '-'}", size=12, color=ft.Colors.BLACK_87),
                        ft.Text(f"• 등록일: {chosen.get('created_at') or '-'}  |  메모: {chosen.get('memo') or '-'}", size=12, color=ft.Colors.GREY_800),
                    ],
                    spacing=4,
                ),
                bgcolor=ft.Colors.BLUE_50,
                border=ft.Border.all(1, ft.Colors.BLUE_200),
                border_radius=10,
                padding=10,
            )
        )

    def _render_alerts_and_detail():
        alerts_column.controls.clear()
        if not alert_entries:
            alerts_column.controls.append(
                ft.Text("7일 이내 임박 또는 만료된 재고 품목이 없습니다.", size=13, color=ft.Colors.GREY_800)
            )
            selected_detail_column.controls.clear()
            return

        for it in alert_entries:
            iid = it.get("id")
            is_sel = iid == state["selected_id"]
            dd = it["diff_days"]
            is_expired = dd < 0
            badge_text = f"만료 +{abs(dd)}일" if is_expired else ("오늘 마감" if dd == 0 else f"D-{dd}")

            alerts_column.controls.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text(
                                        f"{'✔ ' if is_sel else ''}{it.get('prdlst_nm', '-')}",
                                        size=14,
                                        weight=ft.FontWeight.BOLD,
                                        color=ft.Colors.BLUE_900 if is_sel else (ft.Colors.RED_900 if is_expired else ft.Colors.ORANGE_900),
                                        expand=True,
                                    ),
                                    ft.Container(
                                        content=ft.Text(
                                            badge_text,
                                            size=11,
                                            weight=ft.FontWeight.BOLD,
                                            color=ft.Colors.WHITE if is_expired else ft.Colors.BLACK_87,
                                        ),
                                        bgcolor=ft.Colors.RED_700 if is_expired else ft.Colors.AMBER_200,
                                        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                        border_radius=6,
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            ft.Text(
                                f"유통기한: {it.get('expiry_date', '-')} | 수량: {it.get('quantity', 0)}개 | 위치: {it.get('location', '-')}",
                                size=12,
                                color=ft.Colors.BLACK_87,
                            ),
                        ],
                        spacing=4,
                    ),
                    bgcolor=ft.Colors.BLUE_50 if is_sel else (ft.Colors.RED_50 if is_expired else ft.Colors.AMBER_50),
                    border=ft.Border.all(2 if is_sel else 1, ft.Colors.BLUE_600 if is_sel else (ft.Colors.RED_200 if is_expired else ft.Colors.AMBER_300)),
                    border_radius=8,
                    padding=10,
                    on_click=lambda _, item_id=iid: _on_select_alert(item_id),
                )
            )

        _render_selected_detail()

    _render_alerts_and_detail()

    return ft.Column(
        [
            ft.Container(
                content=ft.Column(
                    [
                        ft.Text("재고 통계 요약", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK_87),
                        ft.Row(
                            [
                                ft.Text(f"• 전체 품목: {len(items)}건", size=13, weight=ft.FontWeight.W_600, color=ft.Colors.BLACK_87, expand=True),
                                ft.Text(f"• 총 수량: {total_qty}개", size=13, weight=ft.FontWeight.W_600, color=ft.Colors.BLUE_900, expand=True),
                            ]
                        ),
                        ft.Row(
                            [
                                ft.Text(f"• 임박(7일 이내): {len(expiring_soon)}건", size=13, weight=ft.FontWeight.W_600, color=ft.Colors.ORANGE_900, expand=True),
                                ft.Text(f"• 만료: {len(expired_items)}건", size=13, weight=ft.FontWeight.W_600, color=ft.Colors.RED_800, expand=True),
                            ]
                        ),
                        ft.Divider(height=8, color=ft.Colors.GREY_300),
                        ft.Text("분류별 보유 수량", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK_87),
                        ft.Text(
                            f"아이스크림 {cat_counts['아이스크림']}개  |  음료수 {cat_counts['음료수']}개  |  과자 {cat_counts['과자']}개  |  기타 {cat_counts['기타']}개",
                            size=12,
                            color=ft.Colors.GREY_800,
                        ),
                    ],
                    spacing=6,
                ),
                bgcolor=ft.Colors.WHITE,
                padding=12,
                border_radius=12,
                border=ft.Border.all(1, ft.Colors.GREY_300),
            ),
            ft.Container(
                content=ft.Column(
                    [
                        ft.Text("유통기한 임박 · 만료 알림 목록 (항목 탭 시 아래 상세 표시)", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.BLACK_87),
                        alerts_column,
                        selected_detail_column,
                    ],
                    spacing=8,
                ),
                bgcolor=ft.Colors.WHITE,
                padding=12,
                border_radius=12,
                border=ft.Border.all(1, ft.Colors.GREY_300),
            ),
            ft.Container(height=48),
        ],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
        spacing=10,
    )