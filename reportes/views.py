from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.db.models import Sum, F, Prefetch
from django.template.loader import render_to_string
from django.utils import timezone
from datetime import datetime, timedelta
from fpdf import FPDF
import io
import os

# Models
from ventas.models import Venta, DetalleVenta
from compras.models import Compra, DetalleCompra
from clientes.models import Cliente
from proveedores.models import Proveedor
from inventario.models import Inventario
from productos.models import Producto
from categorias.models import Categoria

from .utils import PDFReporteGeneral


# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================

def get_date_range(filter_type, custom_from=None, custom_to=None):
    """Obtiene el rango de fechas según el filtro seleccionado"""
    today = timezone.now().date()
    
    # Si hay fechas personalizadas, tienen prioridad
    if custom_from and custom_to:
        try:
            from_date = datetime.strptime(custom_from, '%Y-%m-%d').date()
            to_date = datetime.strptime(custom_to, '%Y-%m-%d').date()
            return from_date, to_date
        except:
            pass
    
    # Filtros preestablecidos
    if filter_type == 'ultimo_dia':
        return today, today
    elif filter_type == 'ultima_semana':
        return today - timedelta(days=7), today
    elif filter_type == 'este_mes':
        return today.replace(day=1), today
    elif filter_type == 'este_año':
        return today.replace(month=1, day=1), today
    
    return None, None


def filtrar_ventas(request):
    """Lógica de filtrado para ventas"""
    ventas = Venta.objects.select_related('cliente', 'metodo_pago').prefetch_related(
        Prefetch('detalles', queryset=DetalleVenta.objects.select_related('inventario__producto'))
    ).all()
    
    filtro_fecha = request.GET.get('filtro_fecha', '')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    producto_filter = request.GET.get('producto', '')
    categoria_filter = request.GET.get('categoria', '')
    
    # Filtrar por fecha
    from_date, to_date = get_date_range(filtro_fecha, fecha_desde, fecha_hasta)
    if from_date and to_date:
        ventas = ventas.filter(fecha__date__range=[from_date, to_date])
    
    # Filtrar por producto
    if producto_filter:
        if producto_filter == 'mas_vendido':
            detalles = DetalleVenta.objects.values('inventario__producto').annotate(
                total_cantidad=Sum('cantidad')
            ).order_by('-total_cantidad')
            if detalles:
                producto_id = detalles[0]['inventario__producto']
                ventas = ventas.filter(detalles__inventario__producto_id=producto_id)
        else:
            ventas = ventas.filter(detalles__inventario__producto_id=producto_filter)
    
    # Filtrar por categoría
    if categoria_filter and categoria_filter != '':
        try:
            ventas = ventas.filter(detalles__inventario__producto__categoria_id=categoria_filter)
        except:
            pass
    
    return ventas.distinct()


def filtrar_compras(request):
    """Lógica de filtrado para compras"""
    compras = Compra.objects.select_related('proveedor').prefetch_related(
        Prefetch('detalles', queryset=DetalleCompra.objects.select_related('inventario__producto'))
    ).all()
    
    filtro_fecha = request.GET.get('filtro_fecha', '')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    producto_filter = request.GET.get('producto', '')
    categoria_filter = request.GET.get('categoria', '')
    proveedor_filter = request.GET.get('proveedor', '')
    estado_inventario = request.GET.get('estado_inventario', '')
    
    # Filtrar por fecha
    from_date, to_date = get_date_range(filtro_fecha, fecha_desde, fecha_hasta)
    if from_date and to_date:
        compras = compras.filter(fecha__date__range=[from_date, to_date])
    
    # Filtrar por proveedor
    if proveedor_filter:
        compras = compras.filter(proveedor_id=proveedor_filter)
    
    # Filtrar por producto
    if producto_filter:
        if producto_filter == 'mas_comprado':
            detalles = DetalleCompra.objects.values('inventario__producto').annotate(
                total_cantidad=Sum('cantidad')
            ).order_by('-total_cantidad')
            if detalles:
                producto_id = detalles[0]['inventario__producto']
                compras = compras.filter(detalles__inventario__producto_id=producto_id)
        else:
            compras = compras.filter(detalles__inventario__producto_id=producto_filter)
    
    # Filtrar por categoría
    if categoria_filter and categoria_filter != '':
        try:
            compras = compras.filter(detalles__inventario__producto__categoria_id=categoria_filter)
        except:
            pass
    
    # Filtrar por estado en inventario
    if estado_inventario:
        if estado_inventario == 'agotado':
            compras = compras.filter(detalles__inventario__stock_actual=0)
        elif estado_inventario == 'bajo_stock':
            compras = compras.filter(
                detalles__inventario__stock_actual__lte=F('detalles__inventario__producto__stockMinimo')
            )
    
    return compras.distinct()


