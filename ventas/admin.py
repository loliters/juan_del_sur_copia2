from django.contrib import admin
from .models import Venta, DetalleVenta

class DetalleVentaInline(admin.TabularInline):
    model = DetalleVenta
    extra = 1
    readonly_fields = ('subtotal',)

@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = ('id_venta', 'fecha', 'cliente', 'metodo_pago', 'total')
    list_filter = ('fecha', 'metodo_pago')
    search_fields = ('cliente__nombre',)  
    readonly_fields = ('fecha', 'total')
    inlines = [DetalleVentaInline]

@admin.register(DetalleVenta)
class DetalleVentaAdmin(admin.ModelAdmin):
    list_display = ('id_detalle', 'venta', 'producto', 'cantidad', 'subtotal')
    search_fields = ('venta__id_venta', 'producto__nomProducto')  # <-- CORRECCIÓN