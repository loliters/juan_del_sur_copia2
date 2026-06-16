# ventas/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Venta, DetalleVenta
from metodopago.models import MetodoPago
from clientes.models import Cliente
from inventario.models import Inventario
from productos.models import Producto
from django.db import models
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.template.loader import render_to_string
from django.utils import timezone
from fpdf import FPDF
import io
import json
import re

# ========================
# FUNCIÓN AUXILIAR PARA OBTENER INVENTARIO
# ========================
def obtener_inventario(producto):
    inventario, _ = Inventario.objects.get_or_create(
        producto=producto,
        defaults={'stock_actual': 0, 'tipo_unidad': None}  # Ajusta según tu modelo
    )
    return inventario

# ========================
# CRUD DE VENTAS
# ========================

def ver_ventas(request):
    if request.session.get('usuario_id') is None:
        return redirect('login')
    
    ventas = Venta.objects.select_related('cliente', 'metodo_pago').all().order_by('-fecha')
    paginator = Paginator(ventas, 20)
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    ventas_con_detalles = []
    for venta in page_obj:
        detalles = DetalleVenta.objects.filter(venta=venta).select_related('inventario__producto')
        ventas_con_detalles.append({
            'venta': venta,
            'detalles': detalles,
        })
    
    return render(request, 'ventas/ver_ventas.html', {
        'ventas': ventas_con_detalles,
        'page_obj': page_obj,
        'total_ventas': paginator.count,
        'es_cajero': request.session.get('rol') == 'cajero',
    })

