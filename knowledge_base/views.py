from django.shortcuts import get_object_or_404, render

from .models import Article
from .search import search_articles


def article_list(request):
    query = request.GET.get("q", "").strip()
    articles = search_articles(query) if query else Article.objects.all()
    return render(request, "knowledge_base/list.html", {"articles": articles, "query": query})


def article_detail(request, slug):
    article = get_object_or_404(Article, slug=slug)
    return render(request, "knowledge_base/detail.html", {"article": article})
