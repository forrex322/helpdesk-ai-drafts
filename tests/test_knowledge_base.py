import re

import pytest


def slugs_in(response):
    return re.findall(r'data-article-slug="([^"]+)"', response.content.decode())


def test_knowledge_base_is_public_and_lists_seeded_articles(db, client):
    response = client.get("/kb/")

    assert response.status_code == 200
    assert 5 <= len(slugs_in(response)) <= 10


def test_article_page_is_public(db, client):
    response = client.get("/kb/export-pdf/")

    assert response.status_code == 200
    assert "PDF" in response.content.decode()


def test_unknown_article_is_404(db, client):
    assert client.get("/kb/no-such-article/").status_code == 404


@pytest.mark.parametrize(
    ("message", "expected_first"),
    [
        ("Не можу експортувати звіт у PDF", "export-pdf"),
        ("Забув пароль і не можу увійти в акаунт", "password-reset"),
        ("Скільки коштує тариф Business і як оплатити рахунок?", "billing-plans"),
        ("Як підключити Google Sheets як джерело даних?", "data-sources"),
        ("Хочу щопонеділка отримувати звіт на пошту", "scheduled-reports"),
        ("Як дати колезі доступ до дашборду тільки на перегляд?", "sharing-access"),
        ("Вивантажте, будь ласка, таблицю в Excel", "export-excel-csv"),
        ("Дашборд дуже повільно завантажується і показує старі дані", "dashboard-performance"),
    ],
    ids=lambda value: value if value.isascii() else "",
)
def test_search_ranks_the_most_relevant_article_first(db, client, message, expected_first):
    slugs = slugs_in(client.get("/kb/", {"q": message}))

    assert slugs[0] == expected_first
    assert len(slugs) <= 3


def test_search_finds_nothing_for_an_unrelated_message(db, client):
    response = client.get("/kb/", {"q": "Яка погода буде в Києві завтра?"})

    assert slugs_in(response) == []


def test_search_leaves_out_articles_far_weaker_than_the_best_match(db, client):
    response = client.get("/kb/", {"q": "Забув пароль і не можу увійти в акаунт"})

    assert slugs_in(response) == ["password-reset"]