# =============================================================================
# VISTAS PRINCIPALES DE REPORTES
# =============================================================================

def ventas_report(request):
    """Vista principal del reporte de ventas"""
    ventas = filtrar_ventas(request)
    
    total_vendido = ventas.aggregate(total=Sum('total'))['total'] or 0
    cant_ventas = ventas.count()
    
    productos = Producto.objects.filter(estado='activo').select_related('categoria')
    categorias = Categoria.objects.filter(estado=True)
    clientes = Cliente.objects.filter(estado=True)
    
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    filtro_fecha = request.GET.get('filtro_fecha', '')
    
    from_date, to_date = get_date_range(filtro_fecha, fecha_desde, fecha_hasta)
    if from_date and to_date:
        fecha_reporte = f"{from_date.strftime('%Y-%m-%d')} - {to_date.strftime('%Y-%m-%d')}"
    else:
        fecha_reporte = "Todos los registros"
    
    context = {
        'ventas': ventas,
        'total_vendido': total_vendido,
        'cant_ventas': cant_ventas,
        'fecha_reporte': fecha_reporte,
        'productos': productos,
        'categorias': categorias,
        'clientes': clientes,
        'filtro_fecha': filtro_fecha,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
    }
    
    return render(request, 'reportes/ventas_report.html', context)


def compras_report(request):
    """Vista principal del reporte de compras"""
    compras = filtrar_compras(request)
    
    total_comprado = compras.aggregate(total=Sum('total'))['total'] or 0
    ordenes_realizadas = compras.count()
    
    productos = Producto.objects.filter(estado='activo').select_related('categoria')
    categorias = Categoria.objects.filter(estado=True)
    proveedores = Proveedor.objects.filter(estado=True)
    
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    filtro_fecha = request.GET.get('filtro_fecha', '')
    
    from_date, to_date = get_date_range(filtro_fecha, fecha_desde, fecha_hasta)
    if from_date and to_date:
        fecha_reporte = f"{from_date.strftime('%Y-%m-%d')} - {to_date.strftime('%Y-%m-%d')}"
    else:
        fecha_reporte = "Todos los registros"
    
    context = {
        'compras': compras,
        'total_comprado': total_comprado,
        'ordenes_realizadas': ordenes_realizadas,
        'fecha_reporte': fecha_reporte,
        'productos': productos,
        'categorias': categorias,
        'proveedores': proveedores,
        'filtro_fecha': filtro_fecha,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
    }
    
    return render(request, 'reportes/compras_report.html', context)


# =============================================================================
# CLASES PDF PARA FACTURAS INDIVIDUALES
# =============================================================================

class PDFVenta(FPDF):
    """Clase PDF personalizada para facturas de venta"""
    
    def header(self):
        self.set_font('Helvetica', 'B', 16)
        self.cell(0, 10, 'JUAN DEL SUR', 0, 1, 'C')
        self.set_font('Helvetica', '', 10)
        self.cell(0, 5, 'NIT: 1234567890', 0, 1, 'C')
        self.ln(5)
        self.set_font('Helvetica', 'B', 14)
        self.cell(0, 10, 'FACTURA DE VENTA', 0, 1, 'C')
        self.ln(5)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)
    
    def footer(self):
        self.set_y(-25)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 5, 'Gracias por su compra', 0, 0, 'C')
        self.ln(4)
        self.cell(0, 5, f'Impreso: {timezone.now().strftime("%d/%m/%Y %H:%M:%S")}', 0, 0, 'C')
    
    def section_title(self, title):
        self.set_font('Helvetica', 'B', 10)
        self.set_fill_color(37, 99, 235)
        self.set_text_color(255, 255, 255)
        self.cell(0, 8, f' {title}', 0, 1, 'L', 1)
        self.set_text_color(0, 0, 0)
        self.ln(2)
    
    def info_row(self, label, value):
        self.set_font('Helvetica', 'B', 9)
        self.cell(40, 5, f'{label}:', 0, 0)
        self.set_font('Helvetica', '', 9)
        self.cell(0, 5, str(value), 0, 1)


