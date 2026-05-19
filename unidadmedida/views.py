from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import UnidadMedida
import re


# =========================
# GENERAR ABREVIATURA
# =========================
def generar_abreviatura(nombre):
    nombre = nombre.lower().strip()

    abreviaturas = {
        'kilogramo': 'kg',
        'kilogramos': 'kg',
        'kilo': 'kg',
        'kilos': 'kg',

        'gramo': 'g',
        'gramos': 'g',

        'litro': 'lt',
        'litros': 'lts',

        'mililitro': 'ml',
        'mililitros': 'ml',

        'unidad': 'und',
        'unidades': 'und',

        'metro': 'm',
        'metros': 'm',

        'centimetro': 'cm',
        'centimetros': 'cm',
        'centímetro': 'cm',
        'centímetros': 'cm',

        'caja': 'cj',
        'cajas': 'cj',

        'paquete': 'pqt',
        'paquetes': 'pqt',
    }

    if nombre in abreviaturas:
        return abreviaturas[nombre]

    palabras = nombre.split()

    if len(palabras) == 1:
        return nombre[:3].capitalize()

    return ''.join(p[0].upper() for p in palabras)


# =========================
# VALIDAR SOLO LETRAS
# =========================
def solo_letras(texto):
    if not texto:
        return False

    patron = r'^[A-Za-zÁÉÍÓÚáéíóúÑñ\s\-]+$'
    return re.match(patron, texto) is not None


# =========================
# LISTAR
# =========================
def lista_unidades(request):

    if request.session.get('usuario_id') is None:
        return redirect('login')

    unidades = UnidadMedida.objects.filter(estado=True)

    return render(request, 'unidadmedida/lista.html', {
        'unidades': unidades
    })


# =========================
# CREAR
# =========================
def crear_unidad(request):

    if request.session.get('usuario_id') is None:
        return redirect('login')

    if request.session.get('rol') != 'administrador':
        messages.error(request, 'Solo el administrador puede crear')
        return redirect('unidadmedida:lista')

    if request.method == 'POST':

        nombre = request.POST.get('nombre')

        if nombre:
            nombre = nombre.strip()

        if not nombre:
            messages.error(request, 'El nombre es obligatorio')
            return redirect('unidadmedida:crear')

        if not solo_letras(nombre):
            messages.error(request, 'Solo se permiten letras')
            return redirect('unidadmedida:crear')

        if UnidadMedida.objects.filter(nombre__iexact=nombre).exists():
            messages.error(request, 'La unidad ya existe')
            return redirect('unidadmedida:crear')

        abreviatura = generar_abreviatura(nombre)

        UnidadMedida.objects.create(
            nombre=nombre,
            abreviatura=abreviatura,
            estado=True
        )

        messages.success(request, 'Unidad creada correctamente')
        return redirect('unidadmedida:lista')

    return render(request, 'unidadmedida/crear.html')


# =========================
# EDITAR
# =========================
def editar_unidadmedida(request, id):

    if request.session.get('usuario_id') is None:
        return redirect('login')

    if request.session.get('rol') != 'administrador':
        messages.error(request, 'Solo el administrador puede editar')
        return redirect('unidadmedida:lista')

    unidad = get_object_or_404(UnidadMedida, id=id)

    if request.method == 'POST':

        nombre = request.POST.get('nombre')

        if nombre:
            nombre = nombre.strip()

        if not nombre:
            messages.error(request, 'El nombre es obligatorio')
            return redirect('unidadmedida:editar', id=id)

        if not solo_letras(nombre):
            messages.error(request, 'Solo se permiten letras')
            return redirect('unidadmedida:editar', id=id)

        if UnidadMedida.objects.filter(nombre__iexact=nombre).exclude(id=unidad.id).exists():
            messages.error(request, 'Ya existe otra unidad con ese nombre')
            return redirect('unidadmedida:editar', id=id)

        unidad.nombre = nombre
        unidad.abreviatura = generar_abreviatura(nombre)
        unidad.save()

        messages.success(request, 'Unidad actualizada correctamente')
        return redirect('unidadmedida:lista')

    return render(request, 'unidadmedida/editar.html', {
        'unidad': unidad
    })


# =========================
# ELIMINAR
# =========================
def eliminar_unidadmedida(request, id):

    if request.session.get('usuario_id') is None:
        return redirect('login')

    if request.session.get('rol') != 'administrador':
        messages.error(request, 'Solo el administrador puede eliminar')
        return redirect('unidadmedida:lista')

    unidad = get_object_or_404(UnidadMedida, id=id)

    if request.method == 'POST':

        unidad.estado = False
        unidad.save()

        messages.success(request, 'Unidad eliminada correctamente')
        return redirect('unidadmedida:lista')

    return render(request, 'unidadmedida/eliminar.html', {
        'unidad': unidad
    })


# =========================
# INACTIVAS
# =========================
def inactivas_unidadmedida(request):

    if request.session.get('usuario_id') is None:
        return redirect('login')

    unidades = UnidadMedida.objects.filter(estado=False)

    return render(request, 'unidadmedida/inactivas.html', {
        'unidades': unidades
    })


# =========================
# RECUPERAR
# =========================
def recuperar_unidadmedida(request, id):

    if request.session.get('usuario_id') is None:
        return redirect('login')

    unidad = get_object_or_404(UnidadMedida, id=id)

    unidad.estado = True
    unidad.save()

    messages.success(request, 'Unidad recuperada correctamente')

    return redirect('unidadmedida:inactivas')