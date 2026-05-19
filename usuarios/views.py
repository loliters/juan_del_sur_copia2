# usuarios/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.hashers import make_password, check_password
from django.contrib import messages
from django.db import IntegrityError
from django.http import JsonResponse
from .models import Usuario, Rol
import re

# Importar modelos de otras apps
from productos.models import Producto
from ventas.models import Venta, DetalleVenta
from metodopago.models import MetodoPago
from clientes.models import Cliente


# =========================
# LOGIN
# =========================
# =========================
# LOGIN (VERSIÓN CORRECTA)
# =========================
def login_view(request):
    if request.method == "POST":
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')

        if not email or not password:
            messages.error(request, ' Completa todos los campos')
            return redirect('login')

        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            messages.error(request, ' Correo electrónico inválido')
            return redirect('login')

        try:
            user = Usuario.objects.select_related('rol').get(email__iexact=email)
        except Usuario.DoesNotExist:
            messages.error(request, ' Usuario o contraseña incorrectos')
            return redirect('login')

        if not user.estado:
            messages.error(request, ' Usuario deshabilitado. Contacta al administrador')
            return redirect('login')

        if not check_password(password, user.password):
            messages.error(request, ' Usuario o contraseña incorrectos')
            return redirect('login')

        if not user.rol or not user.rol.nom_rol:
            messages.error(request, ' Usuario sin rol asignado. Contacta al administrador')
            return redirect('login')

        rol = user.rol.nom_rol.strip().lower()

        request.session['usuario_id'] = user.id
        request.session['rol'] = rol
        request.session['nombre'] = user.nom_usuario
        request.session['email'] = user.email

        # ✅ VERIFICAR SI ES PRIMERA VEZ
        if user.cambiar_password:
            messages.warning(request, '⚠️ Por seguridad, debes cambiar tu contraseña.')
            return redirect('perfil_admin')

        messages.success(request, f'¡Bienvenido {user.nom_usuario}!')

        if rol == "administrador":
            return redirect('dashboard_admin')
        elif rol == "cajero":
            return redirect('dashboard_cajero')
        else:
            messages.error(request, ' Rol no válido en el sistema')
            return redirect('login')

    return render(request, 'usuarios/login.html')


