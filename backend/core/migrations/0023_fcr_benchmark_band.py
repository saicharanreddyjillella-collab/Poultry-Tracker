from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0022_billconfig_feed_reconciliation_tolerance'),
    ]

    operations = [
        migrations.AddField(
            model_name='farm',
            name='fcr_benchmark_enabled',
            field=models.BooleanField(default=False, help_text='Apply fixed-benchmark FCR premium/deduction (independent of area-avg FCR recovery)'),
        ),
        migrations.AddField(
            model_name='billconfig', name='fcr_benchmark',
            field=models.DecimalField(decimal_places=2, default=1.75, help_text='Target FCR; beating earns a premium, missing a deduction', max_digits=5),
        ),
        migrations.AddField(
            model_name='billconfig', name='fcr_benchmark_tolerance_pct',
            field=models.DecimalField(decimal_places=2, default=5.00, help_text='Neutral band around the benchmark (± %); no adjustment inside it', max_digits=5),
        ),
        migrations.AddField(
            model_name='billconfig', name='fcr_premium_per_kg_per_step',
            field=models.DecimalField(decimal_places=3, default=0.300, help_text='₹/kg premium per 0.1 FCR below the band', max_digits=6),
        ),
        migrations.AddField(
            model_name='billconfig', name='fcr_deduction_per_kg_per_step',
            field=models.DecimalField(decimal_places=3, default=0.300, help_text='₹/kg deduction per 0.1 FCR above the band', max_digits=6),
        ),
        migrations.AddField(
            model_name='billconfig', name='fcr_benchmark_max_adjustment_per_kg',
            field=models.DecimalField(decimal_places=3, default=2.000, help_text='Cap on the per-kg premium/deduction magnitude', max_digits=6),
        ),
        migrations.AddField(
            model_name='bill', name='fcr_benchmark_adjustment',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
    ]
