from django.db import models


class UnidadMedida(models.Model):

    nombre = models.CharField(
        max_length=50
    )

    abreviatura = models.CharField(
        max_length=10
    )

    estado = models.BooleanField(
        default=True
    )

    def __str__(self):
        return f"{self.nombre} ({self.abreviatura})"