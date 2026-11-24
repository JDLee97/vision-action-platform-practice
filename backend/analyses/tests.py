"""과제 테스트 T05·T06·T07·T08·T09 중 DB·권한 부분을 자동으로 확인한다.

FastAPI·Celery는 가짜 함수로 바꿔(mock) Django 쪽 동작만 검사한다.
"""

import shutil
import tempfile
from unittest import mock

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from .models import AnalysisJob, PersonPrediction
from .services import AIServiceError
from .tasks import run_analysis

MEDIA = tempfile.mkdtemp()
CAMERAS = {"phone": {"name": "테스트 카메라", "url": "http://camera.invalid/video"}}


def fake_video(name="clip.mp4"):
    return SimpleUploadedFile(name, b"\x00\x00\x00\x18ftypmp42" + b"0" * 2048, content_type="video/mp4")


FAKE_RESULT = {
    "status": "ok",
    "message": "2명의 동작을 예측했습니다.",
    "processing_ms": 1234,
    "video": {"duration_sec": 3.2},
    "predictions": [
        {"track_id": 1, "action_label": "wave", "confidence": 0.81, "uncertain": False, "valid_frames": 80, "probabilities": {}},
        {"track_id": 2, "action_label": "sit_stand", "confidence": 0.41, "uncertain": True, "valid_frames": 60, "probabilities": {}},
    ],
    "preview_jpeg_base64": None,
}


@override_settings(MEDIA_ROOT=MEDIA, IP_WEBCAM_CAMERAS=CAMERAS)
class AnalysisApiTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.a = User.objects.create_user("student_a", password="VisionAi!2026")
        self.b = User.objects.create_user("student_b", password="VisionAi!2026")
        self.admin = User.objects.create_user("teacher", password="VisionAi!2026", is_staff=True)
        self.client_a = APIClient()
        self.client_a.force_authenticate(self.a)
        self.client_b = APIClient()
        self.client_b.force_authenticate(self.b)
        self.list_url = reverse("analyses:analysis-list")

    def create_job(self, client):
        with mock.patch("analyses.views.run_analysis.delay") as delay, self.captureOnCommitCallbacks(execute=True):
            delay.return_value.id = "task-1"
            response = client.post(self.list_url, {"input_type": "upload", "video": fake_video()}, format="multipart")
        return response, delay

    # T05: 분석을 기다리지 않고 작업 ID를 즉시 반환, DB 저장 후 큐 등록
    def test_create_returns_job_id_immediately(self):
        response, delay = self.create_job(self.client_a)
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.data["status"], "PENDING")
        delay.assert_called_once_with(response.data["id"])
        self.assertEqual(AnalysisJob.objects.get().celery_task_id, "task-1")

    def test_anonymous_rejected(self):
        response = APIClient().get(self.list_url)
        self.assertIn(response.status_code, (401, 403))

    def test_invalid_inputs_rejected(self):
        bad_ext = self.client_a.post(self.list_url, {"input_type": "upload", "video": fake_video("a.txt")}, format="multipart")
        no_file = self.client_a.post(self.list_url, {"input_type": "upload"}, format="multipart")
        bad_camera = self.client_a.post(self.list_url, {"input_type": "ipwebcam", "camera_key": "http://evil/video"})
        self.assertEqual(bad_ext.status_code, 400)
        self.assertEqual(no_file.status_code, 400)
        self.assertEqual(bad_camera.status_code, 400)
        self.assertEqual(AnalysisJob.objects.count(), 0)

    # T07: A는 B의 결과를 조회·수정·삭제할 수 없다.
    def test_other_users_job_is_invisible(self):
        response, _ = self.create_job(self.client_b)
        url = reverse("analyses:analysis-detail", args=[response.data["id"]])
        self.assertEqual(self.client_a.get(url).status_code, 404)
        self.assertEqual(self.client_a.patch(url, {"title": "hack"}).status_code, 404)
        self.assertEqual(self.client_a.delete(url).status_code, 404)
        self.assertEqual(self.client_a.get(self.list_url).data["count"], 0)
        self.assertTrue(AnalysisJob.objects.filter(pk=response.data["id"]).exists())

    def test_user_can_only_update_title_and_memo(self):
        response, _ = self.create_job(self.client_a)
        url = reverse("analyses:analysis-detail", args=[response.data["id"]])
        updated = self.client_a.patch(url, {"title": "내 손 흔들기", "status": "SUCCESS"}, format="json")
        self.assertEqual(updated.status_code, 200)
        job = AnalysisJob.objects.get()
        self.assertEqual(job.title, "내 손 흔들기")
        self.assertEqual(job.status, "PENDING")

    def test_staff_sees_all_jobs(self):
        self.create_job(self.client_a)
        self.create_job(self.client_b)
        staff = APIClient()
        staff.force_authenticate(self.admin)
        self.assertEqual(staff.get(self.list_url).data["count"], 2)

    # T06: Worker가 저장한 결과가 DB에 남는다 (사람 2명 → 결과 2건)
    def test_task_saves_predictions(self):
        response, _ = self.create_job(self.client_a)
        with mock.patch("analyses.tasks.request_prediction", return_value=FAKE_RESULT):
            run_analysis(response.data["id"])
        job = AnalysisJob.objects.get()
        self.assertEqual(job.status, "SUCCESS")
        self.assertEqual(job.predictions.count(), 2)
        self.assertTrue(PersonPrediction.objects.get(track_id=2).uncertain)
        detail = self.client_a.get(reverse("analyses:analysis-status", args=[job.id]))
        self.assertEqual(len(detail.data["predictions"]), 2)

    # T09: AI 서버 오류 → FAILURE + 사용자용 오류 메시지 저장
    def test_task_failure_is_recorded(self):
        response, _ = self.create_job(self.client_a)
        with mock.patch("analyses.tasks.request_prediction", side_effect=AIServiceError("AI 서버(FastAPI)에 연결할 수 없습니다.")):
            run_analysis(response.data["id"])
        job = AnalysisJob.objects.get()
        self.assertEqual(job.status, "FAILURE")
        self.assertIn("FastAPI", job.error_message)

    def test_delete_removes_predictions(self):
        response, _ = self.create_job(self.client_a)
        with mock.patch("analyses.tasks.request_prediction", return_value=FAKE_RESULT):
            run_analysis(response.data["id"])
        url = reverse("analyses:analysis-detail", args=[response.data["id"]])
        self.assertEqual(self.client_a.delete(url).status_code, 204)
        self.assertEqual(PersonPrediction.objects.count(), 0)


class DashboardTests(TestCase):
    # T08: 관리자만 /dashboard/ 접근
    def test_dashboard_staff_only(self):
        User.objects.create_user("student", password="VisionAi!2026")
        User.objects.create_user("teacher", password="VisionAi!2026", is_staff=True)
        self.client.login(username="student", password="VisionAi!2026")
        self.assertEqual(self.client.get(reverse("analyses:dashboard")).status_code, 302)
        self.client.login(username="teacher", password="VisionAi!2026")
        response = self.client.get(reverse("analyses:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "동작별 예측 건수")
