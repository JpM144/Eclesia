from django.db import models


class Pais(models.Model):
    nombre = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name = "país"
        verbose_name_plural = "países"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Departamento(models.Model):
    nombre = models.CharField(max_length=100)
    pais = models.ForeignKey(Pais, on_delete=models.PROTECT, related_name="departamentos")

    class Meta:
        verbose_name = "departamento"
        verbose_name_plural = "departamentos"
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(fields=["pais", "nombre"], name="unico_departamento_por_pais")
        ]

    def __str__(self):
        return f"{self.nombre} - {self.pais}"


class Municipio(models.Model):
    nombre = models.CharField(max_length=100)
    departamento = models.ForeignKey(
        Departamento, on_delete=models.PROTECT, related_name="municipios"
    )

    class Meta:
        verbose_name = "municipio"
        verbose_name_plural = "municipios"
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["departamento", "nombre"], name="unico_municipio_por_departamento"
            )
        ]

    def __str__(self):
        return f"{self.nombre} - {self.departamento}"
