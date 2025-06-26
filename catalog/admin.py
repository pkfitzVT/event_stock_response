from django.contrib import admin

from .models import AnalysisPost, Comment, Vote


# Register only the JSON-backed AnalysisPost and related models
@admin.register(AnalysisPost)
class AnalysisPostAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "created_at", "updated_at")
    readonly_fields = ("created_at", "updated_at")


admin.site.register(Vote)
admin.site.register(Comment)
