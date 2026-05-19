from django.db import models

class Rol(models.Model):
    nom_rol = models.CharField(max_length=50)

    def __str__(self):
        return self.nom_rol


class Usuario(models.Model):
    nom_usuario = models.CharField(max_length=100)
    ap1 = models.CharField(max_length=100)
    ap2 = models.CharField(max_length=100, blank=True)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    estado = models.BooleanField(default=True)

    cambiar_password = models.BooleanField(default=True)

    rol = models.ForeignKey(Rol, on_delete=models.CASCADE)

    def __str__(self):
        return self.nom_usuario