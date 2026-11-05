"""Find the Articles most relevant to a Customer's message.

Postgres has no Ukrainian stemmer, so full-text search would miss
"експортувати" vs "Експорт". Trigram word similarity tolerates word forms:
each meaningful word of the message is scored against the Article's text,
weak matches are ignored, and the strong ones are summed.
"""

import re
from functools import reduce
from operator import add

from django.contrib.postgres.search import TrigramWordSimilarity
from django.db.models import Case, F, FloatField, TextField, Value, When
from django.db.models.functions import Concat

from .models import Article

# A word counts only if it matches some part of the Article at least this well.
WORD_MATCH_THRESHOLD = 0.5
# Articles scoring below this share of the best match are noise, not citations.
RELATIVE_SCORE_CUTOFF = 0.5
MAX_WORDS = 12
STOP_WORDS = frozenset(
    """
    але або аби адже без біля будь буде було були вам вас ваш ваша ваше ваші вже все всі
    від для добрий день дуже дякую його йому коли котрий ласка мене мені мій мною моє моя
    мої можна можу може міг навіть над нас нам наш немає ось після під потрібно привіт про
    при так там тут теж треба тобто той тому хочу хоче цей ця це чому через щоб щось який
    яка яке які як що ще усі між хто
    """.split()
)


def meaningful_words(text):
    words = re.findall(r"\w+", text.lower())
    unique = dict.fromkeys(w for w in words if len(w) >= 3 and w not in STOP_WORDS)
    return list(unique)[:MAX_WORDS]


def search_articles(text, limit=3):
    words = meaningful_words(text)
    if not words:
        return []

    articles = Article.objects.annotate(
        document=Concat("title", Value(" "), "keywords", Value(" "), "body", output_field=TextField()),
    )
    similarities = {f"word_{i}": TrigramWordSimilarity(word, "document") for i, word in enumerate(words)}
    articles = articles.annotate(**similarities)
    strong_matches = (
        Case(
            When(**{f"{name}__gte": WORD_MATCH_THRESHOLD}, then=F(name)),
            default=Value(0.0),
            output_field=FloatField(),
        )
        for name in similarities
    )
    ranked = list(
        articles.annotate(score=reduce(add, strong_matches))
        .filter(score__gt=0)
        .order_by("-score", "title")[:limit]
    )
    if not ranked:
        return []
    cutoff = ranked[0].score * RELATIVE_SCORE_CUTOFF
    return [article for article in ranked if article.score >= cutoff]
