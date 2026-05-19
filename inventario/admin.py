from django.contrib import admin
from .models import Inventario


@admin.register(Inventario)
class InventarioAdmin(admin.ModelAdmin):

    list_display = (
        'id',
        'producto',
        'tipo_unidad',
        'stock_actual'
    )

    list_filter = (
        'tipo_unidad',
    )

    search_fields = (
        'producto__nomProducto',
    )