from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Producto
from categorias.models import Categoria
from presentacion.models import Presentacion
from inventario.models import Inventario
from decimal import Decimal
import re
from django.http import JsonResponse

def verificar_duplicado_api(request):
    nombre = request.GET.get('nombre', '').strip()
    presentacion_id = request.GET.get('presentacion')
    
    if not nombre:
        return JsonResponse({'existe': False})
    
    presentacion_obj = None
    if presentacion_id:
        try:
            from presentacion.models import Presentacion
            presentacion_obj = Presentacion.objects.get(id=presentacion_id)
        except:
            pass
    
    existe = Producto.objects.filter(
        nomProducto__iexact=nombre,
        presentacion=presentacion_obj,
        estado='activo'
    ).exists()
    
    return JsonResponse({'existe': existe})


# =========================
# GENERAR CÓDIGO PRODUCTO
# =========================

def generar_codigo_producto(nombre, presentacion_id):
    nombre_abrev = re.sub(
        r'[^A-Za-z0-9]',
        '',
        nombre
    )[:4].upper()

    presentacion = None

    if presentacion_id:
        presentacion = Presentacion.objects.filter(
            id=presentacion_id
        ).first()

    pres_abrev = (
        presentacion.medida.abreviatura.upper()
        if presentacion
        else 'GEN'
    )

    ultimo = Producto.objects.order_by(
        '-id'
    ).first()

    nuevo_id = (
        ultimo.id + 1
    ) if ultimo else 1

    id_formateado = str(
        nuevo_id
    ).zfill(3)

    return f"{nombre_abrev}_{pres_abrev}_{id_formateado}"


# =========================
# LISTAR PRODUCTOS
# =========================

def inventario(request):

    if request.session.get(
        'usuario_id'
    ) is None:

        return redirect(
            'login'
        )

    productos = Producto.objects.filter(
        estado='activo'
    ).select_related(
        'presentacion',
        'presentacion__medida',
        'categoria'
    )

    if request.session.get(
        'rol'
    ) == 'cajero':

        return render(
            request,
            'productos/lista.html',
            {
                'productos': productos
            }
        )

    return render(
        request,
        'productos/inventario.html',
        {
            'productos': productos
        }
    )


# =========================
# REGISTRAR PRODUCTO
# =========================

def registrar(request):

    if request.session.get(
        'usuario_id'
    ) is None:

        return redirect(
            'login'
        )

    if request.session.get(
        'rol'
    ) != 'administrador':

        messages.error(
            request,
            'Acceso denegado'
        )

        return redirect(
            'productos:inventario'
        )

    if request.method == 'POST':

        nomProducto = request.POST.get(
            'nomProducto'
        )

        categoria_id = request.POST.get(
            'categoria'
        )

        presentacion_id = request.POST.get(
            'presentacion'
        )

        precioCompra = request.POST.get(
            'precioCompra'
        )

        precioVenta = request.POST.get(
            'precioVenta'
        )

        codProducto = request.POST.get(
            'codProducto'
        )

        if not nomProducto:

            messages.error(
                request,
                'El nombre es obligatorio'
            )

            return redirect(
                'productos:registrar'
            )

        # ==============================================
        # VALIDACIÓN: No permitir mismo nombre + misma presentación
        # ==============================================
        presentacion_obj = None
        if presentacion_id:
            presentacion_obj = get_object_or_404(Presentacion, id=presentacion_id)

        duplicado = Producto.objects.filter(
            nomProducto__iexact=nomProducto,
            presentacion=presentacion_obj,
            estado='activo'
        ).exists()

        if duplicado:
            messages.error(
                request,
                f'Ya existe un producto activo con el nombre "{nomProducto}" y la misma presentación. '
                'No se puede crear otro igual.'
            )
            return redirect('productos:registrar')
        # ==============================================

        if Producto.objects.filter(
            codProducto=codProducto
        ).exists():

            codProducto = generar_codigo_producto(
                nomProducto,
                presentacion_id
            )

        categoria = None

        if categoria_id:
            categoria = get_object_or_404(
                Categoria,
                id=categoria_id
            )

        presentacion = None

        if presentacion_id:

            presentacion = get_object_or_404(
                Presentacion,
                id=presentacion_id
            )

        producto = Producto.objects.create(

            codProducto=codProducto,

            nomProducto=nomProducto,

            categoria=categoria,

            presentacion=presentacion,

            precioCompra=Decimal(
                precioCompra.replace(',', '.')
                if precioCompra
                else '0.00'
            ),

            precioVenta=Decimal(
                precioVenta.replace(',', '.')
                if precioVenta
                else '0.00'
            ),

            stockMinimo=2,

            estado='activo',

            usuario_id=request.session.get(
                'usuario_id'
            )
        )

        Inventario.objects.create(
            producto=producto,
            stock_actual=0
        )

        messages.success(
            request,
            f'Producto "{nomProducto}" creado correctamente'
        )

        return redirect(
            'productos:inventario'
        )

    categorias = Categoria.objects.filter(
        estado=True
    )

    presentaciones = Presentacion.objects.select_related(
        'medida'
    )

    return render(
        request,
        'productos/registrar.html',
        {
            'categorias': categorias,
            'presentaciones': presentaciones
        }
    )


