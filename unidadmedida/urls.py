from django.urls import path
from . import views

app_name = 'unidadmedida'

urlpatterns = [

    path('', views.lista_unidades, name='lista'),

    path('crear/', views.crear_unidad, name='crear'),

    path('editar/<int:id_unidad>/', views.editar_unidadmedida, name='editar'),

    path('eliminar/<int:id_unidad>/', views.eliminar_unidadmedida, name='eliminar'),

    path('inactivas/', views.inactivas_unidadmedida, name='inactivas'),

    path('recuperar/<int:id_unidad>/', views.recuperar_unidadmedida, name='recuperar'),
]