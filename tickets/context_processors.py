from django.conf import settings


def llm_mode(request):
    return {"llm_stub_mode": not settings.ANTHROPIC_API_KEY}