def editar_venta(request, id):
    if request.session.get('usuario_id') is None:
        return redirect('login')
    
    venta = get_object_or_404(Venta, id_venta=id)
    cliente_original = venta.cliente
    detalles_actuales = DetalleVenta.objects.filter(venta=venta).select_related('inventario__producto')
    
    if request.method == "POST":
        cliente_id = request.POST.get('cliente_id')
        metodo_pago_id = request.POST.get('metodo_pago_id')
        productos_data = request.POST.getlist('productos')
        
        errores = False
        if cliente_id and int(cliente_id) != cliente_original.id_cliente:
            messages.error(request, f'❌ No se puede cambiar el cliente de una venta existente.')
            errores = True
        if not metodo_pago_id:
            messages.error(request, 'Debe seleccionar un método de pago')
            errores = True
        if not productos_data and not detalles_actuales.exists():
            messages.error(request, 'Debe agregar al menos un producto')
            errores = True
        
        if not errores:
            try:
                cliente = cliente_original
                metodo_pago = MetodoPago.objects.get(id_met_pago=metodo_pago_id)
                venta.metodo_pago = metodo_pago
                
                nuevos_productos = {}
                for item_json in productos_data:
                    item_json = item_json.strip()
                    if not item_json or item_json in ['null', 'undefined']:
                        continue
                    item_json = item_json.replace("'", '"')
                    item = json.loads(item_json)
                    cod = item.get('cod')
                    if not cod:
                        continue
                    cantidad = int(item.get('cantidad', 1))
                    precio = float(item.get('precio', 0))
                    if cantidad > 0:
                        nuevos_productos[cod] = {'cantidad': cantidad, 'precio': precio}
                
                # Si no hay productos válidos, eliminar la venta y restaurar stock
                if len(nuevos_productos) == 0:
                    for detalle in detalles_actuales:
                        inv = detalle.inventario
                        inv.stock_actual += detalle.cantidad
                        inv.save()
                        detalle.delete()
                    venta.delete()
                    if 'carrito' in request.session:
                        del request.session['carrito']
                    messages.success(request, f'✅ Venta #{id} eliminada porque no tenía productos')
                    return redirect('ventas:ver_ventas')
                
                detalles_dict = {d.inventario.producto.codProducto: d for d in detalles_actuales}
                total_venta = 0
                
                # 1. Eliminar productos que ya no están
                for cod, detalle in list(detalles_dict.items()):
                    if cod not in nuevos_productos:
                        inv = detalle.inventario
                        inv.stock_actual += detalle.cantidad
                        inv.save()
                        detalle.delete()
                
                # 2. Actualizar o crear nuevos
                for cod, data in nuevos_productos.items():
                    producto = Producto.objects.get(codProducto=cod)
                    cantidad = data['cantidad']
                    precio = data['precio']
                    subtotal = cantidad * precio
                    total_venta += subtotal
                    
                    inventario = obtener_inventario(producto)
                    
                    if cod in detalles_dict:
                        detalle = detalles_dict[cod]
                        diferencia = cantidad - detalle.cantidad
                        if diferencia > 0:
                            if inventario.stock_actual < diferencia:
                                messages.error(request, f'Stock insuficiente para {producto.nomProducto}')
                                return redirect('ventas:editar_venta', id=id)
                            inventario.stock_actual -= diferencia
                        elif diferencia < 0:
                            inventario.stock_actual += abs(diferencia)
                        inventario.save()
                        detalle.cantidad = cantidad
                        detalle.subtotal = subtotal
                        detalle.save()
                    else:
                        if inventario.stock_actual < cantidad:
                            messages.error(request, f'Stock insuficiente para {producto.nomProducto}')
                            return redirect('ventas:editar_venta', id=id)
                        inventario.stock_actual -= cantidad
                        inventario.save()
                        DetalleVenta.objects.create(
                            venta=venta,
                            inventario=inventario,
                            cantidad=cantidad,
                            subtotal=subtotal
                        )
                
                venta.total = total_venta
                venta.save()
                if 'carrito' in request.session:
                    del request.session['carrito']
                messages.success(request, f'✓ Venta #{venta.id_venta} actualizada - Total: Bs {venta.total:.2f}')
                return redirect('ventas:ver_ventas')
                
            except Exception as e:
                messages.error(request, f'Error al actualizar: {str(e)}')
    
    # GET
    clientes = Cliente.objects.filter(estado=True)
    metodos_pago = MetodoPago.objects.all()
    detalles = DetalleVenta.objects.filter(venta=venta).select_related('inventario__producto')
    productos_disponibles = Producto.objects.filter(estado='activo')
    
    for detalle in detalles:
        subtotal = float(detalle.subtotal) if detalle.subtotal else 0.0
        cantidad = int(detalle.cantidad) if detalle.cantidad else 1
        if cantidad > 0 and subtotal > 0:
            detalle.precio_unitario = round(subtotal / cantidad, 2)
        else:
            precio_producto = float(detalle.inventario.producto.precioVenta) if detalle.inventario.producto.precioVenta else 0.0
            detalle.precio_unitario = round(precio_producto, 2)
    
    return render(request, 'ventas/editar_venta.html', {
        'venta': venta,
        'clientes': clientes,
        'metodos_pago': metodos_pago,
        'detalles': detalles,
        'productos_disponibles': productos_disponibles,
    })

def eliminar_venta(request, id):
    if request.session.get('usuario_id') is None:
        return redirect('login')
    
    venta = get_object_or_404(Venta, id_venta=id)
    if request.method == "POST":
        try:
            detalles = DetalleVenta.objects.filter(venta=venta).select_related('inventario__producto')
            for detalle in detalles:
                inv = detalle.inventario
                inv.stock_actual += detalle.cantidad
                inv.save()
            detalles.delete()
            venta.delete()
            messages.success(request, f' Venta #{id} eliminada y stock restaurado')
            return redirect('ventas:ver_ventas')
        except Exception as e:
            messages.error(request, f' Error al eliminar venta: {str(e)}')
    return render(request, 'ventas/eliminar_venta.html', {'venta': venta})

# ========================
# CARRITO DE COMPRAS
# ========================

