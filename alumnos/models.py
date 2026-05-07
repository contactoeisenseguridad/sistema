from django.db import models
from django.utils import timezone


class Alumno(models.Model):
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    rut = models.CharField(max_length=12, unique=True)
    direccion = models.CharField(max_length=255)
    comuna = models.CharField(max_length=100, blank=True, null=True)
    correo = models.EmailField()
    telefono = models.CharField(max_length=20, blank=True, null=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    rut_confirmado = models.BooleanField(default=False)

    # 🔵 Confirmación de correo
    correo_confirmado = models.BooleanField(default=False)
    codigo_confirmacion = models.CharField(max_length=4, blank=True, null=True)
    codigo_ingresado = models.CharField(
        max_length=4,
        blank=True,
        null=True,
        verbose_name="Código de confirmación"
    )
    fecha_codigo = models.DateTimeField(blank=True, null=True)
    intentos_codigo = models.IntegerField(default=0)

    class Meta:
        ordering = ['apellidos', 'nombres']

    def save(self, *args, **kwargs):
        import random

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

        if not self.codigo_confirmacion:
            self.codigo_confirmacion = str(random.randint(1000, 9999))

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.apellidos} {self.nombres}"


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


class Aviso(models.Model):
    titulo = models.CharField(max_length=200, default="Aviso")
    contenido = models.TextField()
    activo = models.BooleanField(default=True)
    fecha = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.titulo


class Pago(models.Model):
    METODO_PAGO = [
        ('EFECTIVO', 'Efectivo'),
        ('TRANSFERENCIA', 'Transferencia'),
        ('TARJETA', 'Tarjeta'),
        ('OTRO', 'Otro'),
    ]

    alumno = models.ForeignKey(Alumno, on_delete=models.CASCADE)
    inscripcion = models.ForeignKey(
        Inscripcion,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    metodo_pago = models.CharField(max_length=20, choices=METODO_PAGO)
    monto_total = models.PositiveIntegerField()
    cantidad_cuotas = models.PositiveIntegerField(default=1)

    fecha_pago = models.DateField(default=timezone.localdate)
    observaciones = models.TextField(blank=True, null=True)

    fecha_registro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.alumno} - ${self.monto_total}"


class Cuota(models.Model):
    ESTADO_CUOTA = [
        ('PENDIENTE', 'Pendiente'),
        ('PAGADA', 'Pagada'),
        ('VENCIDA', 'Vencida'),
    ]

    pago = models.ForeignKey(
        Pago,
        on_delete=models.CASCADE,
        related_name='cuotas'
    )
    numero_cuota = models.PositiveIntegerField()
    monto = models.PositiveIntegerField()
    fecha_vencimiento = models.DateField()
    fecha_pago = models.DateField(blank=True, null=True)

    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CUOTA,
        default='PENDIENTE'
    )

    class Meta:
        ordering = ['fecha_vencimiento']
        # 👇 AQUÍ ESTÁ EL PERMISO NUEVO DE SEGURIDAD
        permissions = [
            ("can_edit_locked_cuotas", "Puede editar cuotas ya ingresadas"),
        ]
        verbose_name_plural = "Listado de Deudores"

    def save(self, *args, **kwargs):
        if self.estado == 'PAGADA' and not self.fecha_pago:
            self.fecha_pago = timezone.localdate()

        if self.estado == 'PENDIENTE':
            self.fecha_pago = None
            # 👇 Ajuste de indentación aquí
            if self.fecha_vencimiento < timezone.localdate():
                self.estado = 'VENCIDA'

        if self.estado == 'VENCIDA':
            self.fecha_pago = None

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Cuota {self.numero_cuota} - {self.estado}"


class GastoOperacional(models.Model):
    grupo = models.CharField(max_length=100, blank=True, null=True)
    concepto = models.CharField(max_length=200)
    monto = models.PositiveIntegerField()
    fecha = models.DateField(default=timezone.localdate)
    observaciones = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.concepto} - ${self.monto}"