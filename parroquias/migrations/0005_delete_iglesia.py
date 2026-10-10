from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("parroquias", "0004_libro_apertura_cierre_estado"),
        ("sacramentos", "0005_remove_iglesia_campos"),
    ]

    operations = [
        migrations.DeleteModel(
            name="Iglesia",
        ),
    ]
