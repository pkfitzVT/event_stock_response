from django.contrib.auth.models import User
from django.db import models


class AnalysisPost(models.Model):
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="posts")
    title = models.CharField(max_length=200)
    prompt_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class EventDate(models.Model):
    post = models.ForeignKey(
        AnalysisPost, on_delete=models.CASCADE, related_name="dates"
    )
    event_date = models.DateField()

    def __str__(self):
        return f"{self.post.title}: {self.event_date}"


class HorizonResult(models.Model):
    post = models.ForeignKey(
        AnalysisPost, on_delete=models.CASCADE, related_name="results"
    )
    horizon = models.CharField(max_length=10)  # e.g. "1D", "1W"
    return_value = models.FloatField()

    def __str__(self):
        return f"{self.post.title} {self.horizon}: {self.return_value:.4f}"


class Vote(models.Model):
    UPVOTE = 1
    DOWNVOTE = -1
    VALUE_CHOICES = ((UPVOTE, "Up"), (DOWNVOTE, "Down"))

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