class PDFCompra(FPDF):
    """Clase PDF personalizada para órdenes de compra"""
    
    def header(self):
        self.set_font('Helvetica', 'B', 16)
        self.cell(0, 10, 'JUAN DEL SUR', 0, 1, 'C')
        self.set_font('Helvetica', '', 10)
        self.cell(0, 5, 'NIT: 1234567890', 0, 1, 'C')
        self.ln(5)
        self.set_font('Helvetica', 'B', 14)
        self.cell(0, 10, 'ORDEN DE COMPRA', 0, 1, 'C')
        self.ln(5)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)
    
    def footer(self):
        self.set_y(-25)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 5, 'Documento de compra oficial', 0, 0, 'C')
        self.ln(4)
        self.cell(0, 5, f'Impreso: {timezone.now().strftime("%d/%m/%Y %H:%M:%S")}', 0, 0, 'C')
    
    def section_title(self, title):
        self.set_font('Helvetica', 'B', 10)
        self.set_fill_color(37, 99, 235)
        self.set_text_color(255, 255, 255)
        self.cell(0, 8, f' {title}', 0, 1, 'L', 1)
        self.set_text_color(0, 0, 0)
        self.ln(2)
    
    def info_row(self, label, value):
        self.set_font('Helvetica', 'B', 9)
        self.cell(40, 5, f'{label}:', 0, 0)
        self.set_font('Helvetica', '', 9)
        self.cell(0, 5, str(value), 0, 1)


# =============================================================================
# GENERACIÓN DE PDF INDIVIDUALES (VENTA/COMPRA)
# =============================================================================

def generar_pdf_venta(request, id_venta):
    """Generar PDF de venta individual usando io.BytesIO"""
    venta = get_object_or_404(
        Venta.objects.select_related('cliente', 'metodo_pago'), 
        id_venta=id_venta
    )
    detalles = DetalleVenta.objects.select_related('inventario__producto').filter(venta=venta)
    
    buffer = io.BytesIO()
    pdf = PDFVenta()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Cliente
    cliente = venta.cliente
    pdf.section_title('Información del Cliente')
    pdf.info_row('Nombre', cliente.nombre)
    if cliente.razonSocial:
        pdf.info_row('Razon Social', cliente.razonSocial)
    pdf.info_row('Carnet', cliente.carnet)
    pdf.info_row('Telefono', cliente.telefono)
    pdf.info_row('Email', cliente.email)
    pdf.info_row('Direccion', f"{cliente.zona}, {cliente.calle} #{cliente.numeroCasa}")
    pdf.ln(3)
    
    # Venta
    pdf.section_title('Información de la Venta')
    pdf.info_row('Numero de Venta', f"#{venta.id_venta}")
    pdf.info_row('Fecha', venta.fecha.strftime("%d/%m/%Y %H:%M"))
    pdf.info_row('Metodo de Pago', venta.metodo_pago.tipoPago)
    pdf.ln(5)
    
    # Tabla
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_fill_color(37, 99, 235)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(25, 8, 'Codigo', 1, 0, 'C', 1)
    pdf.cell(70, 8, 'Producto', 1, 0, 'L', 1)
    pdf.cell(20, 8, 'Cant.', 1, 0, 'C', 1)
    pdf.cell(30, 8, 'P. Unit.', 1, 0, 'R', 1)
    pdf.cell(30, 8, 'Subtotal', 1, 1, 'R', 1)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font('Helvetica', '', 9)
    
    for detalle in detalles:
        producto = detalle.inventario.producto
        pdf.cell(25, 7, producto.codProducto or '', 1, 0, 'C')
        pdf.cell(70, 7, producto.nomProducto[:35], 1, 0, 'L')
        pdf.cell(20, 7, str(detalle.cantidad), 1, 0, 'C')
        pdf.cell(30, 7, f"Bs {float(producto.precioVenta):.2f}", 1, 0, 'R')
        pdf.cell(30, 7, f"Bs {float(detalle.subtotal):.2f}", 1, 1, 'R')
    
    pdf.ln(5)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(145, 10, 'TOTAL:', 0, 0, 'R')
    pdf.set_text_color(37, 99, 235)
    pdf.cell(40, 10, f"Bs {float(venta.total):.2f}", 0, 1, 'R')
    pdf.set_text_color(0, 0, 0)
    
    pdf.ln(20)
    pdf.set_font('Helvetica', '', 9)
    pdf.cell(90, 10, '_________________________', 0, 0, 'C')
    pdf.cell(90, 10, '_________________________', 0, 1, 'C')
    pdf.cell(90, 5, 'Firma del Cliente', 0, 0, 'C')
    pdf.cell(90, 5, 'Firma del Vendedor', 0, 1, 'C')
    
    pdf.output(buffer)
    buffer.seek(0)
    
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="venta_{id_venta}.pdf"'
    return response


