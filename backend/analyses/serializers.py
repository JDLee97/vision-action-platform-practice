"""입력 검사와 JSON 응답 형태를 정한다.

- 생성: 입력 방식에 따라 영상 파일 또는 허용된 카메라 키를 검사
- 수정: 제목·메모만 허용 (상태·AI 결과는 읽기 전용)
"""

from pathlib import Path

from django.conf import settings
from rest_framework import serializers

from .constants import ACTION_DISPLAY, ACTION_ID
from .models import AnalysisJob, PersonPrediction

ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}


class PersonPredictionSerializer(serializers.ModelSerializer):
    action_id = serializers.SerializerMethodField()
    action_display = serializers.SerializerMethodField()

    class Meta:
        model = PersonPrediction
        fields = ["track_id", "action_label", "action_id", "action_display",
                  "confidence", "uncertain", "valid_frames", "probabilities", "created_at"]
        read_only_fields = fields

    def get_action_id(self, obj):
        return ACTION_ID.get(obj.action_label, "")

    def get_action_display(self, obj):
        return ACTION_DISPLAY.get(obj.action_label, obj.action_label)


class AnalysisJobSerializer(serializers.ModelSerializer):
    user = serializers.CharField(source="user.username", read_only=True)
    input_type_display = serializers.CharField(source="get_input_type_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    stage_display = serializers.CharField(source="get_stage_display", read_only=True)
    camera_name = serializers.SerializerMethodField()
    predictions = PersonPredictionSerializer(many=True, read_only=True)
    video = serializers.FileField(required=False, allow_empty_file=False)

    class Meta:
        model = AnalysisJob
        fields = [
            "id", "user", "title", "memo",
            "input_type", "input_type_display", "video", "camera_key", "camera_name", "expected_action",
            "status", "status_display", "stage", "stage_display",
            "result_message", "error_message", "result_image", "processing_ms", "video_duration_sec",
            "celery_task_id", "created_at", "started_at", "finished_at",
            "predictions",
        ]
        read_only_fields = [
            "status", "stage", "result_message", "error_message", "result_image", "processing_ms",
            "video_duration_sec", "celery_task_id", "created_at", "started_at", "finished_at",
        ]

    def get_camera_name(self, obj):
        camera = settings.IP_WEBCAM_CAMERAS.get(obj.camera_key)
        return camera["name"] if camera else ""

    def validate_video(self, video):
        suffix = Path(video.name).suffix.lower()
        if suffix not in ALLOWED_VIDEO_EXTENSIONS:
            raise serializers.ValidationError("MP4·AVI·MOV·MKV·WEBM 영상만 올릴 수 있습니다.")
        if video.size > settings.MAX_UPLOAD_MB * 1024 * 1024:
            raise serializers.ValidationError(f"영상은 {settings.MAX_UPLOAD_MB}MB 이하만 올릴 수 있습니다.")
        return video

    def validate(self, attrs):
        if self.instance is not None:  # 수정은 UpdateSerializer가 담당
            return attrs
        input_type = attrs.get("input_type")
        if input_type == AnalysisJob.InputType.UPLOAD:
            if not attrs.get("video"):
                raise serializers.ValidationError({"video": "분석할 영상 파일을 선택하세요."})
            attrs["camera_key"] = ""
        elif input_type == AnalysisJob.InputType.IPWEBCAM:
            key = attrs.get("camera_key", "")
            if key not in settings.IP_WEBCAM_CAMERAS:
                # 사용자가 임의의 URL을 넣을 수 없고, 서버 허용 목록의 키만 고를 수 있다.
                raise serializers.ValidationError({"camera_key": "허용된 카메라를 선택하세요."})
            attrs.pop("video", None)
        return attrs


class AnalysisJobUpdateSerializer(serializers.ModelSerializer):
    """PATCH/PUT: 사용자는 제목과 메모만 바꿀 수 있다."""

    class Meta:
        model = AnalysisJob
        fields = ["title", "memo"]


class AnalysisJobStatusSerializer(serializers.ModelSerializer):
    """브라우저가 주기적으로 호출하는 가벼운 상태 조회 응답."""

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    stage_display = serializers.CharField(source="get_stage_display", read_only=True)
    predictions = PersonPredictionSerializer(many=True, read_only=True)

    class Meta:
        model = AnalysisJob
        fields = ["id", "status", "status_display", "stage", "stage_display", "result_message",
                  "error_message", "result_image", "processing_ms", "finished_at", "predictions"]
        read_only_fields = fields
