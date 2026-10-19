from django.db import models


class RolUsuario(models.TextChoices):
    SECRETARIO = "SECRETARIO", "Secretario(a)"
    SACERDOTE = "SACERDOTE", "Sacerdote"


class TipoDocumento(models.TextChoices):
    CC = "CC", "Cédula de Ciudadanía"
    TI = "TI", "Tarjeta de Identidad"
    RC = "RC", "Registro Civil"
    CE = "CE", "Cédula de Extranjería"
    PA = "PA", "Pasaporte"


class EstadoCivil(models.TextChoices):
    SOLTERO = "soltero", "Soltero/a"
    CASADO = "casado", "Casado/a"
    VIUDO = "viudo", "Viudo/a"
    DIVORCIADO = "divorciado", "Divorciado/a"
    UNION_LIBRE = "union_libre", "Unión libre"
    SEPARADO = "separado", "Separado/a"
    ANULADO = "anulado", "Matrimonio anulado"


class RespuestaDoctrina(models.TextChoices):
    SI = "SI", "Sí"
    NO = "NO", "No"
    NS = "NS", "No sabe"


class SiNo(models.TextChoices):
    SI = "SI", "Sí"
    NO = "NO", "No"


class CargoMinisterial(models.TextChoices):
    PARROCO = "Párroco", "Párroco"
    VICARIO = "Vicario", "Vicario"
    DIACONO = "Diácono", "Diácono"
    CATEQUISTA = "Catequista", "Catequista"
    SACRISTAN = "Sacristán", "Sacristán"
    SERVIDOR_LITURGICO = "Servidor Litúrgico", "Servidor Litúrgico"


class TipoHijo(models.TextChoices):
    BIOLOGICO = "Biológico", "Biológico"
    ADOPTIVO = "Adoptivo", "Adoptivo"
    CRIANZA = "Crianza", "Crianza"


class TipoSacramento(models.TextChoices):
    BAUTISMO = "BAUTISMO", "Bautismo"
    PRIMERA_COMUNION = "PRIMERA_COMUNION", "Primera Comunión"
    CONFIRMACION = "CONFIRMACION", "Confirmación"
    MATRIMONIO = "MATRIMONIO", "Matrimonio"


class TipoLibro(models.TextChoices):
    BAUTISMOS = "BAUTISMOS", "Bautismos"
    PRIMERA_COMUNION = "PRIMERA_COMUNION", "Primera Comunión"
    CONFIRMACIONES = "CONFIRMACIONES", "Confirmaciones"
    MATRIMONIOS = "MATRIMONIOS", "Matrimonios"


class EstadoRegistro(models.TextChoices):
    ACTIVO = "ACTIVO", "Activo"
    ANULADO = "ANULADO", "Anulado"
    CORREGIDO = "CORREGIDO", "Corregido"
    ARCHIVADO = "ARCHIVADO", "Archivado"


class EstadoLibro(models.TextChoices):
    ABIERTO = "ABIERTO", "Abierto"
    CERRADO = "CERRADO", "Cerrado"


class Sexo(models.TextChoices):
    HOMBRE = "H", "Hombre"
    MUJER = "M", "Mujer"


class TipoAnotacionMarginal(models.TextChoices):
    CONFIRMACION = "CONFIRMACION", "Confirmación"
    MATRIMONIO = "MATRIMONIO", "Matrimonio"
    ORDEN_SAGRADO = "ORDEN_SAGRADO", "Orden sagrado"
    PROFESION_RELIGIOSA = "PROFESION_RELIGIOSA", "Profesión religiosa"
    CAMBIO_RITO = "CAMBIO_RITO", "Cambio de rito"
    ADOPCION = "ADOPCION", "Adopción"
    DEFUNCION = "DEFUNCION", "Defunción"
    CORRECCION = "CORRECCION", "Corrección"
    ANULACION = "ANULACION", "Anulación"
    OTRO = "OTRO", "Otro"


class EstadoAnotacion(models.TextChoices):
    ANOTADA = "ANOTADA", "Anotada"
    POR_COMUNICAR = "POR_COMUNICAR", "Por comunicar"
    COMUNICADA = "COMUNICADA", "Comunicada"


class AccionHistorial(models.TextChoices):
    CREACION = "CREACION", "Creación"
    MODIFICACION = "MODIFICACION", "Modificación"
    ANULACION = "ANULACION", "Anulación"
    CORRECCION = "CORRECCION", "Corrección"
    ARCHIVADO = "ARCHIVADO", "Archivado"
    CERTIFICADO = "CERTIFICADO", "Certificado expedido"


class ResultadoProclama(models.TextChoices):
    PUBLICADA = "PUBLICADA", "Publicada"
    SIN_IMPEDIMENTOS = "SIN_IMPEDIMENTOS", "Sin impedimentos"
    CON_IMPEDIMENTO = "CON_IMPEDIMENTO", "Con impedimento"
    DISPENSADA = "DISPENSADA", "Dispensada"
    DESIERTA = "DESIERTA", "Desierta"


class RelacionCertificado(models.TextChoices):
    TITULAR = "TITULAR", "El mismo titular"
    PADRE_MADRE = "PADRE_MADRE", "Padre o madre"
    FAMILIAR = "FAMILIAR", "Familiar"
    APODERADO = "APODERADO", "Apoderado"
    ENTIDAD = "ENTIDAD", "Entidad"
    OTRO = "OTRO", "Otro"


class FinalidadCertificado(models.TextChoices):
    MATRIMONIO = "MATRIMONIO", "Matrimonio"
    CONFIRMACION = "CONFIRMACION", "Confirmación"
    PRIMERA_COMUNION = "PRIMERA_COMUNION", "Primera comunión"
    TRAMITE_CIVIL = "TRAMITE_CIVIL", "Trámite civil"
    OTRO = "OTRO", "Otro"
