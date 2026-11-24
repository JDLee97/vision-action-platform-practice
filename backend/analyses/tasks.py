"""Celery Worker가 실행하는 분석 작업.

PENDING → STARTED(영상 수집 → AI 분석) → SUCCESS 또는 FAILURE
FastAPI는 결과 JSON만 돌려주고, DB 저장은 여기서 Django ORM으로 한다.
"""

import base64
import logging
import os

from celery import shared_task
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from .camera_capture import CameraError, capture_clip
from .models import AnalysisJob, PersonPrediction
from .services import AIServiceError, request_prediction

logger = logging.getLogger("analyses")


def _set(job: AnalysisJob, **fields):
    for name, value in fields.items():
        setattr(job, name, value)
    job.save(update_fields=list(fields))


@shared_task(name="analyses.run_analysis")
def run_analysis(job_id: int):
    try:
        job = AnalysisJob.objects.get(pk=job_id)
    except AnalysisJob.DoesNotExist:
        logger.warning("작업 %s가 없습니다(이미 삭제됨).", job_id)
        return

    if job.is_finished:
        return

    logger.info("작업 시작 job=%s type=%s", job.id, job.input_type)
    _set(job, status=AnalysisJob.Status.STARTED, stage=AnalysisJob.Stage.COLLECTING,
         started_at=timezone.now(), error_message="")

    capture_info = None
    try:
        # ① 분석할 영상 확보
        if job.input_type == AnalysisJob.InputType.IPWEBCAM:
            relative = f"videos/{timezone.localdate():%Y%m%d}/ipwebcam_job{job.id}.mp4"
            absolute = os.path.join(settings.MEDIA_ROOT, relative)
            capture_info = capture_clip(job.camera_key, absolute)
            logger.info("IP Webcam 수집 job=%s %s", job.id, capture_info)
            _set(job, video=relative)
        if not job.video:
            raise AIServiceError("분석할 영상이 없습니다.")

        # ② FastAPI 추론 요청
        _set(job, stage=AnalysisJob.Stage.ANALYZING)
        result = request_prediction(job.video.path)

        # ③ 결과 저장 (작업 + 사람별 예측을 한 트랜잭션으로)
        with transaction.atomic():
            job.predictions.all().delete()
            for item in result.get("predictions", []):
                PersonPrediction.objects.create(
                    job=job,
                    track_id=item["track_id"],
                    action_label=item["action_label"],
                    confidence=item["confidence"],
                    uncertain=item.get("uncertain", False),
                    valid_frames=item.get("valid_frames", 0),
                    probabilities=item.get("probabilities", {}),
                )

            if result.get("preview_jpeg_base64"):
                image = ContentFile(base64.b64decode(result["preview_jpeg_base64"]))
                job.result_image.save(f"job{job.id}.jpg", image, save=False)

            job.processing_ms = result.get("processing_ms")
            # IP Webcam은 파일의 FPS 값이 실제와 다를 수 있으므로 실제 수집 시간을 기록
            job.video_duration_sec = (
                capture_info["seconds"] if capture_info else (result.get("video") or {}).get("duration_sec")
            )
            job.result_message = result.get("message", "")[:255]
            job.finished_at = timezone.now()
            job.stage = AnalysisJob.Stage.DONE
            if result.get("status") == "ok":
                job.status = AnalysisJob.Status.SUCCESS
            else:
                # 영상은 읽혔지만 사람 없음/너무 짧음 → 판단 불가이므로 실패로 기록하고 이유를 남긴다.
                job.status = AnalysisJob.Status.FAILURE
                job.error_message = result.get("message", "동작을 판단하지 못했습니다.")
            job.save()

        logger.info("작업 완료 job=%s status=%s", job.id, job.status)

    except (CameraError, AIServiceError) as error:
        logger.warning("작업 실패 job=%s: %s", job.id, error)
        _set(job, status=AnalysisJob.Status.FAILURE, stage=AnalysisJob.Stage.DONE,
             error_message=str(error), finished_at=timezone.now())
    except Exception as error:  # 예상하지 못한 오류도 FAILURE로 남겨 화면에서 멈추지 않게 한다.
        logger.exception("작업 오류 job=%s", job.id)
        _set(job, status=AnalysisJob.Status.FAILURE, stage=AnalysisJob.Stage.DONE,
             error_message=f"서버 내부 오류: {error.__class__.__name__}: {error}", finished_at=timezone.now())
