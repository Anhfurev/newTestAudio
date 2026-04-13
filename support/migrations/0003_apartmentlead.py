from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("support", "0002_intent_intentdetail"),
    ]

    operations = [
        migrations.CreateModel(
            name="ApartmentLead",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("owner_name", models.CharField(max_length=120)),
                ("owner_phone", models.CharField(max_length=40)),
                ("title", models.CharField(max_length=200)),
                ("location", models.CharField(max_length=200)),
                ("price", models.DecimalField(decimal_places=2, max_digits=14)),
                ("bedrooms", models.PositiveIntegerField(default=1)),
                ("area_sqm", models.PositiveIntegerField(default=0)),
                ("description", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("published", "Published")], default="pending", max_length=20)),
                ("agent_name", models.CharField(blank=True, max_length=120)),
                ("agent_phone", models.CharField(blank=True, max_length=40)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("assigned_agent", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="apartment_leads", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]