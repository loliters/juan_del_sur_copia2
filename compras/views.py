# compras/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import models
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.template.loader import render_to_string
from django.utils import timezone
from .models import Compra, DetalleCompra
from proveedores.models import Proveedor
from inventario.models import Inventario
from productos.models import Producto
from datetime import datetime
import json
import urllib.parse
from fpdf import FPDF
import io

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger 

# ========================
# FUNCIÓN AUXILIAR PARA OBTENER INVENTARIO
# ========================
def obtener_inventario(producto):
    inventario, _ = Inventario.objects.get_or_create(
        producto=producto,
        defaults={'stock_actual': 0}
    )
    return inventario

# ========================
# VER COMPRAS
# ========================

def ver_compras(request):
    if request.session.get('usuario_id') is None:
        return redirect('login')
    
    compras_qs = Compra.objects.filter(estado=True).select_related('proveedor').all().order_by('-fecha')
    paginator = Paginator(compras_qs, 5)
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    
    compras_con_detalles = []
    for compra in page_obj:
        detalles = DetalleCompra.objects.filter(compra=compra).select_related('inventario__producto')
        detalles_con_subtotal = []
        for detalle in detalles:
            precio = _obtener_precio_compra(detalle)
            subtotal = precio * detalle.cantidad
            detalles_con_subtotal.append({
                'detalle': detalle,
                'precio_unitario': precio,
                'subtotal': subtotal
            })
        compras_con_detalles.append({
            'compra': compra,
            'detalles': detalles_con_subtotal,
        })
    
    return render(request, 'compras/ver_compras.html', {
        'compras': compras_con_detalles,
        'page_obj': page_obj,
        'total_compras': paginator.count,
    })

# ========================
# CREAR COMPRA
# ========================

def crear_compra(request):
    if request.session.get('usuario_id') is None:
        return redirect('login')

    base_context = {
        'proveedores': Proveedor.objects.filter(estado=True),
        'productos_disponibles': Producto.objects.filter(estado__iexact='activo'),
    }

    if request.method == "POST":
        fecha_str = request.POST.get('fecha')
        try:
            fecha_compra = datetime.fromisoformat(fecha_str) if fecha_str else datetime.now()
        except:
            fecha_compra = datetime.now()

        proveedor_id = request.POST.get('proveedor_id')
        productos_data = request.POST.getlist('productos')

        if not proveedor_id or not productos_data:
            messages.error(request, 'Debe completar proveedor y productos')
            return render(request, 'compras/crear_compra.html', base_context)

        productos_validos = [p for p in productos_data if p.strip() not in ['', 'null', 'undefined', '[]']]
        if not productos_validos:
            messages.error(request, 'Debe agregar productos válidos')
            return render(request, 'compras/crear_compra.html', base_context)

        try:
            proveedor = Proveedor.objects.get(id=proveedor_id)
            total = 0
            items = []

            for item_json in productos_validos:
                if '%' in item_json:
                    item_json = urllib.parse.unquote(item_json)
                item = json.loads(item_json)
                producto = Producto.objects.get(codProducto=item['cod'])
                cantidad = int(item.get('cantidad', 1))
                precio = float(item.get('precio_compra', 0))
                total += cantidad * precio
                items.append((producto, cantidad))

            compra = Compra.objects.create(
                total=total,
                fecha=fecha_compra,
                proveedor=proveedor,
                estado=True
            )

            for producto, cantidad in items:
                inventario = obtener_inventario(producto)
                inventario.stock_actual += cantidad
                inventario.save()
                DetalleCompra.objects.create(
                    compra=compra,
                    inventario=inventario,
                    cantidad=cantidad
                )

            messages.success(request, f'Compra #{compra.id_compra} creada correctamente')
            return redirect('compras:detalle_compra', id_compra=compra.id_compra)

        except Exception as e:
            messages.error(request, str(e))

    return render(request, 'compras/crear_compra.html', base_context)

# ========================
# EDITAR COMPRA
# ========================

