import signal
import threading

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run the background worker that drafts and delivers Replies."

    def handle(self, *args, **options):
        stop = threading.Event()
        signal.signal(signal.SIGTERM, lambda *_: stop.set())
        signal.signal(signal.SIGINT, lambda *_: stop.set())
        self.stdout.write("Worker started.")
        stop.wait()
        self.stdout.write("Worker stopped.")
