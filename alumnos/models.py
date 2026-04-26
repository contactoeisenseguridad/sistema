from django.db import models


class Alumno(models.Model):
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    rut = models.CharField(max_length=12, unique=True)
    direccion = models.CharField(max_length=255)
    comuna = models.CharField(max_length=100, blank=True, null=True)
    correo = models.EmailField()
    telefono = models.CharField(max_length=20, blank=True, null=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.nombres:
            self.nombres = self.nombres.upper()
        if self.apellidos:
            self.apellidos = self.apellidos.upper()
        if self.rut:
            self.rut = self.rut.upper()
        if self.direccion:
            self.direccion = self.direccion.upper()
        if self.comuna:
            self.comuna = self.comuna.upper()
        if self.correo:
            self.correo = self.correo.upper()
        if self.telefono:
            self.telefono = self.telefono.upper()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nombres} {self.apellidos}"


class Inscripcion(models.Model):
    alumno = models.ForeignKey(
        Alumno,
        on_delete=models.CASCADE,
        related_name='inscripciones'
    )
    curso = models.CharField(max_length=100)
    grupo = models.CharField(max_length=50)
    fecha_inicio = models.DateField(blank=True, null=True)
    fecha_fin = models.DateField(blank=True, null=True)
    estado = models.CharField(max_length=50, blank=True, null=True)
    observaciones = models.TextField(blank=True, null=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.alumno} - {self.curso}"


class Auditoria(models.Model):
    usuario = models.CharField(max_length=100)
    accion = models.CharField(max_length=50)
    modelo = models.CharField(max_length=50)
    objeto_id = models.IntegerField()
    descripcion = models.TextField()
    fecha = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.usuario} - {self.accion} - {self.fecha}"