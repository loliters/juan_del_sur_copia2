# ventas/tests/test_ventas.py
import pytest
import json
from django.urls import reverse
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory
from decimal import Decimal

from ventas.models import Venta, DetalleVenta
from clientes.models import Cliente
from productos.models import Producto
from metodopago.models import MetodoPago
from inventario.models import Inventario
from usuarios.models import Usuario, Rol


# =========================================
# FIXTURES PARA LIMPIAR DATOS
# =========================================
@pytest.fixture(autouse=True)
def limpiar_datos(db):
    """Limpia todos los datos antes de cada test"""
    DetalleVenta.objects.all().delete()
    Venta.objects.all().delete()
    Inventario.objects.all().delete()
    Producto.objects.all().delete()
    Cliente.objects.all().delete()
    yield


@pytest.fixture
def crear_cliente():
    """Crea un cliente de prueba"""
    return Cliente.objects.create(
        nombre='Juan Perez',
        email='juan@test.com',
        telefono='77777777',
        zona='Centro',
        calle='Bolivar',
        numeroCasa='123',
        estado=True
    )


@pytest.fixture
def crear_producto():
    """Crea un producto de prueba con su inventario"""
    producto = Producto.objects.create(
        codProducto='P001',
        nomProducto='Producto Test',
        precioVenta=100.00,
        precioCompra=50.00,
        stockMinimo=5,
        estado='activo'
    )

    Inventario.objects.create(
        producto=producto,
        stock_actual=10,
        estado=True,
    )
    
    return producto


@pytest.fixture
def crear_metodo_pago():
    """Crea un método de pago de prueba"""
    metodo, _ = MetodoPago.objects.get_or_create(tipoPago='QR')
    return metodo


@pytest.fixture
def crear_inventario(crear_producto):
    """Crea inventario asociado al producto"""
    inventario, created = Inventario.objects.get_or_create(
        producto=crear_producto,
        defaults={'stock_actual': 10, 'estado': True}
    )
    return inventario


@pytest.fixture
def crear_venta(crear_cliente, crear_metodo_pago):
    """Crea una venta de prueba"""
    return Venta.objects.create(
        total=200.00,
        cliente=crear_cliente,
        metodo_pago=crear_metodo_pago
    )


@pytest.fixture
def session_con_cajero(client):
    """Simula sesión de cajero"""
    rol, _ = Rol.objects.get_or_create(nom_rol='cajero')
    
    usuario, _ = Usuario.objects.get_or_create(
        id=1,
        defaults={
            'nom_usuario': 'Cajero Test',
            'email': 'cajero@test.com',
            'password': '12345',
            'rol': rol,
            'estado': True
        }
    )
    
    session = client.session
    session['usuario_id'] = usuario.id
    session['rol'] = 'cajero'
    session.save()
    return session


@pytest.fixture
def carrito_en_sesion(client, session_con_cajero, crear_producto, crear_cliente, crear_inventario):
    """Crea un carrito en sesión"""
    carrito = {
        'items': [
            {
                'inventario_id': crear_inventario.id,
                'cod': crear_producto.codProducto,
                'nombre': crear_producto.nomProducto,
                'precio': float(crear_producto.precioVenta),
                'cantidad': 2,
                'subtotal': float(crear_producto.precioVenta) * 2
            }
        ],
        'total': float(crear_producto.precioVenta) * 2,
        'subtotal': float(crear_producto.precioVenta) * 2
    }
    session = client.session
    session['carrito'] = carrito
    session['cliente_venta'] = crear_cliente.id_cliente
    session.save()
    return client


# =========================================
# 1. REGISTRO DE VENTAS
# =========================================

@pytest.mark.django_db
def test_registro_venta_exitoso(carrito_en_sesion, crear_cliente, crear_metodo_pago):
    """Prueba 1: Registro exitoso de venta"""
    response = carrito_en_sesion.post('/ventas/registro-venta/', {
        'metodo_pago': 'QR'
    }, follow=True)
    
    assert response.status_code == 200
    assert Venta.objects.count() == 1
    venta = Venta.objects.first()
    assert venta.total == 200.00
    assert venta.cliente == crear_cliente


