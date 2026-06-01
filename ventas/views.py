# ventas/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Venta, DetalleVenta
from metodopago.models import MetodoPago
from clientes.models import Cliente
from inventario.models import Inventario
from productos.models import Producto
from django.db import models  # ← Agregar al inicio del archivo

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger #para paginador / que no sea tan lento

# ========================
# CRUD DE VENTAS (Administrador)
# ========================

def ver_ventas(request):
    # Verificar sesión
    if request.session.get('usuario_id') is None:
        return redirect('login')
    
    # Obtener todas las ventas con sus relaciones
    ventas = Venta.objects.select_related('cliente', 'metodo_pago').all().order_by('-fecha')
    
    #CONFIGURACIÓN DEL PAGINADOR
    paginator = Paginator(ventas, 20)  # 20 ventas por página (ajustable)
    page_number = request.GET.get('page')
    
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)


    # Para cada venta, calcular los detalles
    ventas_con_detalles = []
    for venta in page_obj: #page_obj en lugar de ventas
        detalles = DetalleVenta.objects.filter(venta=venta).select_related('inventario__producto')
        
        ventas_con_detalles.append({
            'venta': venta,
            'detalles': detalles,
        })
    
    return render(request, 'ventas/ver_ventas.html', {
        'ventas': ventas_con_detalles,
        'page_obj': page_obj, #para cargar ciertos datos
        'total_ventas': paginator.count, #total de ventas, sin esto transaccion aparece solo 20
        'es_cajero': request.session.get('rol') == 'cajero',
    })

