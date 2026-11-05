from django.conf import settings
from django.db import models
from django.urls import reverse


class Article(models.Model):
    """One short help page in the Knowledge Base, with a stable public link."""

    slug = models.SlugField(max_length=100, unique=True)
    title = models.CharField(max_length=200)
    # Extra word forms and synonyms that Customers use but the body may not.
    keywords = models.TextField(blank=True)
    body = models.TextField()

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("knowledge_base:article", args=[self.slug])

    @property
    def public_url(self):
        return f"{settings.PUBLIC_BASE_URL}{self.get_absolute_url()}"