def generar_pdf_compra(request, id_compra):
    """Generar PDF de compra individual usando io.BytesIO"""
    compra = get_object_or_404(
        Compra.objects.select_related('proveedor'), 
        id_compra=id_compra
    )
    detalles = DetalleCompra.objects.select_related('inventario__producto').filter(compra=compra)
    
    buffer = io.BytesIO()
    pdf = PDFCompra()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Proveedor
    proveedor = compra.proveedor
    pdf.section_title('Información del Proveedor')
    pdf.info_row('Nombre', proveedor.nomProv)
    pdf.info_row('Direccion', proveedor.direccion)
    pdf.info_row('Telefono', proveedor.telefono)
    pdf.info_row('Email', proveedor.email)
    pdf.ln(3)
    
    # Compra
    pdf.section_title('Información de la Compra')
    pdf.info_row('Numero de Compra', f"#{compra.id_compra}")
    pdf.info_row('Fecha', compra.fecha.strftime("%d/%m/%Y %H:%M"))
    pdf.info_row('Estado', 'Activa' if compra.estado else 'Inactiva')
    pdf.ln(5)
    
    # Tabla
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_fill_color(37, 99, 235)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(25, 8, 'Codigo', 1, 0, 'C', 1)
    pdf.cell(70, 8, 'Producto', 1, 0, 'L', 1)
    pdf.cell(20, 8, 'Cant.', 1, 0, 'C', 1)
    pdf.cell(30, 8, 'P. Unit.', 1, 0, 'R', 1)
    pdf.cell(30, 8, 'Subtotal', 1, 1, 'R', 1)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font('Helvetica', '', 9)
    
    for detalle in detalles:
        producto = detalle.inventario.producto
        subtotal = detalle.cantidad * producto.precioCompra
        pdf.cell(25, 7, producto.codProducto or '', 1, 0, 'C')
        pdf.cell(70, 7, producto.nomProducto[:35], 1, 0, 'L')
        pdf.cell(20, 7, str(detalle.cantidad), 1, 0, 'C')
        pdf.cell(30, 7, f"Bs {float(producto.precioCompra):.2f}", 1, 0, 'R')
        pdf.cell(30, 7, f"Bs {float(subtotal):.2f}", 1, 1, 'R')
    
    pdf.ln(5)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(145, 10, 'TOTAL:', 0, 0, 'R')
    pdf.set_text_color(37, 99, 235)
    pdf.cell(40, 10, f"Bs {float(compra.total):.2f}", 0, 1, 'R')
    pdf.set_text_color(0, 0, 0)
    
    pdf.ln(20)
    pdf.set_font('Helvetica', '', 9)
    pdf.cell(90, 10, '_________________________', 0, 0, 'C')
    pdf.cell(90, 10, '_________________________', 0, 1, 'C')
    pdf.cell(90, 5, 'Firma del Proveedor', 0, 0, 'C')
    pdf.cell(90, 5, 'Resp. de Compras', 0, 1, 'C')
    
    pdf.output(buffer)
    buffer.seek(0)
    
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="compra_{id_compra}.pdf"'
    return response


# =============================================================================
# VISTAS DE IMPRESIÓN HTML
# =============================================================================

def imprimir_venta(request, id_venta):
    """Vista para imprimir venta en formato HTML"""
    venta = get_object_or_404(
        Venta.objects.select_related('cliente', 'metodo_pago'), 
        id_venta=id_venta
    )
    detalles = DetalleVenta.objects.select_related('inventario__producto').filter(venta=venta)
    
    context = {
        'venta': venta,
        'detalles': detalles,
        'cliente': venta.cliente,
        'fecha_impresion': timezone.now()
    }
    html_string = render_to_string('reportes/venta_print.html', context)
    return HttpResponse(html_string)


