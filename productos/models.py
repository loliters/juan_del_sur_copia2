from django.db import models
from decimal import Decimal
from categorias.models import Categoria
from usuarios.models import Usuario
from presentacion.models import Presentacion


class Producto(models.Model):

    ESTADO_CHOICES = [
        ('activo', 'Activo'),
        ('inactivo', 'Inactivo'),
    ]

    codProducto = models.CharField(
        max_length=45,
        unique=True,
        verbose_name="Código de Producto",
        null=True,
        blank=True
    )

    nomProducto = models.CharField(
        max_length=100,
        verbose_name="Nombre del Producto"
    )

    precioCompra = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )

    precioVenta = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )

    stockMinimo = models.IntegerField(
        default=0
    )

    estado = models.CharField(
        max_length=10,
        choices=ESTADO_CHOICES,
        default='activo'
    )

    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='productos'
    )

    presentacion = models.ForeignKey(
        Presentacion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    @property
    def stockActual(self):
        try:
            return self.inventario.stock_actual
        except:
            return 0


    @stockActual.setter
    def stockActual(self, value):

        from inventario.models import Inventario

        inv, created = Inventario.objects.get_or_create(
            producto=self
        )

        inv.stock_actual = value
        inv.save()

    def __str__(self):
        return self.nomProducto

    class Meta:
        db_table = 'productos'
        ordering = ['nomProducto']