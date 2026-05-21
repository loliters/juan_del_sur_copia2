# clientes/models.py
from django.db import models

class Cliente(models.Model):
    id_cliente = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    razonSocial = models.CharField(max_length=150, blank=True, null=True)
    carnet = models.CharField(max_length=20, blank=True, null=True, unique=True)  # ← AGREGAR
    email = models.EmailField(unique=True)
    telefono = models.CharField(max_length=20, unique=True)
    zona = models.CharField(max_length=100)
    calle = models.CharField(max_length=100)
    numeroCasa = models.CharField(max_length=20)
    estado = models.BooleanField(default=True)

   

    def __str__(self):
        return self.nombre