def imprimir_compra(request, id_compra):
    """Vista para imprimir compra en formato HTML"""
    compra = get_object_or_404(
        Compra.objects.select_related('proveedor'), 
        id_compra=id_compra
    )
    detalles = DetalleCompra.objects.select_related('inventario__producto').filter(compra=compra)
    
    context = {
        'compra': compra,
        'detalles': detalles,
        'proveedor': compra.proveedor,
        'fecha_impresion': timezone.now()
    }
    html_string = render_to_string('reportes/compra_print.html', context)
    return HttpResponse(html_string)


# =============================================================================
# EXPORTACIÓN DE REPORTES GENERALES (PDF)
# =============================================================================

def exportar_ventas_pdf(request):
    """Generar PDF con reporte general de ventas filtradas (AGREGADO POR PRODUCTO)"""
    ventas = filtrar_ventas(request)
    
    # ===== 1. PROCESAR Y AGRUPAR DATOS POR PRODUCTO =====
    productos_agg = {}
    total_ventas = 0.0
    total_ganancia = 0.0
    
    for venta in ventas:
        for detalle in venta.detalles.select_related('inventario__producto'):
            producto = detalle.inventario.producto
            pid = producto.id  # Clave para agrupar sin duplicados
            
            precio_venta = float(producto.precioVenta) if producto.precioVenta is not None else 0.0
            precio_compra = float(producto.precioCompra) if producto.precioCompra is not None else 0.0
            cantidad = int(detalle.cantidad) if detalle.cantidad else 0
            subtotal = float(detalle.subtotal) if detalle.subtotal else 0.0
            ganancia = (precio_venta - precio_compra) * cantidad
            
            if pid not in productos_agg:
                productos_agg[pid] = {
                    'cod': producto.codProducto or '',
                    'nom': producto.nomProducto,
                    'cantidad': 0,
                    'subtotal': 0.0,
                    'ganancia': 0.0,
                }
            
            productos_agg[pid]['cantidad'] += cantidad
            productos_agg[pid]['subtotal'] += subtotal
            productos_agg[pid]['ganancia'] += ganancia
            
            total_ventas += subtotal
            total_ganancia += ganancia
    
    # Convertir a lista y calcular precio unitario promedio ponderado
    productos_data = list(productos_agg.values())
    for p in productos_data:
        p['precio_unit'] = p['subtotal'] / p['cantidad'] if p['cantidad'] > 0 else 0.0
        
    # ===== 2. RECONSTRUIR FILTROS PARA EL PDF =====
    filtro_fecha = request.GET.get('filtro_fecha', '')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    
    from_date, to_date = get_date_range(filtro_fecha, fecha_desde, fecha_hasta)
    if from_date and to_date:
        texto_fecha = f"{from_date.strftime('%d/%m/%Y')} - {to_date.strftime('%d/%m/%Y')}"
    elif filtro_fecha:
        nombres_filtro = {
            'ultimo_dia': 'Último día',
            'ultima_semana': 'Última semana',
            'este_mes': 'Este mes',
            'este_año': 'Este año',
        }
        texto_fecha = nombres_filtro.get(filtro_fecha, 'Todos')
    else:
        texto_fecha = 'Todos'
    
    producto_id = request.GET.get('producto', '')
    categoria_id = request.GET.get('categoria', '')
    
    texto_producto = 'Todos'
    if producto_id == 'mas_vendido':
        texto_producto = 'Más vendido'
    elif producto_id:
        prod = Producto.objects.filter(pk=producto_id).first()
        if prod:
            texto_producto = prod.nomProducto
    
    texto_categoria = 'Todas'
    if categoria_id:
        cat = Categoria.objects.filter(pk=categoria_id).first()
        if cat:
            texto_categoria = cat.nomCategoria
    
    filtros = {
        'Fecha': texto_fecha,
        'Producto': texto_producto,
        'Categoria': texto_categoria,
    }
    
    # ===== 3. GENERAR PDF =====
    buffer = io.BytesIO()
    pdf = PDFReporteGeneral()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    pdf.set_font('Helvetica', 'B', 16)
    pdf.cell(0, 10, 'REPORTE DE VENTAS', 0, 1, 'C')
    pdf.ln(5)
    pdf.filters_box(filtros)
    
    pdf.section_title('Resumen')
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(40, 6, 'Total Ventas:', 0, 0)
    pdf.cell(0, 6, f"{ventas.count()} registros", 0, 1)
    pdf.cell(40, 6, 'Productos únicos:', 0, 0)
    num_unicos = len(productos_data)
    pdf.cell(0, 6, f"{num_unicos}", 0, 1)
    pdf.ln(3)
    
    if productos_data:
        pdf.section_title('Detalle de Productos')
        pdf.products_table_header(include_profit=True)
        for prod in productos_data:
            pdf.product_row(
                producto={'cod': prod['cod'], 'nom': prod['nom']},
                cantidad=prod['cantidad'],
                precio_unit=prod['precio_unit'],
                subtotal=prod['subtotal'],
                ganancia=prod['ganancia']
            )
    else:
        pdf.set_font('Helvetica', 'I', 10)
        pdf.cell(0, 10, 'No hay datos para mostrar', 0, 1, 'C')
    
    pdf.ln(5)
    pdf.set_font('Helvetica', 'B', 11)
    pdf.totals_row('TOTAL VENDIDO:', total_ventas)
    pdf.totals_row('GANANCIA TOTAL:', total_ganancia, is_grand_total=True)
    
    pdf.output(buffer)
    buffer.seek(0)
    
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="reporte_ventas.pdf"'
    return response


