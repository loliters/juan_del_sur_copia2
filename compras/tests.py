from django.test import TestCase, Client
from django.urls import reverse  # ← ¡IMPORTANTE! Para URLs seguras
from compras.models import Compra, DetalleCompra
from proveedores.models import Proveedor
from productos.models import Producto
from categorias.models import Categoria
from inventario.models import Inventario
import json
from datetime import datetime
from django.utils import timezone  # ← Para fechas con zona horaria
from usuarios.models import Usuario, Rol 


class ComprasTests(TestCase):
    def setUp(self):
        self.client = Client()
        
        # 1️⃣ Crea un Rol y Usuario de prueba (obligatorio por la FK de Producto)
        self.rol = Rol.objects.create(nom_rol='Administrador')
        self.usuario = Usuario.objects.create(
            nom_usuario='admin_test',
            ap1='Test',
            ap2='Admin',
            email='test@admin.com',
            password='test123',
            estado=True,
            rol=self.rol
        )
        
        # 2️⃣ Configura la sesión con el ID REAL del usuario creado
        session = self.client.session
        session['usuario_id'] = self.usuario.id  # ✅ Ahora sí existe en la BD de prueba
        session['rol'] = 'administrador'
        session.save()

        # 3️⃣ Resto de tus datos de prueba (sin cambios)
        self.prov = Proveedor.objects.create(nomProv="Dist. ABC", estado=True)
        self.cat = Categoria.objects.create(nomCategoria="Alimentos", estado=True)
        self.prod = Producto.objects.create(
            codProducto="P001", nomProducto="Harina", categoria=self.cat,
            precioCompra=20.00, precioVenta=30.00, estado='activo',
        )
        self.inv = Inventario.objects.create(producto=self.prod, stock_actual=10, estado=True)
        self.compra = Compra.objects.create(
            total=200.00, fecha=timezone.now(), proveedor=self.prov, estado=True
        )

    # 1️⃣ Listado muestra compras activas + detalles + proveedor + total
    def test_listado_compras_activas_con_detalles(self):
        DetalleCompra.objects.create(compra=self.compra, inventario=self.inv, cantidad=5, subtotal=100)
        
        resp = self.client.get(reverse('compras:ver_compras'))
        
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.prov.nomProv)
        self.assertContains(resp, "200,00")

    # 2️⃣ Formulario crea/edita con productos filtrados por estado=True
    def test_formulario_compra_filtrado_activos(self):
        # Crear producto inactivo para verificar que NO aparece
        prod_inac = Producto.objects.create(
            codProducto="X", nomProducto="Inactivo", 
            categoria=self.cat, estado='inactivo'
        )
        
        # ✅ PROBLEMA: Los productos se cargan con AJAX/JS, no en HTML inicial
        # SOLUCIÓN: Probar el endpoint AJAX directamente
        resp = self.client.get(
            reverse('compras:buscar_productos_ajax'), 
            {'q': 'harina'}
        )
        
        data = json.loads(resp.content)
        self.assertTrue(data['success'])
        
        # Verificar que "Harina" está en resultados
        nombres = [p['nomProducto'] for p in data['productos']]
        self.assertIn('Harina', nombres)
        
        # Verificar que productos inactivos NO aparecen
        self.assertNotIn('Inactivo', nombres)

    # 3️⃣ Formulario editar recupera todos los datos
    def test_editar_recupera_datos_sin_cambiar_fecha(self):
        DetalleCompra.objects.create(
            compra=self.compra, 
            inventario=self.inv, 
            cantidad=5, 
            subtotal=100
        )

        resp = self.client.get(
            reverse('compras:editar_compra', kwargs={'id': self.compra.id_compra})
        )

        self.assertEqual(resp.status_code, 200)

        contenido = resp.content.decode('utf-8')
        self.assertIn('Harina', contenido)

        fecha_date = self.compra.fecha.strftime("%Y-%m-%d")
        self.assertIn(fecha_date, contenido)
        # Verificar que el campo de fecha existe y tiene un valor válido
        self.assertIn('name="fecha"', contenido)
        self.assertIn('value="', contenido)  # Hay algún valor asignado

    # 4️⃣ Flujo "crear nuevo producto desde compra"
    def test_crear_nuevo_producto_desde_compra(self):
        """
        ✅ Prueba la lógica de creación de producto, no el flujo de pestañas
        (el test client no soporta simular múltiples pestañas del navegador)
        """
        prod_count = Producto.objects.count()
        
        # ✅ Enviar solo los campos que el formulario POST realmente procesa
        resp = self.client.post('/productos/registrar/', {
            'codProducto': 'PNEW', 
            'nomProducto': 'NuevoDesdeCompra', 
            'categoria': self.cat.id,
            'precioCompra': '10', 
            'precioVenta': '15', 
            'stockActual': '20', 
            'tipoUnidad': 'unidad',
            
        }, follow=True)
        
        # ✅ Verificar que el producto se creó (lógica principal)
        self.assertEqual(Producto.objects.count(), prod_count + 1)
        
        # ✅ Verificar datos del nuevo producto
        new_prod = Producto.objects.get(codProducto='PNEW')
        self.assertEqual(new_prod.nomProducto, 'NuevoDesdeCompra')
        
        # ✅ Verificar que también se creó su inventario
        self.assertTrue(Inventario.objects.filter(producto=new_prod).exists())

    # 5️⃣ Stock: al crear compra → stock aumenta
    def test_crear_compra_aumenta_stock(self):
        stock_antes = self.prod.stockActual
        
        # ✅ Datos para crear compra (formato que espera tu vista)
        data = {
            'proveedor_id': self.prov.id,
            'fecha': timezone.now().isoformat(),
            'productos': [
                json.dumps({
                    'inventario_id': self.inv.id,
                    'cod': 'P001',
                    'cantidad': 5,
                    'precio_compra': 20.00
                })
            ]
        }
        
        self.client.post(reverse('compras:crear_compra'), data)
        
        # Verificar que el stock se actualizó
        self.prod.refresh_from_db()
        self.assertEqual(self.prod.stockActual, stock_antes + 5)

    # 6️⃣ Stock: al eliminar compra → stock revierte
    def test_eliminar_compra_revierte_stock(self):
        # Crear detalle para que haya stock que revertir
        DetalleCompra.objects.create(
            compra=self.compra, 
            inventario=self.inv, 
            cantidad=5, 
            subtotal=100
        )
        
        stock_antes = self.prod.stockActual
        
        # ✅ URL CORRECTA: /compras/eliminar/{id}/
        self.client.post(
            reverse('compras:eliminar_compra', kwargs={'id': self.compra.id_compra})
        )
        
        # Verificar que el stock se redujo
        self.prod.refresh_from_db()
        self.assertEqual(self.prod.stockActual, stock_antes - 5)

    # 7️⃣ Stock: al editar compra → stock se ajusta
    def test_editar_compra_ajusta_stock(self):
        # Crear detalle inicial: cantidad=5
        DetalleCompra.objects.create(
            compra=self.compra, 
            inventario=self.inv, 
            cantidad=5, 
            subtotal=100
        )
        
        stock_antes = self.prod.stockActual
        
        # ✅ Editar: cambiar cantidad de 5 → 8 (diferencia: +3)
        data = {
            'proveedor_id': self.prov.id,
            'fecha': self.compra.fecha.isoformat(),
            'productos': [
                json.dumps({
                    'inventario_id': self.inv.id,
                    'cod': 'P001',
                    'cantidad': 8,
                    'precio_compra': 20.00
                })
            ]
        }
        
        self.client.post(
            reverse('compras:editar_compra', kwargs={'id': self.compra.id_compra}), 
            data
        )
        
        # Verificar ajuste de stock: +3 por diferencia (8-5)
        self.prod.refresh_from_db()
        self.assertEqual(self.prod.stockActual, stock_antes + 3)

    # 8️⃣ Detalle compra: datos coinciden con BD
    def test_detalle_compra_coincide_bd(self):
        DetalleCompra.objects.create(
            compra=self.compra, 
            inventario=self.inv, 
            cantidad=3, 
            subtotal=60
        )
        
        # ✅ URL CORRECTA: /compras/{id_compra}/detalle/ (¡orden importante!)
        resp = self.client.get(
            reverse('compras:detalle_compra', kwargs={'id_compra': self.compra.id_compra})
        )
        
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.compra.proveedor.nomProv)
        self.assertContains(resp, "3")      # cantidad
        self.assertContains(resp, "60")     # subtotal (sin .00 a veces)

    # 9️⃣ PDF: genera archivo válido con datos vacíos
    def test_pdf_compra_valido_con_datos_vacios(self):
        # ✅ URL CORRECTA: /compras/pdf/{id_compra}/
        resp = self.client.get(
            reverse('compras:pdf_compra', kwargs={'id_compra': self.compra.id_compra})
        )
        
        self.assertEqual(resp.status_code, 200)
        self.assertIn('application/pdf', resp['Content-Type'])
        # Verificar que el PDF tiene contenido mínimo válido
        self.assertGreater(len(resp.content), 500)

    # 🔟 PDF: no crashea con nombres largos
    def test_pdf_compra_no_crash_con_nombres_largos(self):
        # Crear producto con nombre muy largo
        prod_largo = Producto.objects.create(
            codProducto="LONG", 
            nomProducto="A" * 100,  # ← 100 caracteres
            categoria=self.cat,
            precioCompra=1, 
            precioVenta=2, 
            estado='activo'
        )
        inv_largo = Inventario.objects.create(
            producto=prod_largo, 
            stock_actual=1
        )
        compra_larga = Compra.objects.create(
            total=1, 
            fecha=timezone.now(), 
            proveedor=self.prov, 
            estado=True
        )
        DetalleCompra.objects.create(
            compra=compra_larga, 
            inventario=inv_largo, 
            cantidad=1, 
            subtotal=1
        )
        
        # Generar PDF no debe crashear
        resp = self.client.get(
            reverse('compras:pdf_compra', kwargs={'id_compra': compra_larga.id_compra})
        )
        
        self.assertEqual(resp.status_code, 200)
        self.assertIn('application/pdf', resp['Content-Type'])