# =========================
# REGISTER
# =========================
def register(request):
    roles = Rol.objects.all()

    if request.method == "POST":
        nom_usuario = request.POST.get('nom_usuario', '').strip()
        ap1 = request.POST.get('ap1', '').strip()
        ap2 = request.POST.get('ap2', '').strip()
        password = request.POST.get('password', '')
        rol_id = request.POST.get('rol')
        estado = request.POST.get('estado') == 'on'

        if not nom_usuario and not ap1 and not ap2:
            messages.error(request, 'Debes ingresar al menos un nombre o apellido')
            return redirect('register')

        pattern_letters = r'^[A-Za-zÁÉÍÓÚáéíóúÑñ\s]+$'
        
        if nom_usuario and not re.match(pattern_letters, nom_usuario):
            messages.error(request, 'El nombre solo debe contener letras (sin números)')
            return redirect('register')
        
        if ap1 and not re.match(pattern_letters, ap1):
            messages.error(request, 'El primer apellido solo debe contener letras (sin números)')
            return redirect('register')
        
        if ap2 and not re.match(pattern_letters, ap2):
            messages.error(request, 'El segundo apellido solo debe contener letras (sin números)')
            return redirect('register')

        if not password or not rol_id:
            messages.error(request, 'Completa todos los campos obligatorios')
            return redirect('register')

        if not re.match(r'^(?=.*[A-Za-z])(?=.*\d)(?=.*[@$!%*#?&._-])[A-Za-z\d@$!%*#?&._-]{8,}$', password):
            messages.error(request, 'La contraseña debe tener mínimo 8 caracteres, letras, números y un símbolo')
            return redirect('register')

        try:
            rol_obj = Rol.objects.get(id=rol_id)
        except Rol.DoesNotExist:
            messages.error(request, 'Rol inválido')
            return redirect('register')

        # Generar email
        partes = []
        
        if nom_usuario:
            nombre_limpio = re.sub(r'\s+', ' ', nom_usuario).strip()
            primer_nombre = nombre_limpio.split()[0].lower()
            partes.append(primer_nombre)
        
        if ap1:
            apellido_limpio = re.sub(r'\s+', ' ', ap1).strip()
            primer_apellido = apellido_limpio.split()[0].lower()
            partes.append(primer_apellido)
        elif ap2:
            apellido_limpio = re.sub(r'\s+', ' ', ap2).strip()
            segundo_apellido = apellido_limpio.split()[0].lower()
            partes.append(segundo_apellido)
        
        base = '.'.join(partes) if partes else 'usuario'
        dominio = "juandelsur.com"
        
        email_final = f"{base}@{dominio}"
        contador = 1
        while Usuario.objects.filter(email=email_final).exists():
            contador += 1
            email_final = f"{base}{contador}@{dominio}"

        # Validaciones adicionales
        if nom_usuario and len(nom_usuario) > 100:
            messages.error(request, 'El nombre es demasiado largo (máximo 100 caracteres)')
            return redirect('register')
        
        if ap1 and len(ap1) > 100:
            messages.error(request, 'El primer apellido es demasiado largo (máximo 100 caracteres)')
            return redirect('register')
        
        if ap2 and len(ap2) > 100:
            messages.error(request, 'El segundo apellido es demasiado largo (máximo 100 caracteres)')
            return redirect('register')
        
        if len(password) > 128:
            messages.error(request, 'La contraseña es demasiado larga (máximo 128 caracteres)')
            return redirect('register')
        
        caracteres_especiales = r'[!@#$%^&*()_+=\[\]{};:""\\|,.<>/?]'
        if nom_usuario and re.search(caracteres_especiales, nom_usuario):
            messages.error(request, 'El nombre no debe contener caracteres especiales')
            return redirect('register')
        
        if ap1 and re.search(caracteres_especiales, ap1):
            messages.error(request, 'El primer apellido no debe contener caracteres especiales')
            return redirect('register')
        
        if ap2 and re.search(caracteres_especiales, ap2):
            messages.error(request, 'El segundo apellido no debe contener caracteres especiales')
            return redirect('register')
        
        if len(email_final) > 254:
            messages.error(request, 'El email generado es demasiado largo')
            return redirect('register')

        try:
            # ✅ CORREGIDO: Agregar cambiar_password=True
            Usuario.objects.create(
                nom_usuario=nom_usuario,
                ap1=ap1,
                ap2=ap2,
                email=email_final,
                password=make_password(password),
                rol=rol_obj,
                estado=estado,
                cambiar_password=True,  # ← ESTO ES LO QUE FALTABA
                fecha_creacion=timezone.now(),  # ← También falta la fecha
            )
        except IntegrityError as e:
            messages.error(request, f'Error al registrar usuario: {str(e)}')
            return redirect('register')

        messages.success(request, f'Usuario creado correctamente. Email: {email_final}')
        return redirect('login')

    return render(request, 'usuarios/register.html', {'roles': roles})


# =========================
# AJAX - GENERAR EMAIL PREVIEW
# =========================
def generar_email_preview(request):
    if request.method == "GET" and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        nom_usuario = request.GET.get('nom_usuario', '').strip()
        ap1 = request.GET.get('ap1', '').strip()
        ap2 = request.GET.get('ap2', '').strip()
        
        partes = []
        
        if nom_usuario:
            nombre_limpio = re.sub(r'\s+', ' ', nom_usuario).strip()
            primer_nombre = nombre_limpio.split()[0].lower()
            partes.append(primer_nombre)
        
        if ap1:
            apellido_limpio = re.sub(r'\s+', ' ', ap1).strip()
            primer_apellido = apellido_limpio.split()[0].lower()
            partes.append(primer_apellido)
        elif ap2:
            apellido_limpio = re.sub(r'\s+', ' ', ap2).strip()
            segundo_apellido = apellido_limpio.split()[0].lower()
            partes.append(segundo_apellido)
        
        base = '.'.join(partes) if partes else 'usuario'
        dominio = "juandelsur.com"
        
        email_generado = f"{base}@{dominio}"
        email_final = email_generado
        contador = 0
        while Usuario.objects.filter(email=email_final).exists():
            contador += 1
            email_final = f"{base}{contador}@{dominio}"
        
        return JsonResponse({'success': True, 'email': email_final, 'base_email': email_generado})
    
    return JsonResponse({'success': False, 'error': 'Solicitud inválida'})


