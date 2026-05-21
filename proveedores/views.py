from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Proveedor


# LISTAR (AGREGADO: envía el rol al template)
def lista_proveedores(request):
    # Verificar sesión
    if request.session.get('usuario_id') is None:
        return redirect('login')
    
    proveedores = Proveedor.objects.filter(estado=True)
    
    # Enviar rol al template para controlar botones
    es_cajero = request.session.get('rol') == 'cajero'
    es_admin = request.session.get('rol') == 'administrador'
    
    return render(request, 'proveedores/lista.html', {
        'proveedores': proveedores,
        'es_cajero': es_cajero,
        'es_admin': es_admin,
    })


# CREAR (AGREGADO: solo administrador puede crear)
def crear_proveedor(request):
    # Verificar sesión
    if request.session.get('usuario_id') is None:
        return redirect('login')
    
    # Solo administrador puede crear
    if request.session.get('rol') != 'administrador':
        messages.error(request, ' Acceso denegado. Solo el administrador puede crear proveedores.')
        return redirect('proveedores:lista')
    
    if request.method == 'POST':
        nombre = request.POST.get('nomProv')
        direccion = request.POST.get('direccion')
        if nombre:
            nombre = nombre.strip()
        if direccion:
            direccion = direccion.strip()
        
        email = request.POST.get('email')
        telefono = request.POST.get('telefono')

        if not nombre or not direccion:
            messages.error(request, 'Nombre y dirección son obligatorios')
            return redirect('proveedores:crear')

        # VALIDAR DIRECCIÓN DUPLICADA
        if Proveedor.objects.filter(direccion__iexact=direccion).exists():
            messages.error(request, 'Ya existe un proveedor con esa dirección')
            return redirect('proveedores:crear')

        # VALIDAR MISMO NOMBRE PERO OTRA DIRECCIÓN
        if Proveedor.objects.filter(nomProv__iexact=nombre).exists():
            messages.warning(request, 'Ya existe un proveedor con ese nombre, verifica si es el mismo con otra dirección')

        Proveedor.objects.create(
            nomProv=nombre,
            direccion=direccion,
            email=email,
            telefono=telefono,
            estado=True
        )

        messages.success(request, 'Proveedor creado correctamente')
        return redirect('proveedores:lista')

    return render(request, 'proveedores/crear.html')


# EDITAR (AGREGADO: solo administrador puede editar)
def editar_proveedor(request, id_proveedor):
    # Verificar sesión
    if request.session.get('usuario_id') is None:
        return redirect('login')
    
    # Solo administrador puede editar
    if request.session.get('rol') != 'administrador':
        messages.error(request, ' Acceso denegado. Solo el administrador puede editar proveedores.')
        return redirect('proveedores:lista')
    
    proveedor = get_object_or_404(Proveedor, id=id_proveedor)

    if request.method == 'POST':
        nombre = request.POST.get('nomProv')
        if nombre:
                nombre = nombre.strip()

        if not nombre:
            messages.error(request, 'El nombre es obligatorio')
            return redirect('proveedores:editar', id_proveedor=id_proveedor)

        if Proveedor.objects.filter(nomProv__iexact=nombre).exclude(id=proveedor.id).exists():
            messages.error(request, 'Ya existe ese proveedor')
            return redirect('proveedores:editar', id_proveedor=id_proveedor)

        proveedor.nomProv = nombre
        proveedor.email = request.POST.get('email')
        proveedor.telefono = request.POST.get('telefono')
        proveedor.direccion = request.POST.get('direccion')
        proveedor.save()

        messages.success(request, 'Proveedor actualizado')
        return redirect('proveedores:lista')

    return render(request, 'proveedores/editar.html', {'proveedor': proveedor})


# ELIMINAR (SOFT) - AGREGADO: solo administrador puede eliminar
def eliminar_proveedor(request, id_proveedor):
    # Verificar sesión
    if request.session.get('usuario_id') is None:
        return redirect('login')
    
    # Solo administrador puede eliminar
    if request.session.get('rol') != 'administrador':
        messages.error(request, ' Acceso denegado. Solo el administrador puede eliminar proveedores.')
        return redirect('proveedores:lista')
    
    proveedor = get_object_or_404(Proveedor, id=id_proveedor)

    if request.method == 'POST':
        proveedor.estado = False
        proveedor.save()
        messages.success(request, 'Proveedor eliminado')
        return redirect('proveedores:lista')

    return render(request, 'proveedores/eliminar.html', {'proveedor': proveedor})

# =========================
# LISTAR PROVEEDORES INACTIVOS (ELIMINADOS)
# =========================
def lista_inactivos(request):
    # Verificar sesión
    if request.session.get('usuario_id') is None:
        return redirect('login')
    
    # Solo administrador puede ver y recuperar
    if request.session.get('rol') != 'administrador':
        messages.error(request, '❌ Acceso denegado. Solo el administrador puede recuperar proveedores.')
        return redirect('proveedores:lista')
    
    proveedores = Proveedor.objects.filter(estado=False)
    return render(request, 'proveedores/recuperar.html', {'proveedores': proveedores})


# =========================
# RECUPERAR PROVEEDOR (REACTIVAR)
# =========================
def recuperar_proveedor(request, id_proveedor):
    # Verificar sesión
    if request.session.get('usuario_id') is None:
        return redirect('login')
    
    # Solo administrador puede recuperar
    if request.session.get('rol') != 'administrador':
        messages.error(request, '❌ Acceso denegado. Solo el administrador puede recuperar proveedores.')
        return redirect('proveedores:lista')
    
    proveedor = get_object_or_404(Proveedor, id=id_proveedor, estado=False)
    proveedor.estado = True
    proveedor.save()
    messages.success(request, f'Proveedor "{proveedor.nomProv}" recuperado correctamente')
    return redirect('proveedores:inactivos')