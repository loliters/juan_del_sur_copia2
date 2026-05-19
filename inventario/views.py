from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Inventario


# =========================
# LISTAR INVENTARIO
# =========================
def lista_inventario(request):

    # Verificar sesión
    if request.session.get('usuario_id') is None:
        return redirect('login')

    # Obtener rol
    rol_usuario = request.session.get(
        'rol',
        ''
    ).lower()

    # Solo administrador
    if rol_usuario != 'administrador':

        messages.error(
            request,
            'Acceso denegado. Solo el administrador puede acceder al inventario.'
        )

        return redirect(
            'dashboard_admin'
        )

    # Cargar relaciones necesarias
    inventarios = Inventario.objects.select_related(
        'producto',
        'tipo_unidad'
    ).all()

    return render(
        request,
        'inventario/lista.html',
        {
            'inventarios': inventarios
        }
    )