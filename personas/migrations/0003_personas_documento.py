from django.db import migrations, models
import django.db.models.deletion


def _normalizar(numero):
    return (numero or "").strip().replace(".", "").replace(" ", "").replace("-", "")


def migrar_padres(apps, schema_editor):
    """Crea/reutiliza un ``Documento`` (tipo CC) por cada padre."""
    Documento = apps.get_model("personas", "Documento")
    Padre = apps.get_model("personas", "Padre")
    for padre in Padre.objects.all().iterator():
        numero = _normalizar(padre.cedula)
        if not numero:
            continue
        documento, _ = Documento.objects.get_or_create(
            tipo_documento="CC", numero_documento=numero
        )
        padre.documento_id = documento.pk
        padre.save(update_fields=["documento"])


def migrar_madres(apps, schema_editor):
    """Crea/reutiliza un ``Documento`` (tipo CC) por cada madre."""
    Documento = apps.get_model("personas", "Documento")
    Madre = apps.get_model("personas", "Madre")
    for madre in Madre.objects.all().iterator():
        numero = _normalizar(madre.cedula)
        if not numero:
            continue
        documento, _ = Documento.objects.get_or_create(
            tipo_documento="CC", numero_documento=numero
        )
        madre.documento_id = documento.pk
        madre.save(update_fields=["documento"])


def limpiar_padrinos_sin_documento(apps, schema_editor):
    """Elimina padrinos sin documento (no se puede exigir documento sin él)."""
    Padrino = apps.get_model("personas", "Padrino")
    Padrino.objects.filter(documento__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("personas", "0002_fiel_sexo"),
    ]

    operations = [
        migrations.AddField(
            model_name="padre",
            name="documento",
            field=models.OneToOneField(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="padre",
                to="personas.documento",
                verbose_name="documento",
            ),
        ),
        migrations.RunPython(migrar_padres, migrations.RunPython.noop),
        migrations.RemoveField(model_name="padre", name="cedula"),
        migrations.AlterField(
            model_name="padre",
            name="documento",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="padre",
                to="personas.documento",
                verbose_name="documento",
            ),
        ),
        migrations.AddField(
            model_name="madre",
            name="documento",
            field=models.OneToOneField(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="madre",
                to="personas.documento",
                verbose_name="documento",
            ),
        ),
        migrations.RunPython(migrar_madres, migrations.RunPython.noop),
        migrations.RemoveField(model_name="madre", name="cedula"),
        migrations.AlterField(
            model_name="madre",
            name="documento",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="madre",
                to="personas.documento",
                verbose_name="documento",
            ),
        ),
        migrations.RunPython(limpiar_padrinos_sin_documento, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="padrino",
            name="documento",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="padrino",
                to="personas.documento",
                verbose_name="documento",
            ),
        ),
    ]
