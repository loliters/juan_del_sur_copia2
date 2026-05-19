"""
URL configuration for sistema project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from usuarios import views as usuarios_views   # ← importa las vistas de usuarios
 
urlpatterns = [
    path('', usuarios_views.login_view, name='login'),   # ← raíz apunta al login
    path('admin/', admin.site.urls),
    path('productos/', include('productos.urls')),
    path('usuarios/', include('usuarios.urls')),
    path('categorias/', include('categorias.urls')),
    path('proveedores/', include('proveedores.urls')),
    #path('dashboard/', views.dashboard_admin, name='dashboard_admin')
    path('clientes/', include('clientes.urls')),

    path('ventas/', include('ventas.urls')),
    
    path('compras/', include('compras.urls')),
    path('reportes/', include('reportes.urls')),
    #para lo de estadistica 5ta iteracion
    path('estadisticas/', include('estadisticas.urls')),
    
]