from django.db import models

class Proveedor(models.Model):
    nomProv = models.CharField(max_length=100)
    direccion = models.CharField(max_length=255)
    email = models.EmailField(blank=True, null=True, unique=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    estado = models.BooleanField(default=True)

    def __str__(self):
        return self.nomProv