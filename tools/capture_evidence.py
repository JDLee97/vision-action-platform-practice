"""T01~T10 화면 증거를 자동으로 캡처한다 (Playwright).

전제: docker compose up 으로 5개 서비스 + fakecam(demo 프로필) 실행, create_demo_users 실행 완료.
실행: python tools/capture_evidence.py   → docs/evidence/*.png
"""

import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.getenv("BASE_URL", "http://localhost:8000")
PASSWORD = os.getenv("DEMO_USER_PASSWORD", "VisionAi!2026")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "evidence"
SAMPLES = ROOT / "samples"
OUT.mkdir(parents=True, exist_ok=True)


def login(page, username):
    page.goto(f"{BASE}/accounts/login/")
    page.fill("#id_username", username)
    page.fill("#id_password", PASSWORD)
    page.click("button[type=submit]")
    page.wait_for_url(f"{BASE}/analyses/")


def wait_finished(page, timeout=180_000):
    page.wait_for_function(
        "() => { const s = document.querySelector('.step[data-stage=done]'); "
        "return s && (s.classList.contains('success') || s.classList.contains('failure')); }",
        timeout=timeout,
    )
    page.wait_for_timeout(800)


def upload(page, filename, expected="", title=""):
    page.click(".tab[data-mode=upload]")
    page.set_input_files("#video-file", str(SAMPLES / filename))
    page.select_option("#expected-action", expected)
    page.fill("#job-title", title)
    start_and_wait(page)


def start_and_wait(page, before_finish=None):
    page.click("#start-button")
    # 클릭하면 화면이 새 작업 상태로 초기화되므로, 새 작업 ID가 표시될 때까지 기다린 뒤 완료를 기다린다.
    page.wait_for_function("() => /작업 #\\d+/.test(document.getElementById('job-label').textContent)", timeout=30_000)
    if before_finish:
        before_finish()
    wait_finished(page)


def main():
    only = set(sys.argv[1:])
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 1440, "height": 1000}, device_scale_factor=1, locale="ko-KR")
        page = context.new_page()

        # 회원가입 화면
        page.goto(f"{BASE}/accounts/signup/")
        page.screenshot(path=OUT / "00_signup.png")

        login(page, "student01")

        if not only or "upload" in only:
            # T02 정상 분석 (학습 영상 S01 wave)
            upload(page, "S01_wave_train.mp4", "wave", "T02 손 흔들기 업로드")
            page.screenshot(path=OUT / "T02_upload_success.png", full_page=True)

            # T04 두 사람 (SBU hugging)
            upload(page, "02_sbu_hugging.mp4", "", "T04 두 사람 영상")
            page.screenshot(path=OUT / "T04_two_people.png")

            # T09 잘못된 파일 / 사람 없는 영상
            upload(page, "broken.mp4", "", "T09 손상된 파일")
            page.screenshot(path=OUT / "T09_broken_file.png")
            upload(page, "no_person.mp4", "", "T09 사람 없는 영상")
            page.screenshot(path=OUT / "T09_no_person.png")

            # 수업 10일차 영상 몇 개 추가 (대시보드 통계용)
            for name, action in [("a10_s05_e02.mp4", "leg_raise_lower"), ("a12_s07_e03.mp4", "drink_return"),
                                 ("a18_s07_e03.mp4", "sit_stand"), ("a02_s09_e01.mp4", "bend_return")]:
                upload(page, name, action, f"10일차 {name}")

        if not only or "webcam" in only:
            # T03 IP Webcam (가짜 카메라 → 8초 수집)
            page.click(".tab[data-mode=ipwebcam]")
            page.wait_for_selector("#preview-image:not([hidden])", timeout=20_000)
            page.wait_for_timeout(1500)
            page.screenshot(path=OUT / "T03_ipwebcam_preview.png")
            page.select_option("#expected-action", "wave")
            page.fill("#job-title", "T03 IP Webcam 8초 수집")
            def shot_collecting():
                page.wait_for_selector(".step[data-stage=collecting].current", timeout=30_000)
                page.wait_for_timeout(1500)
                page.screenshot(path=OUT / "T03_ipwebcam_collecting.png")

            start_and_wait(page, shot_collecting)
            page.screenshot(path=OUT / "T03_ipwebcam_success.png")

        # T06 새로고침 후에도 이력 유지
        page.reload()
        page.wait_for_selector("#history-body tr[data-id]")
        page.locator("#history-body").scroll_into_view_if_needed()
        page.screenshot(path=OUT / "T06_history_after_reload.png", full_page=True)

        # T07 다른 회원(student02)은 student01의 작업을 볼 수 없음
        other = browser.new_context(viewport={"width": 1200, "height": 700}, locale="ko-KR")
        other_page = other.new_page()
        login(other_page, "student02")
        first_id = page.locator("#history-body tr[data-id]").last.get_attribute("data-id")
        other_page.goto(f"{BASE}/api/v1/analyses/{first_id}/")
        other_page.screenshot(path=OUT / "T07_other_user_404.png")
        other_page.goto(f"{BASE}/analyses/")
        other_page.wait_for_timeout(1500)
        other_page.screenshot(path=OUT / "T07_other_user_history_empty.png")
        other.close()

        # T08 관리자 대시보드 / Admin, 일반 회원 차단
        page.goto(f"{BASE}/dashboard/")
        page.screenshot(path=OUT / "T08_student_dashboard_blocked.png")
        context.clear_cookies()
        login(page, "teacher")
        page.goto(f"{BASE}/dashboard/")
        page.wait_for_timeout(1500)
        page.screenshot(path=OUT / "T08_dashboard.png", full_page=True)
        page.goto(f"{BASE}/admin/analyses/analysisjob/")
        page.screenshot(path=OUT / "T08_admin_jobs.png", full_page=True)
        page.goto(f"{BASE}/admin/analyses/personprediction/")
        page.screenshot(path=OUT / "T08_admin_predictions.png")

        browser.close()
    print("saved:", sorted(f.name for f in OUT.glob("*.png")))


if __name__ == "__main__":
    main()
