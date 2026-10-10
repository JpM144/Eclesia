# Generated manually: partidas numeradas por libro, no por folio.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parroquias', '0004_libro_apertura_cierre_estado'),
        ('sacramentos', '0003_anotacionmarginal_documentosacramento_and_more'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='sacramento',
            name='unico_numero_por_folio',
        ),
        migrations.AddField(
            model_name='sacramento',
            name='libro',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='sacramentos',
                to='parroquias.libro',
                verbose_name='libro',
            ),
        ),
        migrations.AddConstraint(
            model_name='sacramento',
            constraint=models.UniqueConstraint(
                fields=('libro', 'numero'),
                name='unico_numero_por_libro',
                violation_error_message='Ya existe una partida con ese número en este libro',
            ),
        ),
    ]