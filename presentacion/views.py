from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Presentacion
from unidadmedida.models import UnidadMedida


def crear_presentacion(request):
    if request.session.get('usuario_id') is None:
        return redirect('login')

    if request.session.get('rol') != 'administrador':
        messages.error(request, 'Solo el administrador puede crear')
        return redirect('productos:inventario')

    unidades = UnidadMedida.objects.filter(estado=True)

    if request.method == 'POST':
        cantidad = request.POST.get('cantidad')
        medida_id = request.POST.get('medida')

        if not cantidad:
            messages.error(request, 'La cantidad es obligatoria')
            return redirect('presentacion:crear')

        try:
            cantidad = float(cantidad)

            if cantidad <= 0:
                messages.error(request, 'La cantidad debe ser mayor a 0')
                return redirect('presentacion:crear')

        except ValueError:
            messages.error(request, 'Cantidad inválida')
            return redirect('presentacion:crear')

        if not medida_id:
            messages.error(
                request,
                'Debe seleccionar una unidad de medida'
            )
            return redirect('presentacion:crear')

        medida = get_object_or_404(
            UnidadMedida,
            id=medida_id,
            estado=True
        )

        Presentacion.objects.create(
            cantidad=cantidad,
            medida=medida
        )

        messages.success(
            request,
            f'Presentación {cantidad} {medida.abreviatura} creada correctamente'
        )

        next_url = request.GET.get('next')

        if next_url:
            return redirect(next_url)

        return redirect('productos:inventario')

    return render(
        request,
        'presentacion/crear.html',
        {
            'unidades': unidades,
        }
    )