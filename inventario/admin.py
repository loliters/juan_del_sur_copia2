from django.contrib import admin
from .models import Inventario


@admin.register(Inventario)
class InventarioAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'producto',
        'stock_actual',
        'accion',
        'estado',
        'tipo_unidad',
    )

    list_filter = (
        'estado',
        'tipo_unidad',
    )

    search_fields = (
        'producto__nomProducto',
    )