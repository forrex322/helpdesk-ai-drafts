from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("knowledge_base", "0001_article"),
    ]

    operations = [
        TrigramExtension(),
    ]
