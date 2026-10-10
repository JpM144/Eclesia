# Generated manually: apertura/cierre del libro, un solo libro abierto por tipo.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parroquias', '0003_delete_grupocatequesis'),
    ]

    operations = [
        migrations.RenameField(
            model_name='libro',
            old_name='fecha_creacion',
            new_name='fecha_apertura',
        ),
        migrations.AlterField(
            model_name='libro',
            name='fecha_apertura',
            field=models.DateField(verbose_name='fecha de apertura'),
        ),
        migrations.AddField(
            model_name='libro',
            name='total_folios',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='total de folios'),
        ),
        migrations.AddField(
            model_name='libro',
            name='ministro_apertura',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='libros_abiertos',
                to='parroquias.ministro',
                verbose_name='ministro que abre',
            ),
        ),
        migrations.AddField(
            model_name='libro',
            name='estado',
            field=models.CharField(
                choices=[('ABIERTO', 'Abierto'), ('CERRADO', 'Cerrado')],
                default='ABIERTO',
                max_length=10,
                verbose_name='estado',
            ),
        ),
        migrations.AddField(
            model_name='libro',
            name='fecha_cierre',
            field=models.DateField(blank=True, null=True, verbose_name='fecha de cierre'),
        ),
        migrations.AddField(
            model_name='libro',
            name='ministro_cierre',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='libros_cerrados',
                to='parroquias.ministro',
                verbose_name='ministro que cierra',
            ),
        ),
        migrations.AddField(
            model_name='libro',
            name='nota_cierre',
            field=models.TextField(blank=True, default='', verbose_name='nota de cierre'),
            preserve_default=False,
        ),
        migrations.AddConstraint(
            model_name='libro',
            constraint=models.UniqueConstraint(
                condition=models.Q(('estado', 'ABIERTO')),
                fields=('parroquia', 'tipo_libro'),
                name='un_libro_abierto_por_tipo',
                violation_error_message='Ya existe un libro abierto de este tipo en la parroquia.',
            ),
        ),
        migrations.AddConstraint(
            model_name='libro',
            constraint=models.CheckConstraint(
                condition=~models.Q(('estado', 'CERRADO'), ('fecha_cierre__isnull', True)),
                name='libro_cerrado_requiere_fecha_cierre',
            ),
        ),
        migrations.AddConstraint(
            model_name='libro',
            constraint=models.CheckConstraint(
                condition=models.Q(('fecha_cierre__isnull', True))
                | models.Q(('fecha_cierre__gte', models.F('fecha_apertura'))),
                name='libro_cierre_no_anterior_a_apertura',
            ),
        ),
        migrations.AddConstraint(
            model_name='libro',
            constraint=models.CheckConstraint(
                condition=models.Q(('total_folios__isnull', True))
                | models.Q(('total_folios__gt', 0)),
                name='libro_total_folios_positivo',
            ),
        ),
    ]