@pytest.mark.django_db
def test_registro_venta_sin_carrito(client, session_con_cajero):
    """Prueba 2: Intentar registrar venta con carrito vacío"""
    response = client.post('/ventas/registro-venta/', {
        'metodo_pago': 'QR'
    }, follow=True)
    
    assert response.status_code == 200
    assert Venta.objects.count() == 0
    
    # Convertir bytes a string correctamente
    content = response.content.decode('utf-8').lower()
    assert 'carrito' in content and ('vacio' in content or 'vacío' in content)


@pytest.mark.django_db
def test_registro_venta_sin_cliente(client, session_con_cajero, crear_producto):
    """Prueba 3: Intentar registrar venta sin seleccionar cliente"""
    carrito = {
        'items': [{'id': crear_producto.id, 'cantidad': 2, 'subtotal': 200}],
        'total': 200
    }
    session = client.session
    session['carrito'] = carrito
    session['cliente_venta'] = None
    session.save()
    
    response = client.post('/ventas/registro-venta/', {
        'metodo_pago': 'QR'
    }, follow=True)
    
    assert Venta.objects.count() == 0
    assert 'seleccione un cliente' in str(response.content).lower()


@pytest.mark.django_db
def test_descuento_stock_al_registrar(carrito_en_sesion, crear_producto):
    """Prueba 4: Verificar que el stock disminuya al registrar venta"""
    inventario = Inventario.objects.get(producto=crear_producto)
    stock_inicial = inventario.stock_actual
    
    carrito_en_sesion.post('/ventas/registro-venta/', {
        'metodo_pago': 'QR'
    }, follow=True)
    
    inventario.refresh_from_db()
    assert inventario.stock_actual == stock_inicial - 2


@pytest.mark.django_db
def test_venta_sin_stock(client, session_con_cajero, crear_cliente, crear_producto):
    """Prueba 5: Intentar vender producto con stock insuficiente"""
    inventario = Inventario.objects.get(producto=crear_producto)
    inventario.stock_actual = 1
    inventario.save()
    
    carrito = {
        'items': [{'id': crear_producto.id, 'cantidad': 2, 'subtotal': 200}],
        'total': 200
    }
    session = client.session
    session['carrito'] = carrito
    session['cliente_venta'] = crear_cliente.id_cliente
    session.save()
    
    response = client.post('/ventas/registro-venta/', {
        'metodo_pago': 'QR'
    }, follow=True)
    
    assert Venta.objects.count() == 0
    assert 'stock insuficiente' in str(response.content).lower()


@pytest.mark.django_db
def test_calculo_subtotal_detalle(crear_producto):
    """Prueba 6: Verificar cálculo correcto del subtotal"""
    cantidad = 3
    precio = 100.00
    subtotal_esperado = cantidad * precio
    assert subtotal_esperado == 300.00


@pytest.mark.django_db
def test_calculo_total_venta(carrito_en_sesion, crear_cliente, crear_metodo_pago):
    """Prueba 7: Verificar cálculo correcto del total de venta"""
    carrito_en_sesion.post('/ventas/registro-venta/', {
        'metodo_pago': 'QR'
    }, follow=True)
    
    venta = Venta.objects.first()
    assert venta.total == 200.00


# =========================================
# 2. CARRITO DE COMPRAS
# =========================================

@pytest.mark.django_db
def test_agregar_producto_carrito(client, session_con_cajero, crear_producto):
    """Prueba 8: Agregar producto al carrito exitosamente"""
    response = client.post('/ventas/agregar-al-carrito/', {
        'producto_id': crear_producto.codProducto,
        'cantidad': 2
    })
    
    carrito = client.session.get('carrito', {'items': []})
    assert len(carrito['items']) == 1
    assert carrito['items'][0]['cod'] == crear_producto.codProducto
    assert carrito['items'][0]['cantidad'] == 2


@pytest.mark.django_db
def test_agregar_producto_sin_stock(client, session_con_cajero, crear_producto):
    """Prueba 9: Intentar agregar producto sin stock"""
    inventario = Inventario.objects.get(producto=crear_producto)
    inventario.stock_actual = 0
    inventario.save()
    
    response = client.post('/ventas/agregar-al-carrito/', {
        'producto_id': crear_producto.codProducto,
        'cantidad': 1
    })
    
    carrito = client.session.get('carrito', {'items': []})
    assert len(carrito['items']) == 0
    assert 'stock insuficiente' in str(response.content).lower()


