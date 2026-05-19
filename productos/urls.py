from django.urls import path
from . import views

app_name = 'productos'

urlpatterns = [

    # Inicio / Inventario
    path(
        '',
        views.inventario,
        name='index'
    ),

    path(
        'inventario/',
        views.inventario,
        name='inventario'
    ),

    # CRUD productos
    path(
        'registrar/',
        views.registrar,
        name='registrar'
    ),

    path(
        'editar/<int:id_producto>/',
        views.editar,
        name='editar'
    ),

    path(
        'eliminar/<int:id_producto>/',
        views.eliminar,
        name='eliminar'
    ),

    # Recuperación
    path(
        'recuperar/',
        views.lista_recuperar,
        name='lista_recuperar'
    ),

    path(
        'recuperar/<int:id_producto>/',
        views.ejecutar_recuperacion,
        name='ejecutar_recuperacion'
    ),

    # API próximo código
    path(
        'proximo-id/',
        views.proximo_id_api,
        name='proximo_id'
    ),

]