from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create or update the demo Operator from OPERATOR_USERNAME / OPERATOR_PASSWORD."

    def handle(self, *args, **options):
        User = get_user_model()
        user, created = User.objects.get_or_create(username=settings.OPERATOR_USERNAME)
        user.set_password(settings.OPERATOR_PASSWORD)
        user.is_staff = True
        user.save()
        verb = "Created" if created else "Updated"
        self.stdout.write(f"{verb} Operator '{user.username}'.")
