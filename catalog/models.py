from django.contrib.auth.models import User
from django.db import models


class AnalysisPost(models.Model):
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="posts")
    title = models.CharField(max_length=200)
    prompt_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Storage for wizard state and results as JSON blobs
    events_data = models.JSONField(default=list, blank=True)
    stocks_data = models.JSONField(default=list, blank=True)
    results_data = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return self.title


class EventDate(models.Model):
    # Deprecated: using JSON storage in AnalysisPost
    pass


class SuggestedStock(models.Model):
    # Deprecated: using JSON storage in AnalysisPost
    pass


class HorizonResult(models.Model):
    # Deprecated: using JSON storage in AnalysisPost
    pass


# Optional: Remove Vote and Comment models if using JSON-only persistence
class Vote(models.Model):
    UPVOTE = 1
    DOWNVOTE = -1
    VALUE_CHOICES = (
        (UPVOTE, "Up"),
        (DOWNVOTE, "Down"),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="votes")
    post = models.ForeignKey(
        AnalysisPost, on_delete=models.CASCADE, related_name="votes"
    )
    value = models.SmallIntegerField(choices=VALUE_CHOICES)

    class Meta:
        unique_together = ("user", "post")

    def __str__(self):
        emoji = "👍" if self.value > 0 else "👎"
        return f"{self.user.username} {emoji} {self.post.title}"


class Comment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="comments")
    post = models.ForeignKey(
        AnalysisPost, on_delete=models.CASCADE, related_name="comments"
    )
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comment by {self.user.username} on {self.post.title}"
