from django.db import migrations, models


def preserve_existing(apps, schema_editor):
    preferences = apps.get_model("timezones", "TimezonePreference")
    preferences.objects.using(schema_editor.connection.alias).update(timezone_initialized=True)


class Migration(migrations.Migration):
    dependencies = [("timezones", "0004_delete_timezoneprompt")]
    operations = [
        migrations.AddField(
            model_name="timezonepreference",
            name="timezone_initialized",
            field=models.BooleanField(default=False, editable=False),
        ),
        migrations.RunPython(preserve_existing, migrations.RunPython.noop),
    ]
