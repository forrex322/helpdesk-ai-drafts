from django.conf import settings


def llm_mode(request):
    return {"llm_stub_mode": settings.LLM_STUB_MODE}