#Editar venta
def editar_venta(request, id):
    # Verificar sesión - cualquier usuario logueado puede editar
    if request.session.get('usuario_id') is None:
        return redirect('login')
    
    venta = get_object_or_404(Venta, id_venta=id)
    
    # Guardar cliente original para comparación
    cliente_original = venta.cliente
    
    # Obtener detalles actuales
    detalles_actuales = DetalleVenta.objects.filter(venta=venta).select_related('inventario__producto')
    
    if request.method == "POST":
        cliente_id = request.POST.get('cliente_id')
        metodo_pago_id = request.POST.get('metodo_pago_id')
        productos_data = request.POST.getlist('productos')
        
        # ========== DEBUG ==========
        print("=" * 60)
        print("EDITAR VENTA - POST RECIBIDO")
        print(f"Venta ID: {id}")
        print(f"Cliente ID recibido: {cliente_id}")
        print(f"Cliente original ID: {cliente_original.id_cliente}")
        print(f"Método Pago ID: {metodo_pago_id}")
        print(f"Total productos recibidos: {len(productos_data)}")
        for i, p in enumerate(productos_data):
            print(f"  Producto {i+1}: {p}")
        print("=" * 60)
        # ========== FIN DEBUG ==========
        
        errores = False
        
        # 🔴 VALIDACIÓN: No permitir cambiar el cliente
        if cliente_id and int(cliente_id) != cliente_original.id_cliente:
            messages.error(request, f'❌ No se puede cambiar el cliente de una venta existente. La venta pertenece a {cliente_original.nombre}')
            errores = True
        
        if not metodo_pago_id:
            messages.error(request, 'Debe seleccionar un método de pago')
            errores = True
        
        # ✅ CORREGIDO: Solo validar si NO hay productos en el formulario Y tampoco en la venta
        if not productos_data and not detalles_actuales.exists():
            messages.error(request, 'Debe agregar al menos un producto')
            errores = True
        
        if not errores:
            try:
                import json
                import re
                
                # Usar el cliente original, no el que viene del POST
                cliente = cliente_original
                metodo_pago = MetodoPago.objects.get(id_met_pago=metodo_pago_id)
                
                venta.metodo_pago = metodo_pago
                # NO modificar venta.cliente
                
                # Procesar productos del formulario
                nuevos_productos = {}
                
                for item_json in productos_data:
                    try:
                        # Limpiar el JSON
                        item_json = item_json.strip()
                        if not item_json or item_json == 'null' or item_json == 'undefined':
                            print(f"  Saltando item vacío: {item_json}")
                            continue
                        
                        # Intentar parsear el JSON
                        item_json = item_json.replace("'", '"')
                        item = json.loads(item_json)
                        
                        cod = item.get('cod')
                        if not cod:
                            print(f"  Producto sin código: {item}")
                            continue
                            
                        cantidad = int(item.get('cantidad', 1))
                        precio = float(item.get('precio', 0))
                        
                        # Solo agregar productos con cantidad > 0
                        if cantidad > 0:
                            nuevos_productos[cod] = {'cantidad': cantidad, 'precio': precio}
                            print(f"  ✓ Producto procesado: {cod} - Cantidad: {cantidad} - Precio: {precio}")
                        else:
                            print(f"  ⚠ Producto con cantidad 0, será eliminado: {cod}")
                        
                    except json.JSONDecodeError as e:
                        print(f"  ✗ Error JSON en: {item_json}")
                        print(f"    Error: {e}")
                        continue
                    except (ValueError, KeyError) as e:
                        print(f"  ✗ Error en datos: {e} - Item: {item_json}")
                        continue
                
                print(f"Total productos válidos: {len(nuevos_productos)}")
                
                # ============================================================
                # NUEVO: Si no hay productos válidos, eliminar la venta completa
                # ============================================================
                if len(nuevos_productos) == 0:
                    print("⚠️ No hay productos válidos, eliminando venta completa...")
                    
                    # Restaurar stock de todos los productos existentes
                    for detalle in detalles_actuales:
                        producto = detalle.inventario.producto
                        producto.stockActual += detalle.cantidad
                        producto.save()
                        
                        inventario = detalle.inventario
                        inventario.stock_actual = producto.stockActual
                        inventario.save()
                        
                        detalle.delete()
                        print(f"  ✓ Producto {detalle.inventario.producto.codProducto} eliminado y stock restaurado")
                    
                    # Eliminar la venta
                    venta.delete()
                    
                    # Limpiar carrito de sesión si existe
                    if 'carrito' in request.session:
                        del request.session['carrito']
                    
                    messages.success(request, f'✅ Venta #{id} eliminada porque no tenía productos')
                    return redirect('ventas:ver_ventas')
                # ============================================================
                
                # Diccionario de detalles actuales
                detalles_dict = {d.inventario.producto.codProducto: d for d in detalles_actuales}
                total_venta = 0
                
                # 1. Eliminar productos que ya no están en la nueva lista
                for cod, detalle in list(detalles_dict.items()):
                    if cod not in nuevos_productos:
                        try:
                            # Restaurar stock
                            producto = detalle.inventario.producto
                            producto.stockActual += detalle.cantidad
                            producto.save()
                            
                            inventario = detalle.inventario
                            inventario.stock_actual = producto.stockActual
                            inventario.save()
                            
                            detalle.delete()
                            print(f"  ✓ Producto eliminado: {cod}")
                        except Exception as e:
                            print(f"  ✗ Error eliminando detalle {cod}: {e}")
                
                # 2. Actualizar o crear nuevos productos
                for cod, data in nuevos_productos.items():
                    try:
                        producto = Producto.objects.get(codProducto=cod)
                        cantidad = data['cantidad']
                        precio = data['precio']
                        subtotal = cantidad * precio
                        total_venta += subtotal
                        
                        # Obtener o crear inventario
                        inventario, _ = Inventario.objects.get_or_create(
                            producto=producto,
                            defaults={'stock_actual': producto.stockActual, 'tipoUnidad': 'unidad'}
                        )
                        
                        if cod in detalles_dict:
                            # Actualizar producto existente
                            detalle = detalles_dict[cod]
                            diferencia = cantidad - detalle.cantidad
                            
                            if diferencia > 0:
                                # Se necesita más stock
                                if producto.stockActual < diferencia:
                                    messages.error(request, f'Stock insuficiente para {producto.nomProducto}. Disponible: {producto.stockActual}, Necesita: {diferencia}')
                                    return redirect('ventas:editar_venta', id=id)
                                producto.stockActual -= diferencia
                            elif diferencia < 0:
                                # Se devuelve stock
                                producto.stockActual += abs(diferencia)
                            
                            producto.save()
                            inventario.stock_actual = producto.stockActual
                            inventario.save()
                            
                            detalle.cantidad = cantidad
                            detalle.subtotal = subtotal
                            detalle.save()
                            print(f"  ✓ Detalle actualizado: {cod} - Cantidad: {cantidad}")
                        else:
                            # Crear nuevo producto
                            if producto.stockActual < cantidad:
                                messages.error(request, f'Stock insuficiente para {producto.nomProducto}. Disponible: {producto.stockActual}, Necesita: {cantidad}')
                                return redirect('ventas:editar_venta', id=id)
                            
                            producto.stockActual -= cantidad
                            producto.save()
                            inventario.stock_actual = producto.stockActual
                            inventario.save()
                            
                            DetalleVenta.objects.create(
                                venta=venta,
                                inventario=inventario,
                                cantidad=cantidad,
                                subtotal=subtotal
                            )
                            print(f"  ✓ Nuevo detalle creado: {cod}")
                            
                    except Producto.DoesNotExist:
                        messages.error(request, f'Producto con código {cod} no encontrado')
                        continue
                    except Exception as e:
                        print(f"  ✗ Error procesando producto {cod}: {e}")
                        messages.error(request, f'Error procesando producto: {str(e)}')
                        return redirect('ventas:editar_venta', id=id)
                
                # Guardar el total de la venta
                venta.total = total_venta
                venta.save()
                print(f"Total calculado: {total_venta}")
                print(f"Total guardado en venta: {venta.total}")
                
                # Limpiar carrito de sesión si existe
                if 'carrito' in request.session:
                    del request.session['carrito']
                
                messages.success(request, f'✓ Venta #{venta.id_venta} actualizada exitosamente - Total: Bs {venta.total:.2f}')
                return redirect('ventas:ver_ventas')
                
            except MetodoPago.DoesNotExist:
                messages.error(request, 'Método de pago no encontrado')
            except Exception as e:
                messages.error(request, f'Error al actualizar: {str(e)}')
                print(f"Error general: {e}")
                import traceback
                traceback.print_exc()
    
    # ==================== GET - Mostrar formulario ====================
    clientes = Cliente.objects.filter(estado=True)
    metodos_pago = MetodoPago.objects.all()
    detalles = DetalleVenta.objects.filter(venta=venta).select_related('inventario__producto')
    productos_disponibles = Producto.objects.filter(estado='activo')
    
    # Calcular precio_unitario para cada detalle
    for detalle in detalles:
        subtotal = float(detalle.subtotal) if detalle.subtotal else 0.0
        cantidad = int(detalle.cantidad) if detalle.cantidad else 1
        
        if cantidad > 0 and subtotal > 0:
            detalle.precio_unitario = round(subtotal / cantidad, 2)
        else:
            precio_producto = float(detalle.inventario.producto.precioVenta) if detalle.inventario.producto.precioVenta else 0.0
            detalle.precio_unitario = round(precio_producto, 2)
            if subtotal == 0 and cantidad > 0:
                detalle.subtotal = cantidad * precio_producto
                detalle.save()
                print(f"  - Subtotal corregido de {detalle.inventario.producto.nomProducto}: {detalle.subtotal}")
        
        if detalle.precio_unitario is None or detalle.precio_unitario == 0:
            detalle.precio_unitario = float(detalle.inventario.producto.precioVenta) if detalle.inventario.producto.precioVenta else 0.0
        
        print(f"Producto cargado: {detalle.inventario.producto.nomProducto}")
        print(f"  - Cantidad: {detalle.cantidad}")
        print(f"  - Subtotal: {detalle.subtotal}")
        print(f"  - Precio unitario: {detalle.precio_unitario}")
        print(f"  - Tipo precio: {type(detalle.precio_unitario)}")
        print("-" * 40)
    
    return render(request, 'ventas/editar_venta.html', {
        'venta': venta,
        'clientes': clientes,
        'metodos_pago': metodos_pago,
        'detalles': detalles,
        'productos_disponibles': productos_disponibles,
    })

