from django.db import models
from unidadmedida.models import UnidadMedida


class Presentacion(models.Model):

    cantidad = models.DecimalField(
        max_digits=12,
        decimal_places=4
    )

    medida = models.ForeignKey(
        UnidadMedida,
        on_delete=models.CASCADE,
        related_name='presentaciones'
    )

    def __str__(self):
        return f"{self.cantidad} {self.medida.abreviatura}"