def exportar_compras_pdf(request):
    """Generar PDF con reporte general de compras filtradas + proveedores (AGREGADO POR PRODUCTO)"""
    compras = filtrar_compras(request)
    
    # ===== 1. PROCESAR Y AGRUPAR DATOS POR PRODUCTO =====
    productos_agg = {}
    total_compras = 0.0
    proveedores_usados = set()
    
    for compra in compras:
        proveedor = compra.proveedor
        proveedores_usados.add(proveedor.nomProv)
        
        for detalle in compra.detalles.select_related('inventario__producto'):
            producto = detalle.inventario.producto
            pid = producto.id  # Clave para agrupar sin duplicados
            
            precio_compra = float(producto.precioCompra) if producto.precioCompra else 0.0
            cantidad = int(detalle.cantidad) if detalle.cantidad else 0
            subtotal = cantidad * precio_compra
            
            if pid not in productos_agg:
                productos_agg[pid] = {
                    'cod': producto.codProducto or '',
                    'nom': producto.nomProducto,
                    'cantidad': 0,
                    'subtotal': 0.0,
                    'precio_unit': 0.0,
                }
            
            productos_agg[pid]['cantidad'] += cantidad
            productos_agg[pid]['subtotal'] += subtotal
            total_compras += subtotal
    
    # Convertir a lista y calcular precio unitario promedio ponderado
    productos_data = list(productos_agg.values())
    for p in productos_data:
        p['precio_unit'] = p['subtotal'] / p['cantidad'] if p['cantidad'] > 0 else 0.0
        
    # ===== 2. RECONSTRUIR FILTROS PARA EL PDF =====
    filtro_fecha = request.GET.get('filtro_fecha', '')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')

    from_date, to_date = get_date_range(filtro_fecha, fecha_desde, fecha_hasta)
    if from_date and to_date:
        texto_fecha = f"{from_date.strftime('%d/%m/%Y')} - {to_date.strftime('%d/%m/%Y')}"
    elif filtro_fecha:
        nombres_filtro = {
            'ultimo_dia': 'Último día',
            'ultima_semana': 'Última semana',
            'este_mes': 'Este mes',
            'este_año': 'Este año',
        }
        texto_fecha = nombres_filtro.get(filtro_fecha, 'Todos')
    else:
        texto_fecha = 'Todos'

    producto_id = request.GET.get('producto', '')
    categoria_id = request.GET.get('categoria', '')
    proveedor_id = request.GET.get('proveedor', '')

    texto_producto = 'Todos'
    if producto_id == 'mas_comprado':
        texto_producto = 'Más comprado'
    elif producto_id:
        prod = Producto.objects.filter(pk=producto_id).first()
        if prod:
            texto_producto = prod.nomProducto

    texto_categoria = 'Todas'
    if categoria_id:
        cat = Categoria.objects.filter(pk=categoria_id).first()
        if cat:
            texto_categoria = cat.nomCategoria

    texto_proveedor = 'Todos'
    if proveedor_id:
        prov = Proveedor.objects.filter(pk=proveedor_id).first()
        if prov:
            texto_proveedor = prov.nomProv

    filtros = {
        'Fecha': texto_fecha,
        'Producto': texto_producto,
        'Categoria': texto_categoria,
        'Proveedor': texto_proveedor,
    }
    
    # ===== 3. GENERAR PDF =====
    buffer = io.BytesIO()
    pdf = PDFReporteGeneral()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    pdf.set_font('Helvetica', 'B', 16)
    pdf.cell(0, 10, 'REPORTE DE COMPRAS', 0, 1, 'C')
    pdf.ln(5)
    pdf.filters_box(filtros)
    
    pdf.section_title('Resumen')
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(40, 6, 'Total Compras:', 0, 0)
    pdf.cell(0, 6, f"{compras.count()} registros", 0, 1)
    pdf.cell(40, 6, 'Proveedores:', 0, 0)
    pdf.cell(0, 6, f"{len(proveedores_usados)} únicos", 0, 1)
    pdf.ln(3)
    
    if productos_data:
        pdf.section_title('Detalle de Productos')
        pdf.products_table_header(include_profit=False)
        for prod in productos_data:
            pdf.product_row(
                producto={'cod': prod['cod'], 'nom': prod['nom']},
                cantidad=prod['cantidad'],
                precio_unit=prod['precio_unit'],
                subtotal=prod['subtotal'],
                ganancia=None
            )
    
    pdf.ln(5)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.set_text_color(37, 99, 235)
    pdf.cell(130, 10, 'TOTAL COMPRADO:', 0, 0, 'R')
    pdf.cell(50, 10, f"Bs {total_compras:.2f}", 0, 1, 'R')
    pdf.set_text_color(0, 0, 0)
    
    if proveedores_usados:
        pdf.ln(10)
        pdf.section_title('Proveedores Involucrados')
        pdf.set_font('Helvetica', '', 10)
        proveedores_detalle = Proveedor.objects.filter(
            nomProv__in=proveedores_usados
        ).values('nomProv', 'direccion', 'telefono', 'email')
        
        for prov in proveedores_detalle:
            pdf.set_font('Helvetica', 'B', 10)
            pdf.cell(0, 6, prov['nomProv'], 0, 1)
            pdf.set_font('Helvetica', '', 9)
            pdf.cell(5, 5, '', 0, 0)
            direccion = prov['direccion'] or ''
            telefono = prov['telefono'] or ''
            email = prov['email'] or ''
            pdf.multi_cell(0, 5, f"Direccion: {direccion}\nTelefono: {telefono}\nEmail: {email}")
            pdf.ln(2)
    
    pdf.output(buffer)
    buffer.seek(0)
    
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="reporte_compras.pdf"'
    return response

