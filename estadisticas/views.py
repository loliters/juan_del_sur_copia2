from django.shortcuts import render
from django.db.models import Sum
from django.db.models.functions import TruncDate, ExtractYear
from django.utils import timezone
from datetime import timedelta
import json
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression

from productos.models import Producto
from categorias.models import Categoria
from ventas.models import DetalleVenta
from inventario.models import Inventario


def estadisticas_prediccion(request):
    """
    Regresión Lineal con pandas + sklearn
    x = tiempo (días consecutivos), y = cantidad vendida
    """
    producto_id = request.GET.get('producto')
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')

    # 1. Stock actual total del producto (suma de todas sus presentaciones)
    stock_total = 0
    producto_nombre = "Selecciona un producto"
    
    if producto_id:
        inventarios = Inventario.objects.filter(producto_id=producto_id)
        stock_total = inventarios.aggregate(total=Sum('stock_actual'))['total'] or 0
        if inventarios.exists():
            producto_nombre = inventarios.first().producto.nomProducto

    # 2. Obtener historial de ventas agrupado por día
    ventas_query = DetalleVenta.objects.filter(inventario__producto_id=producto_id)
    
    if fecha_inicio:
        ventas_query = ventas_query.filter(venta__fecha__gte=fecha_inicio)
    if fecha_fin:
        ventas_query = ventas_query.filter(venta__fecha__lte=fecha_fin)

    ventas_por_dia = ventas_query.annotate(
        dia=TruncDate('venta__fecha')
    ).values('dia').annotate(
        cantidad_vendida=Sum('cantidad')
    ).order_by('dia')

    # 3. Crear DataFrame con pandas para análisis
    data = []
    for v in ventas_por_dia:
        data.append({
            'fecha': v['dia'],
            'fecha_str': v['dia'].strftime('%Y-%m-%d'),
            'cantidad': v['cantidad_vendida'] or 0
        })
    
    df = pd.DataFrame(data)
    
    labels = []
    medicion_data = []
    estimacion_data = []
    pendiente_b = 0
    intercepto_a = 0
    fecha_agotamiento = None

    # 4. Aplicar regresión lineal con sklearn si hay suficientes datos
    if len(df) >= 2:
        # Preparar variables: x = días consecutivos, y = cantidad vendida
        df['x'] = np.arange(1, len(df) + 1)  # Variable independiente: tiempo
        df['y'] = df['cantidad']              # Variable dependiente: ventas
        
        # Entrenar modelo de regresión lineal
        X = df[['x']].values  # sklearn requiere array 2D
        y = df['y'].values
        
        model = LinearRegression()
        model.fit(X, y)
        
        # Obtener parámetros del modelo
        pendiente_b = model.coef_[0]      # b = pendiente
        intercepto_a = model.intercept_   # a = intercepto
        
        # Generar predicciones para la línea de tendencia
        df['y_pred'] = model.predict(X)
        
        # Preparar datos para el gráfico
        labels = df['fecha_str'].tolist()
        medicion_data = df['y'].tolist()
        estimacion_data = df['y_pred'].round(2).tolist()
        
        # 5. Calcular cuándo se agotará el stock usando la ecuación: y = a + bx
        # Cuando y = stock_total, despejamos x: x = (stock_total - a) / b
        if pendiente_b > 0 and stock_total > 0:
            dias_desde_inicio = (stock_total - intercepto_a) / pendiente_b
            # Convertir a fecha real: primera fecha + días calculados
            primera_fecha = df['fecha'].iloc[0]
            fecha_agotamiento = primera_fecha + timedelta(days=int(dias_desde_inicio))
            
        # 6. Calcular métricas de calidad del modelo (opcional pero útil)
        r2_score = model.score(X, y)  # Coeficiente de determinación

    context = {
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
        'r2_score': round(r2_score, 4) if 'r2_score' in locals() else None,
        'n_registros': len(df),
    }
    return render(request, 'estadisticas/prediccion.html', context)


def estadisticas_top_productos(request):
    """
    Ranking de productos con mayor demanda usando pandas para procesamiento
    """
    top_n = int(request.GET.get('top', 5))
    categoria_id = request.GET.get('categoria')
    mes = request.GET.get('mes')
    anio = request.GET.get('anio')

    # Query base: cruzar DetalleVenta → Inventario → Producto
    query = DetalleVenta.objects.values(
        'inventario__producto__id',
        'inventario__producto__nomProducto',
        'inventario__producto__categoria__id',
        'inventario__producto__categoria__nomCategoria'
    )

    # Aplicar filtros
    if categoria_id:
        query = query.filter(inventario__producto__categoria_id=categoria_id)
    if mes:
        query = query.filter(venta__fecha__month=int(mes))
    if anio:
        query = query.filter(venta__fecha__year=int(anio))

    # Agrupar y sumar ventas por producto
    top_data = query.annotate(
        total_vendido=Sum('cantidad')
    ).order_by('-total_vendido')[:top_n]

    # Convertir a DataFrame para procesamiento opcional con pandas
    df_top = pd.DataFrame(list(top_data))
    
    productos_labels = df_top['inventario__producto__nomProducto'].tolist() if not df_top.empty else []
    ventas_data = df_top['total_vendido'].fillna(0).tolist() if not df_top.empty else []

    # Obtener años disponibles dinámicamente desde la BD
    anos_disponibles = DetalleVenta.objects.annotate(
        ano=ExtractYear('venta__fecha')
    ).values_list('ano', flat=True).distinct().order_by('-ano')

    context = {
        'categorias': Categoria.objects.all(),
        'productos_labels': json.dumps(productos_labels),
        'ventas_data': json.dumps(ventas_data),
        'top_n': top_n,
        'mes': mes,
        'anio': anio,
        'anos_disponibles': list(anos_disponibles),
        'total_registros': len(df_top),
    }
    return render(request, 'estadisticas/top_productos.html', context)