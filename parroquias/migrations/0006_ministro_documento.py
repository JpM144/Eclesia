from django.db import migrations, models
import django.db.models.deletion


def migrar_ministros(apps, schema_editor):
    """Crea/reutiliza un ``Documento`` (tipo CC) para ministros sin documento."""
    Documento = apps.get_model("personas", "Documento")
    Ministro = apps.get_model("parroquias", "Ministro")
    for ministro in Ministro.objects.filter(documento__isnull=True).iterator():
        numero = (ministro.cedula or "").strip()
        numero = numero.replace(".", "").replace(" ", "").replace("-", "")
        if not numero:
            continue
        documento, _ = Documento.objects.get_or_create(
            tipo_documento="CC", numero_documento=numero
        )
        ministro.documento_id = documento.pk
        ministro.save(update_fields=["documento"])


class Migration(migrations.Migration):

    dependencies = [
        ("parroquias", "0005_delete_iglesia"),
        ("personas", "0003_personas_documento"),
    ]

    operations = [
        migrations.RunPython(migrar_ministros, migrations.RunPython.noop),
        migrations.RemoveField(model_name="ministro", name="cedula"),
        migrations.AlterField(
            model_name="ministro",
            name="documento",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="ministro",
                to="personas.documento",
                verbose_name="documento",
            ),
        ),
    ]