def editar_compra(request, id):
    if request.session.get('usuario_id') is None:
        return redirect('login')

    compra = get_object_or_404(Compra, id_compra=id)
    detalles_actuales = DetalleCompra.objects.filter(compra=compra).select_related('inventario__producto')

    if request.method == "POST":
        proveedor_id = request.POST.get('proveedor_id')
        if not proveedor_id:
            messages.error(request, 'Seleccione un proveedor')
            return redirect('compras:editar_compra', id=id)

        proveedor = Proveedor.objects.get(id=proveedor_id)
        compra.proveedor = proveedor

        productos_data = request.POST.getlist('productos')
        nuevos = {}
        total = 0

        for p in productos_data:
            if '%' in p:
                p = urllib.parse.unquote(p)
            try:
                item = json.loads(p)
                cod = item['cod']
                nuevos[cod] = {
                    'cantidad': int(item['cantidad']),
                    'precio': float(item['precio_compra'])
                }
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                messages.error(request, f'Error en los datos del producto: {e}')
                return redirect('compras:editar_compra', id=id)

        # Restaurar stock anterior (restar lo que se había sumado)
        for d in detalles_actuales:
            inv = d.inventario
            inv.stock_actual -= d.cantidad
            inv.save()

        # Eliminar detalles antiguos
        DetalleCompra.objects.filter(compra=compra).delete()

        # Agregar nuevos productos y sumar stock
        for cod, data in nuevos.items():
            try:
                producto = Producto.objects.get(codProducto=cod)
            except Producto.DoesNotExist:
                messages.error(request, f'Producto con código {cod} no encontrado')
                return redirect('compras:editar_compra', id=id)

            cantidad = data['cantidad']
            precio = data['precio']
            total += cantidad * precio

            inventario = obtener_inventario(producto)
            inventario.stock_actual += cantidad
            inventario.save()

            DetalleCompra.objects.create(
                compra=compra,
                inventario=inventario,
                cantidad=cantidad
            )

        compra.total = total
        compra.save()

        messages.success(request, f"Compra #{compra.id_compra} actualizada correctamente")
        return redirect('compras:ver_compras')

    # ========== GET: Mostrar formulario con datos actuales ==========
    # Preparar lista de detalles para el template
    detalles_data = []
    for detalle in detalles_actuales:
        producto = detalle.inventario.producto
        precio = _obtener_precio_compra(detalle)  # usa la función auxiliar
        subtotal = precio * detalle.cantidad
        detalles_data.append({
            'cod': producto.codProducto,
            'nombre': producto.nomProducto,
            'cantidad': detalle.cantidad,
            'precio_compra': precio,
            'subtotal': subtotal,
        })

    # Productos disponibles para agregar nuevos (puedes filtrar los que ya están)
    productos_disponibles = Producto.objects.filter(estado__iexact='activo')

    context = {
        'compra': compra,
        'proveedores': Proveedor.objects.filter(estado=True),
        'productos_disponibles': productos_disponibles,
        'detalles_data': detalles_data,          # <--- NUEVO: datos de los detalles actuales
        'total_compra': compra.total,            # <--- opcional
    }
    return render(request, 'compras/editar_compra.html', context)

# ========================
# ELIMINAR COMPRA (DESACTIVAR)
# ========================

def eliminar_compra(request, id):
    if request.session.get('usuario_id') is None:
        return redirect('login')
    
    compra = get_object_or_404(Compra, id_compra=id)
    if request.method == "POST":
        try:
            detalles = DetalleCompra.objects.filter(compra=compra).select_related('inventario__producto')
            for detalle in detalles:
                inventario = detalle.inventario
                inventario.stock_actual -= detalle.cantidad
                inventario.save()
            compra.estado = False
            compra.save()
            messages.success(request, f'Compra #{id} eliminada y stock ajustado')
            return redirect('compras:ver_compras')
        except Exception as e:
            messages.error(request, f'Error al desactivar compra: {str(e)}')
            return redirect('compras:ver_compras')
    return render(request, 'compras/eliminar_compra.html', {'compra': compra})

# ========================
# COMPRAS DESACTIVADAS
# ========================

def compras_eliminadas(request):
    if request.session.get('usuario_id') is None:
        return redirect('login')
    compras = Compra.objects.filter(estado=False).select_related('proveedor').order_by('-fecha')
    compras_con_detalles = []
    for compra in compras:
        detalles = DetalleCompra.objects.filter(compra=compra).select_related('inventario__producto')
        detalles_con_subtotal = []
        for detalle in detalles:
            precio = _obtener_precio_compra(detalle)
            subtotal = precio * detalle.cantidad
            detalles_con_subtotal.append({'detalle': detalle, 'precio_unitario': precio, 'subtotal': subtotal})
        compras_con_detalles.append({'compra': compra, 'detalles': detalles_con_subtotal})
    return render(request, 'compras/compras_eliminadas.html', {'compras': compras_con_detalles})

# ========================
# ACTIVAR COMPRA (REHACER REABASTECIMIENTO)
# ========================

