from django.db import migrations
from django.core.management import call_command


def populate_journal_data(apps, schema_editor):
    # This runs directly on production during 'python manage.py migrate'
    call_command('load_journal_data', force=True)


class Migration(migrations.Migration):

    dependencies = [
        ('academics', '0003_enrollment_custom_price_reason_and_more'),
        ('attendance', '0003_lesson_room'),
        ('leads', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(populate_journal_data, reverse_code=migrations.RunPython.noop),
    ]