def agregar_al_carrito(request):
    if request.session.get('usuario_id') is None:
        return redirect('login')
    
    if request.method == 'POST':
        producto_id = request.POST.get('producto_id')
        cantidad = int(request.POST.get('cantidad', 1))
        producto = get_object_or_404(Producto, codProducto=producto_id)
        inventario = obtener_inventario(producto)
        
        if inventario.stock_actual < cantidad:
            messages.error(request, f'Stock insuficiente para {producto.nomProducto}')
            return redirect('dashboard_cajero')
        
        carrito = request.session.get('carrito', {'items': [], 'total': 0})
        encontrado = False
        for item in carrito['items']:
            if item.get('cod') == producto_id:
                nueva_cantidad = item['cantidad'] + cantidad
                if nueva_cantidad > inventario.stock_actual:
                    messages.error(request, f'Stock insuficiente para {producto.nomProducto}')
                    return redirect('dashboard_cajero')
                item['cantidad'] = nueva_cantidad
                item['subtotal'] = item['precio'] * item['cantidad']
                encontrado = True
                break
        if not encontrado:
            carrito['items'].append({
                'cod': producto.codProducto,
                'id': producto.id,
                'nombre': producto.nomProducto,
                'precio': float(producto.precioVenta),
                'cantidad': cantidad,
                'subtotal': float(producto.precioVenta) * cantidad
            })
        carrito['total'] = sum(item['subtotal'] for item in carrito['items'])
        request.session['carrito'] = carrito
        messages.success(request, f' Agregado {producto.nomProducto} al carrito')
    return redirect('dashboard_cajero')

def eliminar_del_carrito(request, cod):
    if request.session.get('usuario_id') is None:
        return redirect('login')
    carrito = request.session.get('carrito', {'items': [], 'total': 0})
    carrito['items'] = [item for item in carrito['items'] if item.get('cod') != cod]
    carrito['total'] = sum(item.get('subtotal', 0) for item in carrito['items'])
    request.session['carrito'] = carrito
    messages.success(request, ' Producto eliminado del carrito')
    return redirect('dashboard_cajero')

def seleccionar_cliente(request):
    if request.session.get('usuario_id') is None:
        return redirect('login')
    
    if request.method == 'POST':
        cliente_id = request.POST.get('cliente_id')
        if cliente_id:
            cliente = get_object_or_404(Cliente, id_cliente=cliente_id, estado=True)
            request.session['cliente_venta'] = cliente.id_cliente
            messages.success(request, f' Cliente {cliente.nombre} seleccionado')
        else:
            request.session['cliente_venta'] = None
            messages.info(request, 'Venta sin cliente registrado')
        return redirect('dashboard_cajero')
    
    query = request.GET.get('q', '').strip()
    clientes = Cliente.objects.filter(estado=True).order_by('nombre')
    if query:
        clientes = clientes.filter(models.Q(carnet__icontains=query) | models.Q(nombre__icontains=query))
    return render(request, 'ventas/seleccionar_cliente.html', {
        'clientes': clientes,
        'query': query,
    })

def registro_venta(request):
    if request.session.get('usuario_id') is None:
        return redirect('login')
    
    carrito = request.session.get('carrito', {'items': [], 'total': 0})
    if not carrito['items']:
        messages.error(request, 'El carrito está vacío')
        return redirect('dashboard_cajero')
    
    if request.method == 'POST':
        metodo_pago = request.POST.get('metodo_pago', 'QR')
        cliente_id = request.session.get('cliente_venta')
        if not cliente_id:
            messages.error(request, 'Seleccione un cliente')
            return redirect('dashboard_cajero')
        
        try:
            # Validar cantidades > 0
            for item in carrito['items']:
                if item['cantidad'] <= 0:
                    messages.error(request, f'La cantidad debe ser mayor a 0')
                    return redirect('dashboard_cajero')
            
            # Verificar stock en inventario
            for item in carrito['items']:
                producto = Producto.objects.get(id=item['id'])
                inventario = obtener_inventario(producto)
                if inventario.stock_actual < item['cantidad']:
                    messages.error(request, f'Stock insuficiente para {producto.nomProducto}')
                    return redirect('dashboard_cajero')
            
            metodo, _ = MetodoPago.objects.get_or_create(tipoPago=metodo_pago)
            cliente = Cliente.objects.filter(id_cliente=cliente_id, estado=True).first()
            if not cliente:
                messages.error(request, 'Seleccione un cliente válido')
                return redirect('dashboard_cajero')
            
            venta = Venta.objects.create(
                total=carrito['total'],
                cliente=cliente,
                metodo_pago=metodo
            )
            
            # Crear detalles y descontar stock
            for item in carrito['items']:
                producto = Producto.objects.get(id=item['id'])
                inventario = obtener_inventario(producto)
                inventario.stock_actual -= item['cantidad']
                inventario.save()
                
                DetalleVenta.objects.create(
                    venta=venta,
                    inventario=inventario,
                    cantidad=item['cantidad'],
                    subtotal=item['subtotal']
                )
            
            request.session['carrito'] = {'items': [], 'total': 0}
            request.session['cliente_venta'] = None
            messages.success(request, f'Venta #{venta.id_venta} registrada por Bs {venta.total:.2f}')
            return redirect('ventas:detalle_venta', id_venta=venta.id_venta)
            
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
            return redirect('dashboard_cajero')
    
    return redirect('dashboard_cajero')

