from datetime import timedelta

from django.db import migrations

# Las anotaciones de anulación se guardaban con tipo CORRECCION (el tipo ANULACION
# no existía) en la misma transacción que el historial de ANULACION. Solo se pueden
# distinguir con seguridad las de una partida ANULADA cuya anotación se creó en el
# mismo momento que ese historial de ANULACION; el resto no se toca.
TOLERANCIA = timedelta(seconds=2)


def _anotaciones_de_anulacion(AnotacionMarginal, HistorialSacramento, tipo):
    for anotacion in AnotacionMarginal.objects.filter(
        tipo=tipo, sacramento__estado="ANULADO"
    ).iterator():
        historial = (
            HistorialSacramento.objects.filter(
                sacramento_id=anotacion.sacramento_id, accion="ANULACION"
            )
            .order_by("fecha")
            .first()
        )
        if historial is None:
            continue
        if abs(historial.fecha - anotacion.creado_en) <= TOLERANCIA:
            yield anotacion


def marcar_anulaciones(apps, schema_editor):
    AnotacionMarginal = apps.get_model("sacramentos", "AnotacionMarginal")
    HistorialSacramento = apps.get_model("sacramentos", "HistorialSacramento")
    for anotacion in _anotaciones_de_anulacion(
        AnotacionMarginal, HistorialSacramento, "CORRECCION"
    ):
        anotacion.tipo = "ANULACION"
        anotacion.save(update_fields=["tipo"])


def revertir(apps, schema_editor):
    AnotacionMarginal = apps.get_model("sacramentos", "AnotacionMarginal")
    HistorialSacramento = apps.get_model("sacramentos", "HistorialSacramento")
    for anotacion in _anotaciones_de_anulacion(
        AnotacionMarginal, HistorialSacramento, "ANULACION"
    ):
        anotacion.tipo = "CORRECCION"
        anotacion.save(update_fields=["tipo"])


class Migration(migrations.Migration):
    dependencies = [
        ("sacramentos", "0008_agregar_tipo_anotacion_anulacion"),
    ]

    operations = [
        migrations.RunPython(marcar_anulaciones, revertir),
    ]
