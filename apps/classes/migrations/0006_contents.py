import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("classes", "0005_remove_classes_account_id_classes_student_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="Contents",
            fields=[
                (
                    "content_id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "class_content",
                    models.JSONField(blank=True, default=None, null=True),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "class_id",
                    models.OneToOneField(
                        db_column="class_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="contents",
                        to="classes.classes",
                    ),
                ),
            ],
        ),
    ]
