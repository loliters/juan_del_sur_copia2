from django.db import models
from productos.models import Producto
from unidadmedida.models import UnidadMedida


class Inventario(models.Model):

    id = models.AutoField(
        primary_key=True
    )

    stock_actual = models.IntegerField(
        default=0
    )

    tipo_unidad = models.ForeignKey(
        UnidadMedida,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    producto = models.OneToOneField(
        Producto,
        on_delete=models.CASCADE,
        related_name='inventario'
    )

    def __str__(self):
        return f"{self.producto.nomProducto} - {self.stock_actual}"


    class Meta:
        db_table = 'inventario_inventario'