# =========================
# DASHBOARD CAJERO (MODIFICADO)
# =========================
def dashboard_cajero(request):
    if request.session.get('usuario_id') is None:
        return redirect('login')
    
    query = request.GET.get('q', '')
    productos = Producto.objects.filter(estado='activo')
    if query:
        productos = productos.filter(nomProducto__icontains=query)
    
    # Asegurar que el carrito tenga el formato correcto con 'cod'
    carrito = request.session.get('carrito', {'items': [], 'total': 0, 'subtotal': 0})
    
    # Convertir items antiguos que puedan tener 'id' a tener 'cod'
    for item in carrito.get('items', []):
        if 'id' in item and 'cod' not in item:
            item['cod'] = item['id']
    
    cliente_id = request.session.get('cliente_venta')
    cliente = None
    if cliente_id:
        try:
            cliente = Cliente.objects.get(id_cliente=cliente_id)
        except Cliente.DoesNotExist:
            request.session['cliente_venta'] = None
    
    clientes_disponibles = Cliente.objects.filter(estado=True).order_by('nombre')
    
    return render(request, 'usuarios/dashboard_cajero.html', {
        'productos': productos,
        'query': query,
        'carrito': carrito,
        'cliente_venta': cliente,
        'clientes_disponibles': clientes_disponibles,
    })


# =========================
# AGREGAR AL CARRITO
# =========================
# usuarios/views.py - Modifica la función agregar_al_carrito
# (para mantener compatibilidad con el método POST tradicional)

def agregar_al_carrito(request):
    if request.session.get('usuario_id') is None:
        return redirect('login')
    
    if request.method == 'POST':
        producto_id = request.POST.get('producto_id')
        cantidad = int(request.POST.get('cantidad', 1))
        
        try:
            producto = Producto.objects.get(codProducto=producto_id, estado='activo')  # Usar codProducto
            
            if producto.stockActual < cantidad:
                messages.error(request, f'Stock insuficiente para {producto.nomProducto}')
                return redirect('dashboard_cajero')
            
            carrito = request.session.get('carrito', {'items': [], 'subtotal': 0, 'total': 0})
            
            encontrado = False
            for item in carrito['items']:
                if item.get('cod') == producto_id or item.get('id') == producto_id:
                    nueva_cantidad = item['cantidad'] + cantidad
                    if nueva_cantidad > producto.stockActual:
                        messages.error(request, f'No hay suficiente stock de {producto.nomProducto}')
                        return redirect('dashboard_cajero')
                    item['cantidad'] = nueva_cantidad
                    item['subtotal'] = item['cantidad'] * float(item['precio'])
                    encontrado = True
                    break
            
            if not encontrado:
                carrito['items'].append({
                    'cod': producto.codProducto,
                    'id': producto.id,
                    'nombre': producto.nomProducto,
                    'precio': float(producto.precioVenta),
                    'cantidad': cantidad,
                    'subtotal': cantidad * float(producto.precioVenta)
                })
            
            carrito['subtotal'] = sum(item['subtotal'] for item in carrito['items'])
            carrito['total'] = carrito['subtotal']
            
            request.session['carrito'] = carrito
            messages.success(request, f'Agregado {producto.nomProducto} al carrito')
            
        except Producto.DoesNotExist:
            messages.error(request, 'Producto no encontrado')
    
    return redirect('dashboard_cajero')


