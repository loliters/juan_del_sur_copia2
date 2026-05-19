from django.contrib import admin
from django.urls import path, include
from usuarios import views as usuarios_views

urlpatterns = [

    # LOGIN
    path('', usuarios_views.login_view, name='login'),

    # ADMIN DJANGO
    path('admin/', admin.site.urls),

    # APPS
    path('usuarios/', include('usuarios.urls')),
    path('productos/', include('productos.urls')),
    path('categorias/', include('categorias.urls')),
    path('proveedores/', include('proveedores.urls')),
    path('clientes/', include('clientes.urls')),
    path('ventas/', include('ventas.urls')),
    path('inventario/', include('inventario.urls')),
    path('compras/', include('compras.urls')),
    path('reportes/', include('reportes.urls')),
    path('estadisticas/', include('estadisticas.urls')),
    path('presentacion/', include('presentacion.urls')),
    path('unidadmedida/', include('unidadmedida.urls')),
    # SOLO DESCOMENTA SI EXISTE urls.py EN LA APP
    # path('unidadmedida/', include('unidadmedida.urls')),

]