def activar_compra(request, id):
    if request.session.get('usuario_id') is None:
        return redirect('login')
    
    compra = get_object_or_404(Compra, id_compra=id)
    try:
        detalles = DetalleCompra.objects.filter(compra=compra).select_related('inventario__producto')
        for detalle in detalles:
            inventario = detalle.inventario
            inventario.stock_actual += detalle.cantidad
            inventario.save()
        compra.estado = True
        compra.save()
        messages.success(request, f'Compra #{id} activada y stock reabastecido')
        return redirect('compras:compras_desactivadas')
    except Exception as e:
        messages.error(request, f'Error al activar compra: {str(e)}')
        return redirect('compras:compras_desactivadas')

# ========================
# RECUPERAR COMPRA (alias de activar)
# ========================

def recuperar_compra(request, id):
    return activar_compra(request, id)

# ========================
# FUNCIÓN AUXILIAR: Obtener precio de compra
# ========================

def _obtener_precio_compra(detalle):
    producto = detalle.inventario.producto
    if hasattr(producto, 'precioCompra') and producto.precioCompra:
        return float(producto.precioCompra)
    if hasattr(producto, 'precioVenta') and producto.precioVenta:
        return float(producto.precioVenta)
    return 0.0

# ========================
# CLASE PDF PARA COMPRAS
# ========================

class PDFCompraIndividual(FPDF):
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

# ========================
# DETALLE DE COMPRA (UNIFICADO)
# ========================

def detalle_compra(request, id_compra):
    compra = get_object_or_404(Compra.objects.select_related('proveedor'), id_compra=id_compra)
    detalles = DetalleCompra.objects.select_related('inventario__producto').filter(compra=compra)
    accion = request.GET.get('accion', 'ver')
    
    if accion == 'pdf':
        return _generar_pdf_compra(compra, detalles)
    
    if accion == 'imprimir':
        context = {
            'compra': compra,
            'detalles': detalles,
            'proveedor': compra.proveedor,
            'fecha_impresion': timezone.now(),
            'modo_impresion': True,
        }
        return render(request, 'compras/detalle_compra_print.html', context)
    
    context = {
        'compra': compra,
        'detalles': detalles,
        'fecha_actual': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
    }
    return render(request, 'compras/detalle_compra.html', context)

def imprimir_compra_html(request, id_compra):
    compra = get_object_or_404(Compra.objects.select_related('proveedor'), id_compra=id_compra)
    detalles = DetalleCompra.objects.select_related('inventario__producto').filter(compra=compra)
    context = {
        'compra': compra,
        'detalles': detalles,
        'proveedor': compra.proveedor,
        'fecha_impresion': timezone.now()
    }
    html_string = render_to_string('compras/compra_print.html', context)
    return HttpResponse(html_string)

def generar_pdf_compra(request, id_compra):
    compra = get_object_or_404(Compra.objects.select_related('proveedor'), id_compra=id_compra)
    detalles = DetalleCompra.objects.select_related('inventario__producto').filter(compra=compra)
    return _generar_pdf_compra(compra, detalles)

def _generar_pdf_compra(compra, detalles):
    buffer = io.BytesIO()
    pdf = PDFCompraIndividual()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    proveedor = compra.proveedor
    pdf.section_title('Información del Proveedor')
    pdf.info_row('Nombre', proveedor.nomProv)
    pdf.info_row('Dirección', proveedor.direccion)
    pdf.info_row('Teléfono', proveedor.telefono)
    pdf.info_row('Email', proveedor.email)
    pdf.ln(3)
    
    pdf.section_title('Información de la Compra')
    pdf.info_row('Número de Compra', f"#{compra.id_compra}")
    pdf.info_row('Fecha', compra.fecha.strftime("%d/%m/%Y %H:%M"))
    pdf.info_row('Estado', 'Activa' if compra.estado else 'Inactiva')
    pdf.ln(5)
    
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_fill_color(37, 99, 235)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(25, 8, 'Código', 1, 0, 'C', 1)
    pdf.cell(70, 8, 'Producto', 1, 0, 'L', 1)
    pdf.cell(20, 8, 'Cant.', 1, 0, 'C', 1)
    pdf.cell(30, 8, 'P. Unit.', 1, 0, 'R', 1)
    pdf.cell(30, 8, 'Subtotal', 1, 1, 'R', 1)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font('Helvetica', '', 9)
    
    for detalle in detalles:
        producto = detalle.inventario.producto
        subtotal = detalle.cantidad * (producto.precioCompra or 0)
        pdf.cell(25, 7, producto.codProducto or '', 1, 0, 'C')
        pdf.cell(70, 7, producto.nomProducto[:35], 1, 0, 'L')
        pdf.cell(20, 7, str(detalle.cantidad), 1, 0, 'C')
        pdf.cell(30, 7, f"Bs {float(producto.precioCompra or 0):.2f}", 1, 0, 'R')
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
    response['Content-Disposition'] = f'attachment; filename="compra_{compra.id_compra}.pdf"'
    return response

