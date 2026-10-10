from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("sacramentos", "0004_sacramento_libro_y_numeracion"),
    ]

    operations = [
        migrations.RemoveField(model_name="confirmacion", name="iglesia_bautismo"),
        migrations.RemoveField(model_name="primeracomunion", name="iglesia_bautismo"),
        migrations.RemoveField(model_name="sacramento", name="iglesia"),
    ]
