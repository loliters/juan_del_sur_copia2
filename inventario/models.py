from django.db import models
from productos.models import Producto
from unidadmedida.models import UnidadMedida


class Inventario(models.Model):

    id = models.AutoField(
        primary_key=True,
    )

    stock_actual = models.IntegerField(
        default=0,
    )

    accion = models.CharField(
        max_length=50,
        blank=True,
        default='',
    )

    estado = models.BooleanField(
        default=True,
    )

    tipo_unidad = models.ForeignKey(
        UnidadMedida,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    producto = models.ForeignKey(
        Producto,
        on_delete=models.CASCADE,
        related_name='inventario',
    )

    def __str__(self):
        return f"{self.producto.nomProducto} - {self.stock_actual}"


    class Meta:
        db_table = 'inventario_inventario'