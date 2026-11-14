from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0019_feedorder_flock_feedtransfer_from_flock_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='dailyentry',
            name='cull_count',
            field=models.PositiveIntegerField(
                default=0,
                help_text='Birds intentionally removed (culled), tracked separately from deaths',
            ),
        ),
    ]