# =========================
# REGISTRO DE VENTA
# =========================
def registro_venta(request):
    if request.session.get('usuario_id') is None:
        return redirect('login')
    
    carrito = request.session.get('carrito', {'items': [], 'total': 0})
    
    if not carrito['items']:
        messages.error(request, ' El carrito está vacío')
        return redirect('dashboard_cajero')
    
    if request.method == 'POST':
        metodo_pago = request.POST.get('metodo_pago', 'QR')
        cliente_id = request.session.get('cliente_venta')
        
        try:
            # Verificar stock nuevamente
            for item in carrito['items']:
                producto = Producto.objects.get(id=item['id'])
                if producto.stockActual < item['cantidad']:
                    messages.error(request, f'Stock insuficiente para {producto.nomProducto}')
                    return redirect('dashboard_cajero')
            
            # Obtener o crear método de pago
            metodo, _ = MetodoPago.objects.get_or_create(tipoPago=metodo_pago)
            
            # Obtener cliente
            cliente = None
            if cliente_id:
                cliente = Cliente.objects.filter(id_cliente=cliente_id, estado=True).first()
            if not cliente:
                messages.error(request, '⚠️ Debes seleccionar un cliente antes de confirmar la venta')
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
                
                # Crear detalle - SIN precio_unitario
                DetalleVenta.objects.create(
                    venta=venta,
                    inventario=inventario,
                    cantidad=item['cantidad'],
                    subtotal=item['subtotal']  # subtotal = cantidad * precio
                )
            
            # Limpiar carrito y cliente
            request.session['carrito'] = {'items': [], 'total': 0}
            request.session['cliente_venta'] = None
            
            # Cambiar $ por Bs
            messages.success(request, f'Venta #{venta.id_venta} registrada exitosamente - Total: Bs {venta.total:.2f}')
            
        except Exception as e:
            messages.error(request, f' Error: {str(e)}')
        
        return redirect('dashboard_cajero')
    
    return redirect('dashboard_cajero')

# =========================
# DASHBOARD ADMIN
# =========================
def dashboard_admin(request):
    if request.session.get('usuario_id') is None:
        return redirect('login')
    
    usuario_id = request.session.get('usuario_id')
    usuario = Usuario.objects.get(id=usuario_id)
    usuarios = Usuario.objects.all().select_related('rol')
    
    # Verificar si es primera vez (campo `cambiar_password` en tu modelo)
    primera_vez = getattr(usuario, 'cambiar_password', False)
    
    return render(request, 'usuarios/dashboard_admin.html', {
        'usuarios': usuarios,
        'usuario': usuario,
        'primera_vez': primera_vez,
    })


