from django.shortcuts import render
from django.db.models import Sum
from django.db.models.functions import TruncDate, ExtractYear
from datetime import timedelta
import json
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression

from productos.models import Producto
from categorias.models import Categoria
from ventas.models import DetalleVenta
from inventario.models import Inventario


# =========================
# PREDICCIÓN DE STOCK
# =========================
def estadisticas_prediccion(request):
    producto_id = request.GET.get('producto')
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')

    stock_total = 0
    producto_nombre = "Selecciona un producto"

    # =========================
    # SI NO HAY PRODUCTO → FORZAR GRAFICA VACÍA
    # =========================
    if not producto_id:
        return render(request, 'estadisticas/prediccion.html', {
            'productos': Producto.objects.all(),
            'labels': json.dumps(["Sin datos 1", "Sin datos 2", "Sin datos 3"]),
            'medicion_data': json.dumps([0, 0, 0]),
            'estimacion_data': json.dumps([0, 0, 0]),
            'fecha_agotamiento': None,
            'stock_actual': 0,
            'nombre_producto': producto_nombre,
            'pendiente': 0,
            'intercepto': 0,
            'r2_score': None,
            'n_registros': 0,
        })

    inventarios = Inventario.objects.filter(producto_id=producto_id)
    stock_total = inventarios.aggregate(total=Sum('stock_actual'))['total'] or 0

    if inventarios.exists():
        producto_nombre = inventarios.first().producto.nomProducto

    ventas_query = DetalleVenta.objects.filter(
        inventario__producto_id=producto_id
    )

    if fecha_inicio:
        ventas_query = ventas_query.filter(venta__fecha__gte=fecha_inicio)

    if fecha_fin:
        ventas_query = ventas_query.filter(venta__fecha__lte=fecha_fin)

    ventas_query = (
        ventas_query
        .annotate(dia=TruncDate('venta__fecha'))
        .values('dia')
        .annotate(cantidad_vendida=Sum('cantidad'))
        .order_by('dia')
    )

    data = [
        {
            'fecha': v['dia'],
            'fecha_str': v['dia'].strftime('%Y-%m-%d'),
            'cantidad': v['cantidad_vendida'] or 0
        }
        for v in ventas_query
        if v['dia']
    ]

    df = pd.DataFrame(data)

    labels = []
    medicion_data = []
    estimacion_data = []
    pendiente_b = 0
    intercepto_a = 0
    fecha_agotamiento = None
    r2_score = None

    # =========================
    # MODELO IA (REGRESIÓN LINEAL)
    # =========================
    if len(df) >= 2:
        df['x'] = np.arange(1, len(df) + 1)
        df['y'] = df['cantidad']

        X = df[['x']].values
        y = df['y'].values

        model = LinearRegression()
        model.fit(X, y)

        pendiente_b = model.coef_[0]
        intercepto_a = model.intercept_

        df['y_pred'] = model.predict(X)

        labels = df['fecha_str'].tolist()
        medicion_data = df['y'].tolist()
        estimacion_data = df['y_pred'].round(2).tolist()

        # =========================
        # FECHA DE AGOTAMIENTO
        # =========================
        if pendiente_b != 0 and stock_total > 0:
            dias = (stock_total - intercepto_a) / pendiente_b

            if dias > 0:
                fecha_base = df['fecha'].iloc[-1]
                fecha_agotamiento = fecha_base + timedelta(days=int(round(dias)))

        r2_score = model.score(X, y)

    else:
        # =========================
        # FORZAR GRAFICA SI NO HAY DATOS
        # =========================
        labels = ["Sin datos 1", "Sin datos 2", "Sin datos 3"]
        medicion_data = [0, 0, 0]
        estimacion_data = [0, 0, 0]

        pendiente_b = 0
        intercepto_a = 0
        r2_score = None

    # =========================
    # RETURN FINAL SEGURO
    # =========================
    return render(request, 'estadisticas/prediccion.html', {
        'productos': Producto.objects.all(),

        'labels': json.dumps(labels),
        'medicion_data': json.dumps(medicion_data),
        'estimacion_data': json.dumps(estimacion_data),

        'fecha_agotamiento': fecha_agotamiento,
        'stock_actual': stock_total,
        'nombre_producto': producto_nombre,

        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,

        'pendiente': round(pendiente_b, 4),
        'intercepto': round(intercepto_a, 4),
        'r2_score': round(r2_score, 4) if r2_score is not None else None,
        'n_registros': len(df),
    })


# =========================
# TOP PRODUCTOS
# =========================
def estadisticas_top_productos(request):
    top_n = int(request.GET.get('top', 5))
    categoria_id = request.GET.get('categoria')
    mes = request.GET.get('mes')
    anio = request.GET.get('anio')

    query = DetalleVenta.objects.values(
        'inventario__producto__nomProducto'
    ).annotate(
        total_vendido=Sum('cantidad')
    ).order_by('-total_vendido')

    if categoria_id:
        query = query.filter(inventario__producto__categoria_id=categoria_id)
    if mes:
        query = query.filter(venta__fecha__month=int(mes))
    if anio:
        query = query.filter(venta__fecha__year=int(anio))

    query = query[:top_n]

    productos_labels = [q['inventario__producto__nomProducto'] for q in query]
    ventas_data = [q['total_vendido'] for q in query]

    anos_disponibles = DetalleVenta.objects.annotate(
        ano=ExtractYear('venta__fecha')
    ).values_list('ano', flat=True).distinct().order_by('-ano')

    return render(request, 'estadisticas/top_productos.html', {
        'categorias': Categoria.objects.all(),
        'productos_labels': json.dumps(productos_labels),
        'ventas_data': json.dumps(ventas_data),
        'top_n': top_n,
        'mes': mes,
        'anio': anio,
        'anos_disponibles': list(anos_disponibles),
    })