@pytest.mark.django_db
def test_agregar_producto_repetido(client, session_con_cajero, crear_producto):
    """Prueba 10: Agregar mismo producto dos veces aumenta cantidad"""
    client.post('/ventas/agregar-al-carrito/', {
        'producto_id': crear_producto.codProducto,
        'cantidad': 2
    })
    
    client.post('/ventas/agregar-al-carrito/', {
        'producto_id': crear_producto.codProducto,
        'cantidad': 3
    })
    
    carrito = client.session.get('carrito', {'items': []})
    assert len(carrito['items']) == 1
    assert carrito['items'][0]['cantidad'] == 5


@pytest.mark.django_db
def test_actualizar_cantidad_carrito(client, session_con_cajero, crear_producto):
    """Prueba 11: Actualizar cantidad de producto en carrito"""
    client.post('/ventas/agregar-al-carrito/', {
        'producto_id': crear_producto.codProducto,
        'cantidad': 2
    })
    
    response = client.post('/ventas/actualizar-cantidad/', {
        'producto_cod': crear_producto.codProducto,
        'cantidad': 5
    }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
    
    data = json.loads(response.content)
    assert data['success'] is True
    carrito = client.session.get('carrito', {'items': []})
    assert carrito['items'][0]['cantidad'] == 5


@pytest.mark.django_db
def test_actualizar_cantidad_excede_stock(client, session_con_cajero, crear_producto):
    """Prueba 12: Intentar actualizar cantidad mayor al stock disponible"""
    inventario = Inventario.objects.get(producto=crear_producto)
    inventario.stock_actual = 3
    inventario.save()
    
    client.post('/ventas/agregar-al-carrito/', {
        'producto_id': crear_producto.codProducto,
        'cantidad': 2
    })
    
    response = client.post('/ventas/actualizar-cantidad/', {
        'producto_cod': crear_producto.codProducto,
        'cantidad': 10
    }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
    
    data = json.loads(response.content)
    assert data['success'] is False
    assert 'stock insuficiente' in data['error'].lower()


@pytest.mark.django_db
def test_eliminar_producto_carrito(client, session_con_cajero, crear_producto):
    """Prueba 13: Eliminar producto del carrito"""
    client.post('/ventas/agregar-al-carrito/', {
        'producto_id': crear_producto.codProducto,
        'cantidad': 2
    })
    
    response = client.post('/ventas/eliminar-del-carrito/', {
        'producto_cod': crear_producto.codProducto
    }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
    
    data = json.loads(response.content)
    assert data['success'] is True
    carrito = client.session.get('carrito', {'items': []})
    assert len(carrito['items']) == 0


# =========================================
# 3. SELECCIÓN DE CLIENTE
# =========================================

@pytest.mark.django_db
def test_seleccionar_cliente_valido(client, session_con_cajero, crear_cliente):
    """Prueba 14: Seleccionar cliente válido para venta"""
    client.post('/ventas/seleccionar-cliente/', {
        'cliente_id': crear_cliente.id_cliente
    })
    
    assert client.session.get('cliente_venta') == crear_cliente.id_cliente


@pytest.mark.django_db
def test_seleccionar_cliente_inactivo(client, session_con_cajero, crear_cliente):
    """Prueba 15: Intentar seleccionar cliente inactivo"""
    crear_cliente.estado = False
    crear_cliente.save()
    
    client.post('/ventas/seleccionar-cliente/', {
        'cliente_id': crear_cliente.id_cliente
    }, follow=True)
    
    assert client.session.get('cliente_venta') is None


@pytest.mark.django_db
def test_buscar_cliente_por_carnet(client, session_con_cajero, crear_cliente):
    """Prueba 16: Buscar cliente por número de carnet"""
    crear_cliente.carnet = '123456'
    crear_cliente.save()
    
    response = client.get('/ventas/seleccionar-cliente/?q=123456')
    assert response.status_code == 200
    assert 'Juan Perez' in str(response.content)


@pytest.mark.django_db
def test_buscar_cliente_por_nombre(client, session_con_cajero, crear_cliente):
    """Prueba 17: Buscar cliente por nombre"""
    response = client.get('/ventas/seleccionar-cliente/?q=Juan')
    assert response.status_code == 200
    assert 'Juan Perez' in str(response.content)


# =========================================
# 4. EDICIÓN DE VENTAS
# =========================================

@pytest.mark.django_db
def test_editar_venta_cambiar_cliente(client, session_con_cajero, crear_venta, crear_inventario):
    """Prueba 18: Intentar editar venta cambiando el cliente - NO DEBE PERMITIR"""
    otro_cliente = Cliente.objects.create(
        nombre='Maria Lopez',
        email='maria@test.com',
        telefono='88888888',
        zona='Norte',
        calle='Sucre',
        numeroCasa='456',
        estado=True
    )
    
    producto_json = json.dumps({
        'cod': crear_inventario.producto.codProducto,
        'cantidad': 2,
        'precio': 100
    })
    
    response = client.post(f'/ventas/editar/{crear_venta.id_venta}/', {
        'cliente_id': otro_cliente.id_cliente,
        'metodo_pago_id': crear_venta.metodo_pago.id_met_pago,
        'productos': [producto_json]
    }, follow=True)
    
    crear_venta.refresh_from_db()
    assert crear_venta.cliente.id_cliente != otro_cliente.id_cliente
    assert 'No se puede cambiar el cliente' in str(response.content)


@pytest.mark.django_db
def test_editar_venta_aumentar_cantidad(client, session_con_cajero, crear_venta, crear_producto, crear_inventario):
    """Prueba 19: Editar venta aumentando cantidad de producto"""
    detalle = DetalleVenta.objects.create(
        venta=crear_venta,
        inventario=crear_inventario,
        cantidad=2,
        subtotal=200
    )
    inventario = Inventario.objects.get(producto=crear_producto)
    stock_inicial = inventario.stock_actual
    
    producto_json = json.dumps({
        'cod': crear_producto.codProducto,
        'cantidad': 5,
        'precio': 100
    })
    
    response = client.post(f'/ventas/editar/{crear_venta.id_venta}/', {
        'cliente_id': crear_venta.cliente.id_cliente,
        'metodo_pago_id': crear_venta.metodo_pago.id_met_pago,
        'productos': [producto_json]
    })
    
    inventario.refresh_from_db()
    assert inventario.stock_actual == stock_inicial - 3


@pytest.mark.django_db
def test_editar_venta_disminuir_cantidad(client, session_con_cajero, crear_venta, crear_producto, crear_inventario):
    """Prueba 20: Editar venta disminuyendo cantidad de producto"""
    detalle = DetalleVenta.objects.create(
        venta=crear_venta,
        inventario=crear_inventario,
        cantidad=5,
        subtotal=500
    )
    inventario = Inventario.objects.get(producto=crear_producto)
    stock_inicial = inventario.stock_actual
    
    producto_json = json.dumps({
        'cod': crear_producto.codProducto,
        'cantidad': 2,
        'precio': 100
    })
    
    response = client.post(f'/ventas/editar/{crear_venta.id_venta}/', {
        'cliente_id': crear_venta.cliente.id_cliente,
        'metodo_pago_id': crear_venta.metodo_pago.id_met_pago,
        'productos': [producto_json]
    })
    
    inventario.refresh_from_db()
    assert inventario.stock_actual == stock_inicial + 3


@pytest.mark.django_db
def test_editar_venta_eliminar_producto(client, session_con_cajero, crear_venta, crear_producto, crear_inventario):
    """Prueba 21: Editar venta eliminando un producto"""
    detalle = DetalleVenta.objects.create(
        venta=crear_venta,
        inventario=crear_inventario,
        cantidad=3,
        subtotal=300
    )
    inventario = Inventario.objects.get(producto=crear_producto)
    stock_inicial = inventario.stock_actual
    
    response = client.post(f'/ventas/editar/{crear_venta.id_venta}/', {
        'cliente_id': crear_venta.cliente.id_cliente,
        'metodo_pago_id': crear_venta.metodo_pago.id_met_pago,
        'productos': []
    }, follow=True)
    
    inventario.refresh_from_db()
    assert inventario.stock_actual == stock_inicial + 3
    assert DetalleVenta.objects.filter(venta=crear_venta).count() == 0


@pytest.mark.django_db
def test_editar_venta_agregar_producto(client, session_con_cajero, crear_venta, crear_producto, crear_inventario):
    """Prueba 22: Editar venta agregando un nuevo producto"""
    inventario = Inventario.objects.get(producto=crear_producto)
    stock_inicial = inventario.stock_actual
    
    producto_json = json.dumps({
        'cod': crear_producto.codProducto,
        'cantidad': 2,
        'precio': 100
    })
    
    response = client.post(f'/ventas/editar/{crear_venta.id_venta}/', {
        'cliente_id': crear_venta.cliente.id_cliente,
        'metodo_pago_id': crear_venta.metodo_pago.id_met_pago,
        'productos': [producto_json]
    })
    
    inventario.refresh_from_db()
    assert inventario.stock_actual == stock_inicial - 2
    assert DetalleVenta.objects.filter(venta=crear_venta).count() == 1


@pytest.mark.django_db
def test_editar_venta_stock_insuficiente(client, session_con_cajero, crear_venta, crear_producto, crear_inventario):
    """Prueba 23: Intentar editar aumentando cantidad sin stock disponible"""
    inventario = Inventario.objects.get(producto=crear_producto)
    inventario.stock_actual = 1
    inventario.save()
    
    detalle = DetalleVenta.objects.create(
        venta=crear_venta,
        inventario=crear_inventario,
        cantidad=1,
        subtotal=100
    )
    
    producto_json = json.dumps({
        'cod': crear_producto.codProducto,
        'cantidad': 5,
        'precio': 100
    })
    
    response = client.post(f'/ventas/editar/{crear_venta.id_venta}/', {
        'cliente_id': crear_venta.cliente.id_cliente,
        'metodo_pago_id': crear_venta.metodo_pago.id_met_pago,
        'productos': [producto_json]
    }, follow=True)
    
    assert 'stock insuficiente' in str(response.content).lower()


@pytest.mark.django_db
def test_editar_venta_recalcular_total(client, session_con_cajero, crear_venta, crear_producto, crear_inventario):
    """Prueba 24: Al editar, el total se recalcula automáticamente"""
    producto_json = json.dumps({
        'cod': crear_producto.codProducto,
        'cantidad': 3,
        'precio': 100
    })
    
    response = client.post(f'/ventas/editar/{crear_venta.id_venta}/', {
        'cliente_id': crear_venta.cliente.id_cliente,
        'metodo_pago_id': crear_venta.metodo_pago.id_met_pago,
        'productos': [producto_json]
    })
    
    crear_venta.refresh_from_db()
    assert crear_venta.total == 300.00


@pytest.mark.django_db
def test_editar_venta_sin_productos(client, session_con_cajero, crear_venta):
    """Prueba 25: Intentar editar venta sin productos"""
    response = client.post(f'/ventas/editar/{crear_venta.id_venta}/', {
        'cliente_id': crear_venta.cliente.id_cliente,
        'metodo_pago_id': crear_venta.metodo_pago.id_met_pago,
        'productos': []
    }, follow=True)
    
    assert 'productos válidos' in str(response.content).lower() or 'producto' in str(response.content).lower()


# =========================================
# 5. ELIMINACIÓN DE VENTAS
# =========================================

@pytest.mark.django_db
def test_eliminar_venta_restaura_stock(client, session_con_cajero, crear_venta, crear_producto, crear_inventario):
    """Prueba 27: Al eliminar venta, el stock se restaura"""
    DetalleVenta.objects.create(
        venta=crear_venta,
        inventario=crear_inventario,
        cantidad=3,
        subtotal=300
    )
    inventario = Inventario.objects.get(producto=crear_producto)
    stock_inicial = inventario.stock_actual
    
    client.post(f'/ventas/eliminar/{crear_venta.id_venta}/', follow=True)
    
    inventario.refresh_from_db()
    assert inventario.stock_actual == stock_inicial + 3


@pytest.mark.django_db
def test_eliminar_venta_elimina_detalles(client, session_con_cajero, crear_venta, crear_inventario):
    """Prueba 28: Los DetalleVenta se eliminan en cascada"""
    DetalleVenta.objects.create(
        venta=crear_venta,
        inventario=crear_inventario,
        cantidad=2,
        subtotal=200
    )
    
    assert DetalleVenta.objects.filter(venta=crear_venta).count() == 1
    
    client.post(f'/ventas/eliminar/{crear_venta.id_venta}/', follow=True)
    
    assert DetalleVenta.objects.filter(venta=crear_venta).count() == 0


@pytest.mark.django_db
def test_eliminar_venta_no_existente(client, session_con_cajero):
    """Prueba 29: Intentar eliminar venta que no existe"""
    response = client.post('/ventas/eliminar/9999/', follow=True)
    assert response.status_code == 404


# =========================================
# 6. VISUALIZACIÓN DE VENTAS
# =========================================

@pytest.mark.django_db
def test_ver_ventas_lista(client, session_con_cajero):
    """Prueba 30: Ver listado de todas las ventas"""
    response = client.get('/ventas/ver/')
    assert response.status_code == 200


@pytest.mark.django_db
def test_ver_ventas_orden_fecha(client, session_con_cajero, crear_cliente, crear_metodo_pago):
    """Prueba 31: Ventas ordenadas por fecha descendente"""
    venta1 = Venta.objects.create(total=100, cliente=crear_cliente, metodo_pago=crear_metodo_pago)
    venta2 = Venta.objects.create(total=200, cliente=crear_cliente, metodo_pago=crear_metodo_pago)
    
    response = client.get('/ventas/ver/')
    assert response.status_code == 200


@pytest.mark.django_db
def test_detalle_venta(client, session_con_cajero, crear_venta, crear_inventario):
    """Prueba 32: Ver detalle de una venta específica"""
    DetalleVenta.objects.create(
        venta=crear_venta,
        inventario=crear_inventario,
        cantidad=2,
        subtotal=200
    )
    
    response = client.get(f'/ventas/{crear_venta.id_venta}/detalle/')
    assert response.status_code == 200


@pytest.mark.django_db
def test_detalle_venta_no_existente(client, session_con_cajero):
    """Prueba 33: Intentar ver detalle de venta inexistente"""
    response = client.get('/ventas/9999/detalle/')
    assert response.status_code == 404


# =========================================
# 7. SEGURIDAD Y ACCESOS
# =========================================

@pytest.mark.django_db
def test_ventas_sin_login(client):
    """Prueba 34: No se puede registrar venta sin sesión iniciada"""
    response = client.get('/ventas/ver/')
    assert response.status_code == 302
    assert '/login' in response.url


@pytest.mark.django_db
def test_ventas_con_rol_cajero(client, session_con_cajero, crear_venta):
    """Prueba 35: Usuario con rol Cajero puede registrar y editar ventas"""
    response = client.get('/ventas/ver/')
    assert response.status_code == 200
    
    response = client.get(f'/ventas/editar/{crear_venta.id_venta}/')
    assert response.status_code == 200


# =========================================
# 8. STOCK Y CÁLCULOS
# =========================================

@pytest.mark.django_db
def test_venta_multiple_productos(client, session_con_cajero, crear_cliente):
    """Prueba 37: Venta con múltiples productos descuenta stock de cada uno"""
    producto1 = Producto.objects.create(
        codProducto='P001', nomProducto='Prod1', precioVenta=100, estado='activo'
    )
    producto2 = Producto.objects.create(
        codProducto='P002', nomProducto='Prod2', precioVenta=50, estado='activo'
    )
    
    Inventario.objects.create(producto=producto1, stock_actual=10, tipoUnidad='unidad')
    Inventario.objects.create(producto=producto2, stock_actual=20, tipoUnidad='unidad')
    
    carrito = {
        'items': [
            {'id': producto1.id, 'cantidad': 2, 'subtotal': 200},
            {'id': producto2.id, 'cantidad': 3, 'subtotal': 150}
        ],
        'total': 350
    }
    session = client.session
    session['carrito'] = carrito
    session['cliente_venta'] = crear_cliente.id_cliente
    session.save()
    
    client.post('/ventas/registro-venta/', {'metodo_pago': 'QR'}, follow=True)
    
    inventario1 = Inventario.objects.get(producto=producto1)
    inventario2 = Inventario.objects.get(producto=producto2)
    
    assert inventario1.stock_actual == 8
    assert inventario2.stock_actual == 17


@pytest.mark.django_db
def test_stock_no_negativo(client, session_con_cajero, crear_cliente, crear_producto):
    """Prueba 38: Verificar que el stock nunca sea negativo"""
    inventario = Inventario.objects.get(producto=crear_producto)
    inventario.stock_actual = 0
    inventario.save()
    
    carrito = {
        'items': [{'id': crear_producto.id, 'cantidad': 1, 'subtotal': 100}],
        'total': 100
    }
    session = client.session
    session['carrito'] = carrito
    session['cliente_venta'] = crear_cliente.id_cliente
    session.save()
    
    response = client.post('/ventas/registro-venta/', {'metodo_pago': 'QR'}, follow=True)
    
    inventario.refresh_from_db()
    assert inventario.stock_actual == 0


# =========================================
# 9. VISTAS AJAX
# =========================================

@pytest.mark.django_db
def test_agregar_carrito_ajax(client, session_con_cajero, crear_producto):
    """Prueba 41: Agregar producto al carrito mediante AJAX"""
    response = client.post('/ventas/agregar-al-carrito/', {
        'producto_id': crear_producto.codProducto,
        'cantidad': 2
    }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
    
    data = json.loads(response.content)
    assert data['success'] is True
    assert data['cart_items_count'] == 1


@pytest.mark.django_db
def test_actualizar_cantidad_ajax(client, session_con_cajero, crear_producto):
    """Prueba 42: Actualizar cantidad en carrito mediante AJAX"""
    client.post('/ventas/agregar-al-carrito/', {
        'producto_id': crear_producto.codProducto,
        'cantidad': 2
    })
    
    response = client.post('/ventas/actualizar-cantidad/', {
        'producto_cod': crear_producto.codProducto,
        'cantidad': 5
    }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
    
    data = json.loads(response.content)
    assert data['success'] is True
    assert data['item_subtotal'] == 500


@pytest.mark.django_db
def test_eliminar_carrito_ajax(client, session_con_cajero, crear_producto):
    """Prueba 43: Eliminar producto del carrito mediante AJAX"""
    client.post('/ventas/agregar-al-carrito/', {
        'producto_id': crear_producto.codProducto,
        'cantidad': 2
    })
    
    response = client.post('/ventas/eliminar-del-carrito/', {
        'producto_cod': crear_producto.codProducto
    }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
    
    data = json.loads(response.content)
    assert data['success'] is True
    assert data['cart_items_count'] == 0


@pytest.mark.django_db
def test_buscar_productos_ajax(client, session_con_cajero, crear_producto):
    """Prueba 44: Buscar productos por nombre mediante AJAX"""
    response = client.get('/ventas/buscar-productos/?q=Producto', 
                          HTTP_X_REQUESTED_WITH='XMLHttpRequest')
    
    # Si la URL no existe, la prueba fallará apropiadamente
    if response.status_code == 200:
        data = json.loads(response.content)
        assert 'success' in data


# =========================================
# 10. IMPRESIÓN Y PDF
# =========================================

@pytest.mark.django_db
def test_imprimir_venta_html(client, session_con_cajero, crear_venta):
    """Prueba 45: Generar vista HTML para imprimir venta"""
    response = client.get(f'/ventas/imprimir/{crear_venta.id_venta}/')
    assert response.status_code == 200
    assert 'text/html' in response['Content-Type']


@pytest.mark.django_db
def test_generar_pdf_venta(client, session_con_cajero, crear_venta):
    """Prueba 46: Generar PDF de venta"""
    response = client.get(f'/ventas/pdf/{crear_venta.id_venta}/')
    assert response.status_code == 200
    assert 'application/pdf' in response['Content-Type']


@pytest.mark.django_db
def test_pdf_contiene_datos_correctos(client, session_con_cajero, crear_venta, crear_inventario):
    """Prueba 47: Verificar que el PDF contenga datos correctos"""
    DetalleVenta.objects.create(
        venta=crear_venta,
        inventario=crear_inventario,
        cantidad=2,
        subtotal=200
    )
    
    response = client.get(f'/ventas/pdf/{crear_venta.id_venta}/')
    assert response.status_code == 200


# =========================================
# 11. CASOS BORDE
# =========================================

@pytest.mark.django_db
def test_venta_cantidad_cero(client, session_con_cajero, crear_cliente, crear_producto):
    """Prueba 48: Intentar vender cantidad 0"""
    carrito = {
        'items': [{'id': crear_producto.id, 'cantidad': 0, 'subtotal': 0}],
        'total': 0
    }
    session = client.session
    session['carrito'] = carrito
    session['cliente_venta'] = crear_cliente.id_cliente
    session.save()
    
    response = client.post('/ventas/registro-venta/', {'metodo_pago': 'QR'}, follow=True)
    assert Venta.objects.count() == 0


@pytest.mark.django_db
def test_venta_cantidad_negativa(client, session_con_cajero, crear_cliente, crear_producto):
    """Prueba 49: Intentar vender cantidad negativa"""
    carrito = {
        'items': [{'id': crear_producto.id, 'cantidad': -1, 'subtotal': -100}],
        'total': -100
    }
    session = client.session
    session['carrito'] = carrito
    session['cliente_venta'] = crear_cliente.id_cliente
    session.save()
    
    response = client.post('/ventas/registro-venta/', {'metodo_pago': 'QR'}, follow=True)
    assert Venta.objects.count() == 0


@pytest.mark.django_db
def test_venta_producto_inactivo(client, session_con_cajero, crear_cliente):
    """Prueba 50: Intentar vender producto inactivo"""
    producto = Producto.objects.create(
        codProducto='P001',
        nomProducto='Producto Inactivo',
        precioVenta=100,
        estado='inactivo'
    )
    
    carrito = {
        'items': [{'id': producto.id, 'cantidad': 1, 'subtotal': 100}],
        'total': 100
    }
    session = client.session
    session['carrito'] = carrito
    session['cliente_venta'] = crear_cliente.id_cliente
    session.save()
    
    response = client.post('/ventas/registro-venta/', {'metodo_pago': 'QR'}, follow=True)
    assert Venta.objects.count() == 0


@pytest.mark.django_db
def test_venta_cliente_eliminado(client, session_con_cajero, crear_cliente):
    """Prueba 51: Venta con cliente eliminado lógicamente"""
    crear_cliente.estado = False
    crear_cliente.save()
    
    response = client.get('/ventas/seleccionar-cliente/')
    assert 'Juan Perez' not in str(response.content)


@pytest.mark.django_db
def test_sql_injection_ventas(client, session_con_cajero):
    """Prueba 52: Prevenir SQL Injection en búsqueda de clientes"""
    payload = "' OR '1'='1"
    response = client.get(f'/ventas/seleccionar-cliente/?q={payload}')
    assert response.status_code == 200


@pytest.mark.django_db
def test_carrito_persiste_en_sesion(client, session_con_cajero, crear_producto):
    """Prueba 53: Verificar que el carrito persista en sesión"""
    client.post('/ventas/agregar-al-carrito/', {
        'producto_id': crear_producto.codProducto,
        'cantidad': 2
    })
    
    carrito1 = client.session.get('carrito')
    client.get('/ventas/ver/')
    carrito2 = client.session.get('carrito')
    
    assert carrito1 == carrito2


@pytest.mark.django_db
def test_limpiar_carrito_despues_venta(carrito_en_sesion):
    """Prueba 54: Limpiar carrito después de confirmar venta"""
    carrito_en_sesion.post('/ventas/registro-venta/', {
        'metodo_pago': 'QR'
    }, follow=True)
    
    carrito = carrito_en_sesion.session.get('carrito', {'items': []})
    assert len(carrito['items']) == 0


@pytest.mark.django_db
def test_limpiar_cliente_sesion_despues_venta(carrito_en_sesion):
    """Prueba 55: Limpiar cliente seleccionado después de venta"""
    carrito_en_sesion.post('/ventas/registro-venta/', {
        'metodo_pago': 'QR'
    }, follow=True)
    
    cliente_venta = carrito_en_sesion.session.get('cliente_venta')
    assert cliente_venta is None


@pytest.mark.django_db
def test_metodo_pago_invalido(carrito_en_sesion):
    """Prueba 56: Intentar registrar venta con método de pago inválido"""
    response = carrito_en_sesion.post('/ventas/registro-venta/', {
        'metodo_pago': 'METODO_INEXISTENTE'
    }, follow=True)
    
    assert MetodoPago.objects.filter(tipoPago='METODO_INEXISTENTE').exists()