# =============================================================================
# FUNCIÓN DE PRUEBA (DEBUG)
# =============================================================================

def test_pdf(request):
    """PDF de prueba simple para verificar que FPDF2 funciona"""
    buffer = io.BytesIO()
    pdf = PDFReporteGeneral()
    pdf.add_page()
    
    pdf.set_font('Helvetica', 'B', 20)
    pdf.cell(0, 10, 'PDF DE PRUEBA', 0, 1, 'C')
    pdf.ln(10)
    
    pdf.set_font('Helvetica', '', 12)
    pdf.cell(0, 10, 'Si ves esto, FPDF2 funciona correctamente', 0, 1, 'C')
    pdf.ln(5)
    pdf.cell(0, 10, 'El problema eran los datos, no el generador de PDF', 0, 1, 'C')
    
    pdf.ln(10)
    pdf.products_table_header(include_profit=True)
    pdf.product_row({'cod': 'TEST001', 'nom': 'Producto de Prueba'}, 10, 15.00, 150.00, 50.00)
    pdf.product_row({'cod': 'TEST002', 'nom': 'Otro Producto'}, 5, 20.00, 100.00, 30.00)
    
    pdf.ln(5)
    pdf.totals_row('TOTAL:', 250.00)
    
    pdf.output(buffer)
    buffer.seek(0)
    
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="test_fpdf2.pdf"'
    return response