#eliminar ventas
def eliminar_venta(request, id):
    # Verificar sesión - cualquier usuario logueado puede eliminar
    if request.session.get('usuario_id') is None:
        return redirect('login')
    
    # ❌ ELIMINA ESTAS LÍNEAS:
    # if request.session.get('rol') != "administrador":
    #     messages.error(request, '❌ Solo el administrador puede eliminar ventas')
    #     return redirect('ventas:ver_ventas')
    
    venta = get_object_or_404(Venta, id_venta=id)
    
    if request.method == "POST":
        try:
            # Devolver stock al producto
            detalles = DetalleVenta.objects.filter(venta=venta).select_related('inventario__producto')
            for detalle in detalles:
                producto = detalle.inventario.producto
                producto.stockActual += detalle.cantidad
                producto.save()
            
            # Eliminar detalles y venta
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
        
        if producto.stockActual < cantidad:
            messages.error(request, f'Stock insuficiente para {producto.nomProducto}')
            return redirect('dashboard_cajero')
        
        carrito = request.session.get('carrito', {'items': [], 'total': 0})
        
        encontrado = False
        for item in carrito['items']:
            if item.get('cod') == producto_id:
                nueva_cantidad = item['cantidad'] + cantidad
                if nueva_cantidad > producto.stockActual:
                    messages.error(request, f'Stock insuficiente para {producto.nomProducto}')
                    return redirect('dashboard_cajero')
                item['cantidad'] = nueva_cantidad
                item['subtotal'] = item['precio'] * item['cantidad']
                encontrado = True
                break
        
        if not encontrado:
            carrito['items'].append({
                'cod': producto.codProducto,  # ← Guardar cod
                'id': producto.id,
                'nombre': producto.nomProducto,
                'precio': float(producto.precioVenta),
                'cantidad': cantidad,
                'subtotal': float(producto.precioVenta) * cantidad
            })
        
        carrito['total'] = sum(item['subtotal'] for item in carrito['items'])
        carrito['subtotal'] = carrito['total']
        
        request.session['carrito'] = carrito
        messages.success(request, f' Agregado {producto.nomProducto} al carrito')
    
    return redirect('dashboard_cajero')
