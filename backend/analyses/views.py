"""DRF API: 분석 작업 CRUD + 상태 조회.

POST   /api/v1/analyses/              작업 생성 → DB 저장 → Celery 등록 → 작업 ID 즉시 반환(202)
GET    /api/v1/analyses/              내 작업 목록 (관리자는 전체)
GET    /api/v1/analyses/{id}/         상세 + 사람별 결과
GET    /api/v1/analyses/{id}/status/  상태만 가볍게 조회 (브라우저 폴링용)
PATCH  /api/v1/analyses/{id}/         제목·메모만 수정
DELETE /api/v1/analyses/{id}/         작업·사람별 결과·영상 파일 삭제
"""

import logging

from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import AnalysisJob
from .serializers import (
    AnalysisJobSerializer,
    AnalysisJobStatusSerializer,
    AnalysisJobUpdateSerializer,
)
from .tasks import run_analysis

logger = logging.getLogger("analyses")


class AnalysisJobViewSet(viewsets.ModelViewSet):
    serializer_class = AnalysisJobSerializer

    def get_queryset(self):
        queryset = AnalysisJob.objects.select_related("user").prefetch_related("predictions")
        user = self.request.user
        # 일반 회원은 자기 작업만 보인다 → 남의 작업 id로 접근하면 404 (조회·수정·삭제 모두 차단)
        if user.is_staff:
            return queryset
        return queryset.filter(user=user)

    def get_serializer_class(self):
        if self.action in {"update", "partial_update"}:
            return AnalysisJobUpdateSerializer
        return AnalysisJobSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        job = serializer.save(user=request.user)

        # DB 저장(commit)이 끝난 뒤에 큐에 넣어야 Worker가 작업을 찾을 수 있다.
        def enqueue():
            try:
                result = run_analysis.delay(job.id)
                AnalysisJob.objects.filter(pk=job.pk).update(celery_task_id=result.id)
            except Exception as error:  # Redis가 꺼져 있으면 실패로 기록
                logger.exception("Celery 등록 실패 job=%s", job.id)
                AnalysisJob.objects.filter(pk=job.pk).update(
                    status=AnalysisJob.Status.FAILURE,
                    error_message=f"작업 대기열(Redis)에 등록하지 못했습니다: {error}",
                )

        transaction.on_commit(enqueue)

        # 분석을 기다리지 않고 작업 ID를 바로 돌려준다.
        job.refresh_from_db()
        data = AnalysisJobSerializer(job, context=self.get_serializer_context()).data
        return Response(data, status=status.HTTP_202_ACCEPTED)

    def update(self, request, *args, **kwargs):
        super().update(request, *args, **kwargs)
        job = self.get_object()
        return Response(AnalysisJobSerializer(job, context=self.get_serializer_context()).data)

    def perform_destroy(self, instance):
        # 사람별 예측은 CASCADE로 함께 삭제. 파일도 함께 지운다.
        for field in (instance.video, instance.result_image):
            if field:
                field.delete(save=False)
        instance.delete()

    @action(detail=True, methods=["get"])
    def status(self, request, pk=None):
        job = self.get_object()
        return Response(AnalysisJobStatusSerializer(job, context=self.get_serializer_context()).data)
