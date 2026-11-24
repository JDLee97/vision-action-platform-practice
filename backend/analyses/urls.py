from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import page_views
from .views import AnalysisJobViewSet

app_name = "analyses"

router = DefaultRouter()
router.register("analyses", AnalysisJobViewSet, basename="analysis")

urlpatterns = [
    # 화면
    path("analyses/", page_views.index, name="index"),
    path("analyses/cameras/<str:camera_key>/snapshot/", page_views.camera_snapshot, name="camera_snapshot"),
    path("dashboard/", page_views.dashboard, name="dashboard"),
    # DRF API
    path("api/v1/", include(router.urls)),
]
