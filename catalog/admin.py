from django.contrib import admin

from .models import AnalysisPost, Comment, EventDate, HorizonResult, Vote


@admin.register(AnalysisPost)
class AnalysisPostAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "created_at", "updated_at")
    search_fields = ("title", "prompt_text")
    list_filter = ("created_at",)


@admin.register(EventDate)
class EventDateAdmin(admin.ModelAdmin):
    list_display = ("post", "event_date")


@admin.register(HorizonResult)
class HorizonResultAdmin(admin.ModelAdmin):
    list_display = ("post", "horizon", "return_value")


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ("user", "post", "value")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("user", "post", "created_at")