# =========================
# EDITAR PRODUCTO
# =========================

def editar(request, id_producto):

    if request.session.get(
        'usuario_id'
    ) is None:

        return redirect(
            'login'
        )

    producto = get_object_or_404(
        Producto,
        id=id_producto
    )

    categorias = Categoria.objects.filter(
        estado=True
    )

    presentaciones = Presentacion.objects.select_related(
        'medida'
    )

    if request.method == 'POST':

        producto.nomProducto = request.POST.get(
            'nomProducto'
        )

        categoria_id = request.POST.get(
            'categoria'
        )

        presentacion_id = request.POST.get(
            'presentacion'
        )

        producto.categoria = get_object_or_404(
            Categoria,
            id=categoria_id
        )

        producto.presentacion = (
            get_object_or_404(
                Presentacion,
                id=presentacion_id
            )
            if presentacion_id
            else None
        )

        try:

            producto.precioCompra = Decimal(
                request.POST.get(
                    'precioCompra',
                    '0'
                ).replace(',', '.')
            )

            producto.precioVenta = Decimal(
                request.POST.get(
                    'precioVenta',
                    '0'
                ).replace(',', '.')
            )

        except:

            producto.precioCompra = Decimal(
                '0.00'
            )

            producto.precioVenta = Decimal(
                '0.00'
            )

        producto.estado = request.POST.get(
            'estado'
        )
        stock = request.POST.get('stockActual')

        if stock:
            producto.stockActual = int(stock)

        producto.save()

        messages.success(
            request,
            'Producto actualizado'
        )

        return redirect(
            'productos:inventario'
        )

    return render(
        request,
        'productos/editar.html',
        {
            'producto': producto,
            'categorias': categorias,
            'presentaciones': presentaciones
        }
    )


# =========================
# ELIMINAR
# =========================

def eliminar(request, id_producto):

    producto = get_object_or_404(
        Producto,
        id=id_producto
    )

    producto.estado = 'inactivo'
    producto.save()

    messages.success(
        request,
        'Producto eliminado'
    )

    return redirect(
        'productos:inventario'
    )


# =========================
# RECUPERAR
# =========================

def lista_recuperar(request):

    productos = Producto.objects.filter(
        estado='inactivo'
    ).select_related(
        'presentacion',
        'presentacion__medida'
    )

    return render(
        request,
        'productos/recuperar.html',
        {
            'productos': productos
        }
    )


def ejecutar_recuperacion(
    request,
    id_producto
):

    producto = get_object_or_404(
        Producto,
        id=id_producto
    )

    producto.estado = 'activo'
    producto.save()

    return redirect(
        'productos:lista_recuperar'
    )


# =========================
# API PRÓXIMO ID
# =========================

def proximo_id_api(request):

    from django.http import JsonResponse

    ultimo = Producto.objects.order_by(
        '-id'
    ).first()

    proximo_id = (
        ultimo.id + 1
    ) if ultimo else 1

    return JsonResponse(
        {
            'proximo_id': proximo_id
        }
    )


# =========================
# LOGOUT
# =========================

def logout_view(request):

    request.session.flush()

    return redirect(
        'login'
    )