from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0021_tds_grower_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='billconfig',
            name='feed_reconciliation_tolerance_pct',
            field=models.DecimalField(
                decimal_places=2,
                default=5.00,
                help_text='Allowed % gap between feed dispatched and consumed before a flock is flagged',
                max_digits=5,
            ),
        ),
    ]
