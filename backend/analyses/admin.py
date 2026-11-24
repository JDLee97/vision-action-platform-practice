from django.contrib import admin

from .models import AnalysisJob, PersonPrediction


class PersonPredictionInline(admin.TabularInline):
    model = PersonPrediction
    extra = 0
    fields = ("track_id", "action_label", "confidence", "uncertain", "valid_frames")
    readonly_fields = fields
    can_delete = False


@admin.register(AnalysisJob)
class AnalysisJobAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "input_type", "status", "stage", "expected_action",
                    "prediction_count", "processing_ms", "created_at")
    list_filter = ("status", "input_type", "created_at")
    search_fields = ("user__username", "title", "memo")
    readonly_fields = ("celery_task_id", "created_at", "started_at", "finished_at", "processing_ms")
    inlines = [PersonPredictionInline]
    date_hierarchy = "created_at"

    @admin.display(description="사람 수")
    def prediction_count(self, obj):
        return obj.predictions.count()


@admin.register(PersonPrediction)
class PersonPredictionAdmin(admin.ModelAdmin):
    list_display = ("id", "job", "track_id", "action_label", "confidence", "uncertain", "valid_frames", "created_at")
    list_filter = ("action_label", "uncertain", "job__input_type")
    search_fields = ("job__user__username", "action_label")
    list_select_related = ("job", "job__user")
