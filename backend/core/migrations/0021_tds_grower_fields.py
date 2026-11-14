from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0020_dailyentry_cull_count'),
    ]

    operations = [
        migrations.AddField(
            model_name='farm',
            name='pan',
            field=models.CharField(blank=True, help_text='Grower PAN (10 chars). Used for TDS reporting.', max_length=10),
        ),
        migrations.AddField(
            model_name='farm',
            name='entity_type',
            field=models.CharField(
                choices=[
                    ('individual', 'Individual'), ('huf', 'HUF'),
                    ('firm', 'Partnership / Firm'), ('company', 'Company'),
                    ('llp', 'LLP'), ('fpo', 'FPO'), ('other', 'Other'),
                ],
                default='individual',
                help_text='Grower entity type — drives the TDS rate (1% for Individual/HUF, 2% otherwise)',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='billconfig', name='apply_tds',
            field=models.BooleanField(default=True, help_text='Deduct TDS on the net amount payable to the grower'),
        ),
        migrations.AddField(
            model_name='billconfig', name='apply_tds_thresholds',
            field=models.BooleanField(default=True, help_text="If ON, skip TDS when this bill <= single limit AND the grower's FY total <= annual limit"),
        ),
        migrations.AddField(
            model_name='billconfig', name='tds_single_payment_limit',
            field=models.DecimalField(decimal_places=2, default=30000.00, help_text='Per-payment TDS threshold (Sec 194C)', max_digits=12),
        ),
        migrations.AddField(
            model_name='billconfig', name='tds_annual_limit',
            field=models.DecimalField(decimal_places=2, default=100000.00, help_text='Annual aggregate TDS threshold per grower (Sec 194C)', max_digits=12),
        ),
        migrations.AddField(
            model_name='bill', name='tds_rate_pct',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=5),
        ),
        migrations.AddField(
            model_name='bill', name='tds_amount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name='bill', name='tds_pan_missing',
            field=models.BooleanField(default=False, help_text='Grower had no valid PAN when this bill was generated'),
        ),
        migrations.AddField(
            model_name='bill', name='amount_paid',
            field=models.DecimalField(decimal_places=2, default=0, help_text='net_payable minus TDS', max_digits=12),
        ),
    ]