# ========================
# AJAX - CARRITO DE COMPRA
# ========================

@require_http_methods(["POST"])
def agregar_al_carrito_compra_ajax(request):
    if request.session.get('usuario_id') is None:
        return JsonResponse({'success': False, 'error': 'Sesión no iniciada'}, status=401)
    producto_id = request.POST.get('producto_id')
    cantidad = int(request.POST.get('cantidad', 1))
    precio_compra = float(request.POST.get('precio_compra', 0))
    try:
        producto = Producto.objects.get(codProducto=producto_id, estado__iexact='Activo')
        carrito = request.session.get('carrito_compra', {'items': [], 'total': 0})
        encontrado = False
        for item in carrito['items']:
            if str(item.get('cod')) == str(producto_id):
                item['cantidad'] += cantidad
                item['subtotal'] = item['precio_compra'] * item['cantidad']
                encontrado = True
                break
        if not encontrado:
            carrito['items'].append({
                'cod': producto.codProducto, 'id': producto.id, 'nombre': producto.nomProducto,
                'precio_compra': precio_compra, 'cantidad': cantidad, 'subtotal': precio_compra * cantidad
            })
        carrito['total'] = sum(item['subtotal'] for item in carrito['items'])
        request.session['carrito_compra'] = carrito
        return JsonResponse({'success': True, 'message': f'Agregado {producto.nomProducto}', 'cart_items_count': len(carrito['items']), 'cart_total': carrito['total']})
    except Producto.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Producto no encontrado'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@require_http_methods(["POST"])
def actualizar_cantidad_carrito_compra(request):
    if request.session.get('usuario_id') is None:
        return JsonResponse({'success': False, 'error': 'Sesión no iniciada'}, status=401)
    producto_cod = request.POST.get('producto_cod')
    nueva_cantidad = int(request.POST.get('cantidad', 1))
    if nueva_cantidad < 1:
        return JsonResponse({'success': False, 'error': 'Cantidad inválida'})
    carrito = request.session.get('carrito_compra', {'items': [], 'total': 0})
    item_encontrado = None
    for item in carrito['items']:
        if str(item.get('cod')) == str(producto_cod):
            item['cantidad'] = nueva_cantidad
            item['subtotal'] = item['precio_compra'] * nueva_cantidad
            item_encontrado = item
            break
    if not item_encontrado:
        return JsonResponse({'success': False, 'error': 'Producto no encontrado'})
    carrito['total'] = sum(item['subtotal'] for item in carrito['items'])
    request.session['carrito_compra'] = carrito
    return JsonResponse({'success': True, 'item_subtotal': item_encontrado['subtotal'], 'cart_total': carrito['total'], 'cart_items_count': len(carrito['items'])})

@require_http_methods(["POST"])
def eliminar_del_carrito_compra_ajax(request):
    if request.session.get('usuario_id') is None:
        return JsonResponse({'success': False, 'error': 'Sesión no iniciada'}, status=401)
    producto_cod = request.POST.get('producto_cod')
    carrito = request.session.get('carrito_compra', {'items': [], 'total': 0})
    carrito['items'] = [item for item in carrito['items'] if str(item.get('cod')) != str(producto_cod)]
    carrito['total'] = sum(item.get('subtotal', 0) for item in carrito['items'])
    request.session['carrito_compra'] = carrito
    return JsonResponse({'success': True, 'cart_total': carrito['total'], 'cart_items_count': len(carrito['items'])})

def buscar_productos_compra_ajax(request):
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({'success': False, 'productos': []})
    try:
        productos = Producto.objects.filter(
            models.Q(codProducto__icontains=query) | models.Q(nomProducto__icontains=query),
            estado__iexact='Activo' 
        )[:10]
        data = []
        for p in productos:
            precio_compra = getattr(p, 'precioCompra', None)
            if precio_compra is None:
                precio_compra = getattr(p, 'precioVenta', 0)
            data.append({
                'codProducto': str(p.codProducto) if p.codProducto else '',
                'nomProducto': p.nomProducto if p.nomProducto else '',
                'precioCompra': float(precio_compra) if precio_compra else 0.0,
                'stockActual': int(obtener_inventario(p).stock_actual)  # Usamos inventario
            })
        return JsonResponse({'success': True, 'productos': data})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})