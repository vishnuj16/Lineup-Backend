# Generated by Django 5.1.7 on 2025-04-01 06:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0002_room_game_started'),
    ]

    operations = [
        migrations.AddField(
            model_name='player',
            name='unique_id',
            field=models.CharField(default='', max_length=100),
        ),
    ]
