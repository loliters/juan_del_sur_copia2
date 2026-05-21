from django.urls import path
from . import views

app_name = 'proveedores'

urlpatterns = [
    path('', views.lista_proveedores, name='lista'),
    path('crear/', views.crear_proveedor, name='crear'),
    path('editar/<int:id_proveedor>/', views.editar_proveedor, name='editar'),
    path('eliminar/<int:id_proveedor>/', views.eliminar_proveedor, name='eliminar'),

    path('inactivos/', views.lista_inactivos, name='inactivos'),
    path('recuperar/<int:id_proveedor>/', views.recuperar_proveedor, name='recuperar'),
    
    path('lista/', views.lista_proveedores, name='lista_proveedores'),

]