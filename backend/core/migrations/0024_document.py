import core.models
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0023_fcr_benchmark_band'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Document',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('doc_type', models.CharField(choices=[('agreement', 'Farmer Agreement'), ('kyc', 'KYC / ID Proof'), ('bank', 'Bank Proof'), ('vet_certificate', 'Vet / Cull Certificate'), ('invoice', 'Invoice / Bill Copy'), ('other', 'Other')], default='other', max_length=20)),
                ('title', models.CharField(blank=True, help_text='Short label; defaults to the file name', max_length=200)),
                ('file', models.FileField(upload_to=core.models.document_upload_path)),
                ('original_name', models.CharField(blank=True, max_length=255)),
                ('notes', models.TextField(blank=True)),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('farm', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='documents', to='core.farm')),
                ('flock', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='documents', to='core.flock')),
                ('uploaded_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='uploaded_documents', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-uploaded_at']},
        ),
    ]