# =========================
# MODIFICAR USUARIO
# =========================
def modify(request, id):
    usuario_sesion = request.session.get('usuario_id')
    rol_sesion = (request.session.get('rol') or '').strip().lower()

    if not usuario_sesion:
        return redirect('login')

    if rol_sesion != "administrador":
        return redirect('login')

    usuario = get_object_or_404(Usuario, id=id)
    roles = Rol.objects.all()

    if request.method == "POST":
        nom_usuario = request.POST.get('nom_usuario', '').strip()
        ap1 = request.POST.get('ap1', '').strip()
        ap2 = request.POST.get('ap2', '').strip()
        email = request.POST.get('email', '').strip()
        estado = request.POST.get('estado') == 'on'
        rol_id = request.POST.get('rol')

        if not nom_usuario and not ap1 and not ap2:
            messages.error(request, 'Debes ingresar al menos un nombre o apellido')
            return redirect('modify', id=id)

        pattern_letters = r'^[A-Za-zÁÉÍÓÚáéíóúÑñ\s]+$'
        
        if nom_usuario and not re.match(pattern_letters, nom_usuario):
            messages.error(request, 'El nombre solo debe contener letras (sin números)')
            return redirect('modify', id=id)
        
        if ap1 and not re.match(pattern_letters, ap1):
            messages.error(request, 'El primer apellido solo debe contener letras (sin números)')
            return redirect('modify', id=id)
        
        if ap2 and not re.match(pattern_letters, ap2):
            messages.error(request, 'El segundo apellido solo debe contener letras (sin números)')
            return redirect('modify', id=id)

        if not rol_id:
            messages.error(request, 'Debes seleccionar un rol')
            return redirect('modify', id=id)
            
        try:
            rol_obj = Rol.objects.get(id=rol_id)
        except Rol.DoesNotExist:
            messages.error(request, 'Rol inválido')
            return redirect('modify', id=id)

        caracteres_especiales = r'[!@#$%^&*()_+=\[\]{};:""\\|,.<>/?]'
        if nom_usuario and re.search(caracteres_especiales, nom_usuario):
            messages.error(request, 'El nombre no debe contener caracteres especiales')
            return redirect('modify', id=id)
        
        if ap1 and re.search(caracteres_especiales, ap1):
            messages.error(request, 'El primer apellido no debe contener caracteres especiales')
            return redirect('modify', id=id)
        
        if ap2 and re.search(caracteres_especiales, ap2):
            messages.error(request, 'El segundo apellido no debe contener caracteres especiales')
            return redirect('modify', id=id)

        if nom_usuario and len(nom_usuario) > 100:
            messages.error(request, 'El nombre es demasiado largo (máximo 100 caracteres)')
            return redirect('modify', id=id)
        
        if ap1 and len(ap1) > 100:
            messages.error(request, 'El primer apellido es demasiado largo (máximo 100 caracteres)')
            return redirect('modify', id=id)
        
        if ap2 and len(ap2) > 100:
            messages.error(request, 'El segundo apellido es demasiado largo (máximo 100 caracteres)')
            return redirect('modify', id=id)

        if email:
            email_existente = Usuario.objects.filter(email=email).exclude(id=usuario.id).exists()
            if email_existente:
                messages.error(request, f'El correo {email} ya está en uso por otro usuario')
                return redirect('modify', id=id)
            
            if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
                messages.error(request, 'Formato de correo electrónico inválido')
                return redirect('modify', id=id)
        
        if not email:
            partes = []
            
            if nom_usuario:
                nombre_limpio = re.sub(r'\s+', ' ', nom_usuario).strip()
                primer_nombre = nombre_limpio.split()[0].lower()
                partes.append(primer_nombre)
            
            if ap1:
                apellido_limpio = re.sub(r'\s+', ' ', ap1).strip()
                primer_apellido = apellido_limpio.split()[0].lower()
                partes.append(primer_apellido)
            elif ap2:
                apellido_limpio = re.sub(r'\s+', ' ', ap2).strip()
                segundo_apellido = apellido_limpio.split()[0].lower()
                partes.append(segundo_apellido)
            
            base = '.'.join(partes) if partes else 'usuario'
            dominio = "juandelsur.com"
            
            email_generado = f"{base}@{dominio}"
            email = email_generado
            contador = 1
            while Usuario.objects.filter(email=email).exclude(id=usuario.id).exists():
                contador += 1
                email = f"{base}{contador}@{dominio}"

        if len(email) > 254:
            messages.error(request, 'El email es demasiado largo')
            return redirect('modify', id=id)

        try:
            usuario.nom_usuario = nom_usuario
            usuario.ap1 = ap1
            usuario.ap2 = ap2
            usuario.email = email
            usuario.estado = estado
            usuario.rol = rol_obj
            usuario.save()
            
            messages.success(request, f'Usuario actualizado correctamente. Nuevo email: {email}')
        except IntegrityError as e:
            messages.error(request, f'Error al actualizar usuario: {str(e)}')
            return redirect('modify', id=id)
        
        return redirect('dashboard_admin')

    return render(request, 'usuarios/modify.html', {'usuario': usuario, 'roles': roles})


# =========================
# LOGOUT
# =========================
def logout_view(request):
    request.session.flush()
    return redirect('login')


# =========================
# ELIMINAR USUARIO (borrado lógico)
# =========================
def eliminar_usuario(request, id):
    if request.session.get('rol') != "administrador":
        return redirect('login')
    
    usuario = get_object_or_404(Usuario, id=id)
    usuario.estado = False
    usuario.save()
    
    messages.success(request, f' Usuario {usuario.nom_usuario} deshabilitado')
    return redirect('dashboard_admin')


# =========================
# VER INACTIVOS
# =========================
def ver_inactivos(request):
    if request.session.get('rol') != "administrador":
        return redirect('login')
    
    if request.method == "POST":
        usuario_id = request.POST.get("id")
        usuario = get_object_or_404(Usuario, id=usuario_id)
        usuario.estado = not usuario.estado
        usuario.save()
        return redirect('ver_inactivos')

    usuarios_inactivos = Usuario.objects.filter(estado=False)
    return render(request, "usuarios/ver_inactivos.html", {"usuarios_inactivos": usuarios_inactivos})

