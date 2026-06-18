from django.db import models
from proveedores.models import Proveedor
from productos.models import Producto  # Asegúrate de que la app se llame 'productos'


class Compra(models.Model):
    id_compra = models.AutoField(primary_key=True, db_column='IdCompre')
    total = models.DecimalField(max_digits=10, decimal_places=2, db_column='Total')
    fecha = models.DateTimeField(db_column='Fecha')
    estado = models.BooleanField(default=True, db_column='Estado')
    proveedor = models.ForeignKey(
        Proveedor,
        on_delete=models.CASCADE,
        related_name='compras_realizadas',
        db_column='IdProv'
    )

    def __str__(self):
        return f"Compra #{self.id_compra} - Total: {self.total}"

    class Meta:
        verbose_name = "Compra"
        verbose_name_plural = "Compras"
        db_table = 'COMPRA'


class DetalleCompra(models.Model):
    id_detalle_compra = models.AutoField(primary_key=True, db_column='IdDetalleCompra')
    cantidad = models.IntegerField(db_column='Cantidad')
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, db_column='Subtotal', editable=False)

    compra = models.ForeignKey(
        Compra,
        on_delete=models.CASCADE,
        related_name='detalles',
        db_column='IdCompra'
    )

    # FK a Producto
    producto = models.ForeignKey(
        Producto,
        on_delete=models.CASCADE,
        related_name='detalles_compra',
        db_column='IdProducto'
    )

    def __str__(self):
        return f"Detalle {self.id_detalle_compra} (Cant: {self.cantidad})"

    def save(self, *args, **kwargs):
        """Calcula automáticamente el subtotal antes de guardar"""
        if self.producto and self.producto.precioCompra:
            self.subtotal = self.cantidad * self.producto.precioCompra
        else:
            self.subtotal = 0
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Detalle de Compra"
        verbose_name_plural = "Detalles de Compras"
        db_table = 'DETALLE_COMPRA'