# ========================
# AJAX - CARRITO
# ========================

@require_http_methods(["POST"])
def agregar_al_carrito_ajax(request):
    if request.session.get('usuario_id') is None:
        return JsonResponse({'success': False, 'error': 'Sesión no iniciada'}, status=401)
    
    producto_id = request.POST.get('producto_id')
    cantidad = int(request.POST.get('cantidad', 1))
    try:
        producto = Producto.objects.get(codProducto=producto_id, estado='activo')
        inventario = obtener_inventario(producto)
        if inventario.stock_actual < cantidad:
            return JsonResponse({'success': False, 'error': f'Stock insuficiente para {producto.nomProducto}'})
        
        carrito = request.session.get('carrito', {'items': [], 'total': 0})
        encontrado = False
        for item in carrito['items']:
            if str(item.get('cod')) == str(producto_id):
                nueva_cantidad = item['cantidad'] + cantidad
                if nueva_cantidad > inventario.stock_actual:
                    return JsonResponse({'success': False, 'error': f'No hay suficiente stock de {producto.nomProducto}'})
                item['cantidad'] = nueva_cantidad
                item['subtotal'] = item['precio'] * nueva_cantidad
                encontrado = True
                break
        if not encontrado:
            carrito['items'].append({
                'cod': producto.codProducto,
                'id': producto.id,
                'nombre': producto.nomProducto,
                'precio': float(producto.precioVenta),
                'cantidad': cantidad,
                'subtotal': float(producto.precioVenta) * cantidad
            })
        carrito['subtotal'] = sum(item['subtotal'] for item in carrito['items'])
        carrito['total'] = carrito['subtotal']
        request.session['carrito'] = carrito
        return JsonResponse({
            'success': True,
            'message': f'Agregado {producto.nomProducto} al carrito',
            'cart_items_count': len(carrito['items']),
            'cart_subtotal': carrito['subtotal'],
            'cart_total': carrito['total']
        })
    except Producto.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Producto no encontrado'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@require_http_methods(["POST"])
def actualizar_cantidad_carrito(request):
    if request.session.get('usuario_id') is None:
        return JsonResponse({'success': False, 'error': 'Sesión no iniciada'}, status=401)
    
    producto_cod = request.POST.get('producto_cod')
    nueva_cantidad = int(request.POST.get('cantidad', 1))
    if nueva_cantidad < 1:
        return JsonResponse({'success': False, 'error': 'La cantidad debe ser mayor a 0'})
    
    carrito = request.session.get('carrito', {'items': [], 'total': 0})
    item_encontrado = None
    for item in carrito['items']:
        if str(item.get('cod')) == str(producto_cod):
            try:
                producto = Producto.objects.get(codProducto=producto_cod)
                inventario = obtener_inventario(producto)
                if inventario.stock_actual < nueva_cantidad:
                    return JsonResponse({
                        'success': False,
                        'error': f'Stock insuficiente. Solo hay {inventario.stock_actual} unidades'
                    })
            except Producto.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Producto no encontrado'})
            item['cantidad'] = nueva_cantidad
            item['subtotal'] = item['precio'] * nueva_cantidad
            item_encontrado = item
            break
    
    if not item_encontrado:
        return JsonResponse({'success': False, 'error': 'Producto no encontrado en el carrito'})
    
    carrito['subtotal'] = sum(item['subtotal'] for item in carrito['items'])
    carrito['total'] = carrito['subtotal']
    request.session['carrito'] = carrito
    return JsonResponse({
        'success': True,
        'item_subtotal': item_encontrado['subtotal'],
        'cart_subtotal': carrito['subtotal'],
        'cart_total': carrito['total'],
        'cart_items_count': len(carrito['items'])
    })

