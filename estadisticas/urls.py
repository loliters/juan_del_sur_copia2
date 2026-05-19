from django.urls import path
from . import views

app_name = 'estadisticas'

urlpatterns = [
    path('prediccion/', views.estadisticas_prediccion, name='prediccion'),
    path('top-productos/', views.estadisticas_top_productos, name='top_productos'),
]