from django.db import models
from clientes.models import Cliente
from metodopago.models import MetodoPago
from productos.models import Producto


class Venta(models.Model):
    id_venta = models.AutoField(primary_key=True, db_column='IdVenta')
    fecha = models.DateTimeField(auto_now_add=True, db_column='Fecha')
    total = models.DecimalField(max_digits=10, decimal_places=2, db_column='Total')

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name='ventas',
        db_column='IdCliente'
    )

    metodo_pago = models.ForeignKey(
        MetodoPago,
        on_delete=models.SET_NULL,
        null=True,
        related_name='ventas',
        db_column='IdMetPago'
    )

    def __str__(self):
        return f"Venta {self.id_venta} - {self.fecha}"

    class Meta:
        db_table = 'VENTAS'


class DetalleVenta(models.Model):
    id_detalle = models.AutoField(primary_key=True, db_column='IdDetalle')
    cantidad = models.IntegerField(db_column='Cantidad')
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, db_column='Subtotal')

    venta = models.ForeignKey(
        Venta,
        on_delete=models.CASCADE,
        related_name='detalles',
        db_column='IdVenta'
    )

    # FK a Producto
    producto = models.ForeignKey(
        Producto,
        on_delete=models.CASCADE,
        related_name='detalles_venta',
        db_column='IdProducto'
    )

    def __str__(self):
        return f"Detalle Venta {self.id_detalle}"

    class Meta:
        db_table = 'DETALLE_VENTA'