@require_http_methods(["POST"])
def eliminar_del_carrito_ajax(request):
    if request.session.get('usuario_id') is None:
        return JsonResponse({'success': False, 'error': 'Sesión no iniciada'}, status=401)
    
    producto_cod = request.POST.get('producto_cod')
    carrito = request.session.get('carrito', {'items': [], 'total': 0})
    carrito['items'] = [item for item in carrito['items'] if str(item.get('cod')) != str(producto_cod)]
    carrito['subtotal'] = sum(item.get('subtotal', 0) for item in carrito['items'])
    carrito['total'] = carrito['subtotal']
    request.session['carrito'] = carrito
    return JsonResponse({
        'success': True,
        'cart_subtotal': carrito['subtotal'],
        'cart_total': carrito['total'],
        'cart_items_count': len(carrito['items'])
    })

# ========================
# AJAX - BUSCAR PRODUCTOS
# ========================

def buscar_productos_ajax(request):
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        query = request.GET.get('q', '').strip()
        if query:
            productos = Producto.objects.filter(
                nomProducto__icontains=query,
                estado='activo'
            )[:10]
            data = [{
                'codProducto': p.codProducto,
                'nomProducto': p.nomProducto,
                'precioVenta': float(p.precioVenta),
                'stockActual': obtener_inventario(p).stock_actual  # ← Usamos inventario
            } for p in productos]
            return JsonResponse({'success': True, 'productos': data})
    return JsonResponse({'success': False, 'productos': []})

# ========================
# DETALLE, IMPRESIÓN Y PDF
# ========================

def detalle_venta(request, id_venta):
    venta = get_object_or_404(Venta.objects.select_related('cliente', 'metodo_pago'), id_venta=id_venta)
    detalles = DetalleVenta.objects.select_related('inventario__producto').filter(venta=venta)
    context = {
        'venta': venta,
        'detalles': detalles,
        'fecha_actual': timezone.now().strftime('%Y-%m-%d')
    }
    return render(request, 'ventas/detalle_venta.html', context)

def imprimir_venta_html(request, id_venta):
    venta = get_object_or_404(Venta.objects.select_related('cliente', 'metodo_pago'), id_venta=id_venta)
    detalles = DetalleVenta.objects.select_related('inventario__producto').filter(venta=venta)
    context = {
        'venta': venta,
        'detalles': detalles,
        'cliente': venta.cliente,
        'fecha_impresion': timezone.now()
    }
    html_string = render_to_string('ventas/venta_print.html', context)
    return HttpResponse(html_string)

class PDFVentaIndividual(FPDF):
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

def generar_pdf_venta(request, id_venta):
    venta = get_object_or_404(Venta.objects.select_related('cliente', 'metodo_pago'), id_venta=id_venta)
    detalles = DetalleVenta.objects.select_related('inventario__producto').filter(venta=venta)
    
    buffer = io.BytesIO()
    pdf = PDFVentaIndividual()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
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
    
    pdf.section_title('Información de la Venta')
    pdf.info_row('Numero de Venta', f"#{venta.id_venta}")
    pdf.info_row('Fecha', venta.fecha.strftime("%d/%m/%Y %H:%M"))
    pdf.info_row('Metodo de Pago', venta.metodo_pago.tipoPago)
    pdf.ln(5)
    
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