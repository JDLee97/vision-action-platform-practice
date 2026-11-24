"""HTML 화면: 사용자 분석 화면(/analyses/), 관리자 대시보드(/dashboard/), 카메라 미리보기."""

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache

from .camera_capture import CameraError, grab_snapshot_jpeg
from .constants import ACTION_CHOICES, ACTIONS
from .models import AnalysisJob, PersonPrediction


@login_required
def index(request):
    cameras = [{"key": key, "name": cam["name"]} for key, cam in settings.IP_WEBCAM_CAMERAS.items()]
    context = {
        "cameras": cameras,
        "capture_seconds": int(settings.IP_WEBCAM_CAPTURE_SECONDS),
        "action_choices": ACTION_CHOICES,
        "max_upload_mb": settings.MAX_UPLOAD_MB,
    }
    return render(request, "analyses/index.html", context)


@login_required
@never_cache
def camera_snapshot(request, camera_key):
    """허용 목록의 카메라에서 한 장을 가져와 JPEG로 전달 (브라우저에 카메라 주소 비노출)."""
    try:
        return HttpResponse(grab_snapshot_jpeg(camera_key), content_type="image/jpeg")
    except CameraError as error:
        return JsonResponse({"detail": str(error)}, status=503)


@staff_member_required  # is_staff가 아니면 관리자 로그인 화면으로 보낸다.
def dashboard(request):
    # ① 동작별 예측 건수 (PersonPrediction) — 6개 Action 순서 고정, 0건도 표시
    action_counts = dict(
        PersonPrediction.objects.values_list("action_label").annotate(n=Count("id")).values_list("action_label", "n")
    )
    action_rows = [
        {"id": action_id, "label": label, "name": name, "count": action_counts.get(label, 0)}
        for action_id, label, name in ACTIONS
    ]

    # ② 작업 상태별 건수 (AnalysisJob)
    status_counts = dict(AnalysisJob.objects.values_list("status").annotate(n=Count("id")).values_list("status", "n"))
    status_rows = [
        {"status": value, "name": name, "count": status_counts.get(value, 0)}
        for value, name in [
            (AnalysisJob.Status.SUCCESS, "완료"),
            (AnalysisJob.Status.FAILURE, "실패"),
            (AnalysisJob.Status.STARTED, "처리 중"),
            (AnalysisJob.Status.PENDING, "대기"),
        ]
    ]

    # 선택 지표: 입력 방식별 건수, 평균 처리 시간
    input_counts = dict(AnalysisJob.objects.values_list("input_type").annotate(n=Count("id")).values_list("input_type", "n"))
    avg_ms = AnalysisJob.objects.filter(status=AnalysisJob.Status.SUCCESS).aggregate(v=Avg("processing_ms"))["v"]

    chart_data = {
        "actions": {"labels": [f"{r['id']} {r['name']}" for r in action_rows], "counts": [r["count"] for r in action_rows]},
        "statuses": {"labels": [r["name"] for r in status_rows], "counts": [r["count"] for r in status_rows]},
    }
    context = {
        "action_rows": action_rows,
        "status_rows": status_rows,
        "total_jobs": sum(status_counts.values()),
        "total_predictions": sum(action_counts.values()),
        "upload_count": input_counts.get(AnalysisJob.InputType.UPLOAD, 0),
        "ipwebcam_count": input_counts.get(AnalysisJob.InputType.IPWEBCAM, 0),
        "avg_seconds": round(avg_ms / 1000, 1) if avg_ms else None,
        "recent_jobs": AnalysisJob.objects.select_related("user").prefetch_related("predictions")[:10],
        "chart_data": chart_data,
    }
    return render(request, "analyses/dashboard.html", context)