def eliminar_del_carrito(request, cod):
    if request.session.get('usuario_id') is None:
        return redirect('login')
    
    # Obtener carrito de sesión
    carrito = request.session.get('carrito', {'items': [], 'total': 0})
    
    # Filtrar el producto a eliminar por 'cod' (codProducto)
    carrito['items'] = [item for item in carrito['items'] if item.get('cod') != cod]
    
    # Recalcular total
    carrito['total'] = sum(item.get('subtotal', 0) for item in carrito['items'])
    carrito['subtotal'] = carrito['total']
    
    # Guardar carrito en sesión
    request.session['carrito'] = carrito
    
    messages.success(request, ' Producto eliminado del carrito')
    return redirect('dashboard_cajero')


def seleccionar_cliente(request):
    if request.method == 'POST':
        cliente_id = request.POST.get('cliente_id')
        
        # Si no hay cliente_id, mostrar error
        if not cliente_id:
            messages.error(request, ' Debes seleccionar un cliente para continuar')
            return redirect('dashboard_cajero')
        
    if request.session.get('usuario_id') is None:
        return redirect('login')
    
    # Manejar selección de cliente
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
    
    # GET - Mostrar clientes con búsqueda
    query = request.GET.get('q', '').strip()
    clientes = Cliente.objects.filter(estado=True).order_by('nombre')
    
    if query:
        # Buscar por carnet (exacto o parcial) o por nombre
        clientes = clientes.filter(
            models.Q(carnet__icontains=query) |  # Buscar por carnet
            models.Q(nombre__icontains=query)     # Buscar por nombre
        )
    
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
            # ============================================================
            # ✅ NUEVA VALIDACIÓN: Cantidades deben ser mayores a 0
            # ============================================================
            for item in carrito['items']:
                if item['cantidad'] <= 0:
                    messages.error(request, f'La cantidad debe ser mayor a 0')
                    return redirect('dashboard_cajero')
            
            # Verificar stock nuevamente
            for item in carrito['items']:
                producto = Producto.objects.get(id=item['id'])
                if producto.stockActual < item['cantidad']:
                    messages.error(request, f'Stock insuficiente para {producto.nomProducto}')
                    return redirect('dashboard_cajero')
            
            # Obtener o crear método de pago
            metodo, _ = MetodoPago.objects.get_or_create(tipoPago=metodo_pago)
            
            # Obtener cliente
            cliente = Cliente.objects.filter(id_cliente=cliente_id, estado=True).first()

            if not cliente:
                messages.error(request, 'Seleccione un cliente válido')
                return redirect('dashboard_cajero')
            
            # Crear venta
            venta = Venta.objects.create(
                total=carrito['total'],
                cliente=cliente,
                metodo_pago=metodo
            )
            
            # Crear detalles y descontar stock
            for item in carrito['items']:
                producto = Producto.objects.get(id=item['id'])
                producto.stockActual -= item['cantidad']
                producto.save()
                
                # Buscar o crear inventario
                inventario, _ = Inventario.objects.get_or_create(
                    producto=producto,
                    defaults={'stock_actual': producto.stockActual, 'tipoUnidad': 'unidad'}
                )
                inventario.stock_actual = producto.stockActual
                inventario.save()
                
                DetalleVenta.objects.create(
                    venta=venta,
                    inventario=inventario,
                    cantidad=item['cantidad'],
                    subtotal=item['subtotal']
                )
            
            # Limpiar carrito y cliente
            request.session['carrito'] = {'items': [], 'total': 0}
            request.session['cliente_venta'] = None
            
            messages.success(request, f'Venta #{venta.id_venta} registrada por Bs {venta.total:.2f}')
            
            # Redirigir al detalle de la venta recién creada
            return redirect('ventas:detalle_venta', id_venta=venta.id_venta)
            
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
            return redirect('dashboard_cajero')
    
    return redirect('dashboard_cajero')
