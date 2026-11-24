"""분석 작업(AnalysisJob)과 사람별 예측(PersonPrediction).

auth_user 1 ── N AnalysisJob 1 ── N PersonPrediction
"""

from django.conf import settings
from django.db import models

from .constants import ACTION_CHOICES, ACTION_DISPLAY


class AnalysisJob(models.Model):
    class InputType(models.TextChoices):
        UPLOAD = "upload", "영상 업로드"
        IPWEBCAM = "ipwebcam", "IP Webcam"

    class Status(models.TextChoices):
        PENDING = "PENDING", "대기"
        STARTED = "STARTED", "처리 중"
        SUCCESS = "SUCCESS", "완료"
        FAILURE = "FAILURE", "실패"

    class Stage(models.TextChoices):
        # 화면의 단계 표시(대기 → 영상 수집 → AI 분석 → 완료)용
        QUEUED = "queued", "대기"
        COLLECTING = "collecting", "영상 수집"
        ANALYZING = "analyzing", "AI 분석"
        DONE = "done", "완료"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="analysis_jobs",
        verbose_name="요청 사용자",
    )
    title = models.CharField("제목", max_length=100, blank=True)
    memo = models.TextField("메모", blank=True)
    input_type = models.CharField("입력 방식", max_length=10, choices=InputType.choices)
    # 영상 파일은 MEDIA 폴더에 두고 DB에는 경로만 저장한다. (IP Webcam은 수집 후 저장)
    video = models.FileField("영상", upload_to="videos/%Y%m%d/", blank=True)
    camera_key = models.CharField("카메라(허용 목록 키)", max_length=50, blank=True)
    expected_action = models.CharField(
        "수행하려는 동작(사용자 입력)", max_length=30, choices=ACTION_CHOICES, blank=True,
        help_text="사용자가 고른 값일 뿐 검증된 정답 Label이 아니다.",
    )
    status = models.CharField("상태", max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    stage = models.CharField("단계", max_length=12, choices=Stage.choices, default=Stage.QUEUED)
    celery_task_id = models.CharField("Celery Task ID", max_length=255, blank=True)
    error_message = models.TextField("오류 메시지", blank=True)
    result_message = models.CharField("결과 메시지", max_length=255, blank=True)
    result_image = models.FileField("결과 미리보기(Skeleton)", upload_to="results/%Y%m%d/", blank=True)
    processing_ms = models.PositiveIntegerField("AI 처리 시간(ms)", null=True, blank=True)
    video_duration_sec = models.FloatField("영상 길이(초)", null=True, blank=True)
    created_at = models.DateTimeField("생성 시간", auto_now_add=True)
    started_at = models.DateTimeField("시작 시간", null=True, blank=True)
    finished_at = models.DateTimeField("완료 시간", null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "분석 작업"
        verbose_name_plural = "분석 작업"

    def __str__(self):
        return f"#{self.pk} {self.user} {self.get_input_type_display()} {self.status}"

    @property
    def is_finished(self) -> bool:
        return self.status in {self.Status.SUCCESS, self.Status.FAILURE}


class PersonPrediction(models.Model):
    job = models.ForeignKey(
        AnalysisJob,
        on_delete=models.CASCADE,  # 작업을 삭제하면 사람별 결과도 함께 삭제
        related_name="predictions",
        verbose_name="분석 작업",
    )
    track_id = models.PositiveIntegerField("Track ID", help_text="이 작업(영상) 안에서만 유효한 추적 번호")
    action_label = models.CharField("예측 동작", max_length=30)
    confidence = models.FloatField("신뢰도")
    uncertain = models.BooleanField("불확실(신뢰도 낮음)", default=False)
    valid_frames = models.PositiveIntegerField("유효 Pose Frame 수", default=0)
    probabilities = models.JSONField("Class별 확률", default=dict, blank=True)
    created_at = models.DateTimeField("예측 시간", auto_now_add=True)

    class Meta:
        ordering = ["job", "track_id"]
        verbose_name = "사람별 예측"
        verbose_name_plural = "사람별 예측"
        constraints = [
            models.UniqueConstraint(fields=["job", "track_id"], name="unique_track_per_job"),
        ]

    def __str__(self):
        return f"job#{self.job_id} ID{self.track_id} {self.action_label} {self.confidence:.2f}"

    @property
    def action_display(self) -> str:
        return ACTION_DISPLAY.get(self.action_label, self.action_label)
