from django.urls import path
from . import views

app_name = 'presentacion'

urlpatterns = [
    path('crear/', views.crear_presentacion, name='crear'),
]