#nuevas cosas
# ventas/views.py

# ventas/views.py - Agrega estas funciones al final del archivo

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from productos.models import Producto

# ========================
# AJAX - AGREGAR AL CARRITO
# ========================
@require_http_methods(["POST"])
def agregar_al_carrito_ajax(request):
    """Agrega un producto al carrito vía AJAX"""
    if request.session.get('usuario_id') is None:
        return JsonResponse({'success': False, 'error': 'Sesión no iniciada'}, status=401)
    
    producto_id = request.POST.get('producto_id')
    cantidad = int(request.POST.get('cantidad', 1))
    
    try:
        producto = Producto.objects.get(codProducto=producto_id, estado='activo')
        
        if producto.stockActual < cantidad:
            return JsonResponse({'success': False, 'error': f'Stock insuficiente para {producto.nomProducto}'})
        
        carrito = request.session.get('carrito', {'items': [], 'total': 0, 'subtotal': 0})
        
        encontrado = False
        for item in carrito['items']:
            if str(item.get('cod')) == str(producto_id):
                nueva_cantidad = item['cantidad'] + cantidad
                if nueva_cantidad > producto.stockActual:
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


# ========================
# AJAX - ACTUALIZAR CANTIDAD
# ========================
@require_http_methods(["POST"])
def actualizar_cantidad_carrito(request):
    """Actualiza la cantidad de un producto en el carrito vía AJAX"""
    if request.session.get('usuario_id') is None:
        return JsonResponse({'success': False, 'error': 'Sesión no iniciada'}, status=401)
    
    producto_cod = request.POST.get('producto_cod')
    nueva_cantidad = int(request.POST.get('cantidad', 1))
    
    if nueva_cantidad < 1:
        return JsonResponse({'success': False, 'error': 'La cantidad debe ser mayor a 0'})
    
    carrito = request.session.get('carrito', {'items': [], 'total': 0, 'subtotal': 0})
    
    item_encontrado = None
    for item in carrito['items']:
        if str(item.get('cod')) == str(producto_cod):
            # Verificar stock
            try:
                producto = Producto.objects.get(codProducto=producto_cod)
                if producto.stockActual < nueva_cantidad:
                    return JsonResponse({
                        'success': False, 
                        'error': f'Stock insuficiente. Solo hay {producto.stockActual} unidades disponibles'
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


# ========================
# AJAX - ELIMINAR DEL CARRITO
# ========================
@require_http_methods(["POST"])
def eliminar_del_carrito_ajax(request):
    """Elimina un producto del carrito vía AJAX"""
    if request.session.get('usuario_id') is None:
        return JsonResponse({'success': False, 'error': 'Sesión no iniciada'}, status=401)
    
    producto_cod = request.POST.get('producto_cod')
    
    carrito = request.session.get('carrito', {'items': [], 'total': 0, 'subtotal': 0})
    
    carrito['items'] = [item for item in carrito['items'] 
                        if str(item.get('cod')) != str(producto_cod)]
    
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
    """API para buscar productos (usado en editar venta)"""
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
                'stockActual': p.stockActual
            } for p in productos]
            return JsonResponse({'success': True, 'productos': data})
    return JsonResponse({'success': False, 'productos': []})

