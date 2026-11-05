"""Plays the Helpdesk's side of the webhook: many Events, redelivered duplicates, concurrency."""

import random
import statistics
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import httpx

SAMPLE_MESSAGES = [
    "Не можу експортувати звіт у PDF",
    "Кнопка «Експорт» неактивна, що робити?",
    "Як вивантажити таблицю в Excel? Кирилиця відображається кракозябрами",
    "Забув пароль і не можу увійти в акаунт",
    "Акаунт заблоковано після кількох спроб входу",
    "Скільки коштує тариф Business і чи можна оплатити рахунком у гривнях?",
    "Хочу повернути кошти за підписку",
    "Як підключити Google Sheets як джерело даних?",
    "Помилка підключення до PostgreSQL",
    "Хочу щопонеділка отримувати звіт на пошту",
    "Розсилка звіту не приходить",
    "Як дати колезі доступ до дашборду тільки на перегляд?",
    "Дашборд дуже повільно завантажується і показує старі дані",
    "Чи можна створити публічне посилання на дашборд з паролем?",
    "Яка у вас адреса офісу у Львові?",
]


@dataclass
class Report:
    requests: int = 0
    accepted: int = 0
    duplicates_acknowledged: int = 0
    errors: int = 0
    latencies: list = field(default_factory=list)

    def summary(self):
        lines = [
            f"requests sent:            {self.requests}",
            f"accepted (new Tickets):   {self.accepted}",
            f"acknowledged duplicates:  {self.duplicates_acknowledged}",
            f"errors:                   {self.errors}",
        ]
        if self.latencies:
            ordered = sorted(self.latencies)
            p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
            lines.append(
                f"webhook latency, s:       p50 {statistics.median(ordered):.3f}  p95 {p95:.3f}  max {ordered[-1]:.3f}"
            )
        return "\n".join(lines)


def simulate(base_url, reply_base_url, count, duplicate_rate, concurrency, over_seconds=0, transport=None):
    """Post `count` Events; each is redelivered 1–2 extra times, at once, with `duplicate_rate` probability."""
    run = uuid.uuid4().hex[:6]
    webhook_url = f"{base_url.rstrip('/')}/webhooks/helpdesk"
    report = Report()
    lock = threading.Lock()
    http = httpx.Client(timeout=10, transport=transport)

    def deliver(event):
        started = time.monotonic()
        try:
            response = http.post(webhook_url, json=event)
            status = response.json().get("status") if response.status_code == 200 else None
        except (httpx.HTTPError, ValueError):
            status = None
        elapsed = time.monotonic() - started
        with lock:
            report.requests += 1
            report.latencies.append(elapsed)
            if status == "accepted":
                report.accepted += 1
            elif status == "duplicate":
                report.duplicates_acknowledged += 1
            else:
                report.errors += 1

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        for i in range(count):
            ticket_id = f"SIM-{run}-{i}"
            event = {
                "event_id": f"sim_{run}_{i}",
                "ticket_id": ticket_id,
                "customer_email": f"customer{i}@example.com",
                "message": random.choice(SAMPLE_MESSAGES),
                "reply_url": f"{reply_base_url.rstrip('/')}/mock-helpdesk/tickets/{ticket_id}/replies",
            }
            copies = 1 + (random.randint(1, 2) if random.random() < duplicate_rate else 0)
            for _ in range(copies):
                pool.submit(deliver, event)
            if over_seconds:
                time.sleep(over_seconds / count)
    http.close()
    return report
