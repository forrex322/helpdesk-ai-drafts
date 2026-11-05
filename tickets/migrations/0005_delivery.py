import uuid

from django.db import migrations, models


def give_each_ticket_its_own_key(apps, schema_editor):
    # A callable default is evaluated once for AddField, which would give every
    # existing Ticket the same key and make the Helpdesk drop all but one Reply.
    Ticket = apps.get_model("tickets", "Ticket")
    for ticket in Ticket.objects.only("pk"):
        Ticket.objects.filter(pk=ticket.pk).update(reply_idempotency_key=uuid.uuid4())


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0004_moderation"),
    ]

    operations = [
        migrations.AddField(
            model_name="ticket",
            name="reply_idempotency_key",
            field=models.UUIDField(null=True, editable=False),
        ),
        migrations.RunPython(give_each_ticket_its_own_key, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="ticket",
            name="reply_idempotency_key",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AddField(
            model_name="ticket",
            name="sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
