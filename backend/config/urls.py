"""최상위 URL 연결."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="analyses:index", permanent=False)),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("", include("analyses.urls")),  # /analyses/, /dashboard/, /api/v1/analyses/
]

# 개발 서버에서 업로드 영상·결과 이미지 제공
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
