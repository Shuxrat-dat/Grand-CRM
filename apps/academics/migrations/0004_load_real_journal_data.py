from django.db import migrations
from django.core.management import call_command


def populate_journal_data(apps, schema_editor):
    # Intentionally a no-op: this used to wipe and reload all data during migrate.
    # Load initial journal data explicitly with: python manage.py load_journal_data
    return


class Migration(migrations.Migration):

    dependencies = [
        ('academics', '0003_enrollment_custom_price_reason_and_more'),
        ('attendance', '0003_lesson_room'),
        ('leads', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(populate_journal_data, reverse_code=migrations.RunPython.noop),
    ]