# =========================
# DETALLE DE VENTA
#==========================


# =============================================================================
# FUNCIONES DE IMPRESIÓN Y PDF PARA VENTAS INDIVIDUALES
# =============================================================================

from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from fpdf import FPDF
import io

from ventas.models import Venta, DetalleVenta


class PDFVentaIndividual(FPDF):
    """Clase PDF para factura de venta individual (formato formal)"""
    
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


def detalle_venta(request, id_venta):
    """Vista para mostrar el detalle de una venta (después de crearla)"""
    venta = get_object_or_404(
        Venta.objects.select_related('cliente', 'metodo_pago'), 
        id_venta=id_venta
    )
    detalles = DetalleVenta.objects.select_related(
        'inventario__producto'
    ).filter(venta=venta)
    
    context = {
        'venta': venta,
        'detalles': detalles,
        'fecha_actual': timezone.now().strftime('%Y-%m-%d')
    }
    return render(request, 'ventas/detalle_venta.html', context)


def imprimir_venta_html(request, id_venta):
    """Vista HTML para imprimir venta (formato formal)"""
    venta = get_object_or_404(
        Venta.objects.select_related('cliente', 'metodo_pago'), 
        id_venta=id_venta
    )
    detalles = DetalleVenta.objects.select_related(
        'inventario__producto'
    ).filter(venta=venta)
    
    context = {
        'venta': venta,
        'detalles': detalles,
        'cliente': venta.cliente,
        'fecha_impresion': timezone.now()
    }
    
    # Renderiza el template HTML formal (puedes copiar venta_print.html de reportes)
    html_string = render_to_string('ventas/venta_print.html', context)
    return HttpResponse(html_string)


def generar_pdf_venta(request, id_venta):
    """Generar PDF de venta individual para descargar"""
    venta = get_object_or_404(
        Venta.objects.select_related('cliente', 'metodo_pago'), 
        id_venta=id_venta
    )
    detalles = DetalleVenta.objects.select_related(
        'inventario__producto'
    ).filter(venta=venta)
    
    buffer = io.BytesIO()
    pdf = PDFVentaIndividual()
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
    
    # Tabla de productos
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
    
    # Total
    pdf.ln(5)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(145, 10, 'TOTAL:', 0, 0, 'R')
    pdf.set_text_color(37, 99, 235)
    pdf.cell(40, 10, f"Bs {float(venta.total):.2f}", 0, 1, 'R')
    pdf.set_text_color(0, 0, 0)
    
    # Firmas
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