def recuperar_contraseña(request):
    from django.contrib.auth.hashers import make_password
    from .models import Usuario
    
    if request.method == 'POST':
        email = request.POST.get('email')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        # Validar que las contraseñas coincidan
        if new_password != confirm_password:
            messages.error(request, 'Las contraseñas no coinciden')
            return redirect('recuperar_contraseña')
        
        # Validar longitud mínima
        if len(new_password) < 4:
            messages.error(request, 'La contraseña debe tener al menos 4 caracteres')
            return redirect('recuperar_contraseña')
        
        # Buscar usuario por email
        try:
            usuario = Usuario.objects.get(email=email)
            
            # Actualizar contraseña
            usuario.password = make_password(new_password)
            usuario.save()
            
            messages.success(request, f'Contraseña actualizada correctamente para {usuario.nom_usuario}')
            return redirect('login')
            
        except Usuario.DoesNotExist:
            messages.error(request, 'No existe un usuario con ese correo electrónico')
            return redirect('recuperar_contraseña')
    
    return render(request, 'usuarios/recuperar_contraseña.html')

#PERFIL ADMIN
def perfil_admin(request):
    if request.session.get('usuario_id') is None:
        return redirect('login')
    
    usuario_id = request.session.get('usuario_id')
    usuario = Usuario.objects.get(id=usuario_id)
    
    if request.method == 'POST':
        nueva_password = request.POST.get('new_password')
        confirmar_password = request.POST.get('confirm_password')
        password_actual = request.POST.get('current_password')
        
        # Verificar contraseña actual
        if not check_password(password_actual, usuario.password):
            messages.error(request, '❌ Contraseña actual incorrecta')
            return redirect('perfil_admin')
        
        if nueva_password != confirmar_password:
            messages.error(request, '❌ Las nuevas contraseñas no coinciden')
            return redirect('perfil_admin')
        
        if len(nueva_password) < 4:
            messages.error(request, '❌ La contraseña debe tener al menos 4 caracteres')
            return redirect('perfil_admin')
        
        # Cambiar contraseña
        usuario.password = make_password(nueva_password)
        
        # ✅ IMPORTANTE: Marcar que YA NO es primera vez
        usuario.cambiar_password = False
        
        usuario.save()
        
        # Limpiar sesión
        messages.success(request, '✅ Contraseña cambiada exitosamente. Por favor, inicia sesión nuevamente.')
        request.session.flush()
        return redirect('login')
    
    # Verificar si es primera vez (para mostrar mensaje específico)
    es_primera_vez = usuario.cambiar_password
    
    return render(request, 'usuarios/perfil_admin.html', {
        'usuario': usuario,
        'es_primera_vez': es_primera_vez,
    })


#perfil cajeros
def perfil_cajero(request):
    if request.session.get('usuario_id') is None:
        return redirect('login')
    
    usuario_id = request.session.get('usuario_id')
    usuario = Usuario.objects.get(id=usuario_id)
    
    if request.method == 'POST':
        nueva_password = request.POST.get('new_password')
        confirmar_password = request.POST.get('confirm_password')
        password_actual = request.POST.get('current_password')
        
        # Verificar contraseña actual
        if not check_password(password_actual, usuario.password):
            messages.error(request, '❌ Contraseña actual incorrecta')
            return redirect('perfil_cajero')
        
        if nueva_password != confirmar_password:
            messages.error(request, '❌ Las nuevas contraseñas no coinciden')
            return redirect('perfil_cajero')
        
        if len(nueva_password) < 4:
            messages.error(request, '❌ La contraseña debe tener al menos 4 caracteres')
            return redirect('perfil_cajero')
        
        # Cambiar contraseña
        usuario.password = make_password(nueva_password)
        usuario.cambiar_password = False
        usuario.save()
        
        messages.success(request, '✅ Contraseña cambiada exitosamente. Por favor, inicia sesión nuevamente.')
        request.session.flush()
        return redirect('login')
    
    es_primera_vez = getattr(usuario, 'cambiar_password', False)
    
    return render(request, 'usuarios/perfil_cajero.html', {
        'usuario': usuario,
        'es_primera_vez': es_primera_vez,
    })