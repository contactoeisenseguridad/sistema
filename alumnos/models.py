from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.utils.html import format_html
import random


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
        if self.nombres: self.nombres = self.nombres.upper()
        if self.apellidos: self.apellidos = self.apellidos.upper()
        if self.rut: self.rut = self.rut.upper()
        if self.direccion: self.direccion = self.direccion.upper()
        if self.comuna: self.comuna = self.comuna.upper()
        if self.correo: self.correo = self.correo.upper()
        if self.telefono: self.telefono = self.telefono.upper()

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

    # 4. FECHA DE PAGO ELIMINADA DEL FORMULARIO (Se deja null en el modelo)
    fecha_pago = models.DateField(null=True, blank=True) 
    observaciones = models.TextField(blank=True, null=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        # CAMBIO DE NOMBRE A COBROS
        verbose_name = "Cobro"
        verbose_name_plural = "Cobros"

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
    
    # Se mantiene para registro interno cuando se marque como PAGADA
    fecha_pago = models.DateField(blank=True, null=True)

    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CUOTA,
        default='PENDIENTE'
    )

    class Meta:
        ordering = ['fecha_vencimiento']
        permissions = [
            ("can_edit_locked_cuotas", "Puede editar cuotas ya ingresadas"),
        ]
        # PUNTO 6: NOMBRE EN EL MENU PRINCIPAL
        verbose_name = "Cuota / Deuda"
        verbose_name_plural = "Listado de Deudores"

    def save(self, *args, **kwargs):
        hoy = timezone.localdate()
        
        if self.estado == 'PAGADA' and not self.fecha_pago:
            self.fecha_pago = hoy

        if self.estado == 'PENDIENTE':
            self.fecha_pago = None
            if self.fecha_vencimiento < hoy:
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


# ==========================================
# 🛡️ NUEVOS MODELOS: SEGURIDAD Y ASISTENCIA
# ==========================================

class PerfilUsuario(models.Model):
    ROLES = [
        ('RELATOR', 'Relator Autorizado'),
        ('FISCALIZADOR', 'Fiscalizador / Auditor'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    rol = models.CharField(max_length=20, choices=ROLES)
    rut = models.CharField(max_length=12, unique=True, null=True, blank=True)
    pin = models.CharField(max_length=4, default="0000", help_text="PIN de 4 dígitos para acceso rápido")
    intentos_fallidos = models.IntegerField(default=0)
    bloqueado = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} - {self.get_rol_display()}"


class Modulo(models.Model):
    nombre = models.CharField(max_length=200)

    def __str__(self):
        return self.nombre


class SesionClase(models.Model):
    MODALIDAD_CHOICES = [
        ('ONLINE', 'Aula Virtual (Online)'),
        ('PRESENCIAL', 'Terreno (Presencial)'),
    ]
    
    grupo = models.CharField(max_length=50, help_text="Debe coincidir con el grupo de la inscripción") 
    modulo = models.ForeignKey(Modulo, on_delete=models.CASCADE)
    # 👇 NUEVO: Ahora cada clase tiene un relator asignado
    relator = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        limit_choices_to={'perfilusuario__rol': 'RELATOR'},
        related_name='clases_dictadas'
    )
    fecha = models.DateField(default=timezone.localdate)
    bloque_horario = models.CharField(max_length=100, help_text="Ej: 09:00 a 11:00") 
    horas_bloque = models.IntegerField(default=2) 
    modalidad = models.CharField(max_length=20, choices=MODALIDAD_CHOICES, default='ONLINE')

    class Meta:
        verbose_name = "Sesión de Clase"
        verbose_name_plural = "Programación de Clases (Calendario)"
        ordering = ['fecha', 'bloque_horario']

    def __str__(self):
        relator_name = self.relator.get_full_name() if self.relator else "Sin Relator"
        return f"{self.fecha} | {self.bloque_horario} | {self.modulo.nombre} | {relator_name}"


class Asistencia(models.Model):
    alumno = models.ForeignKey(Alumno, on_delete=models.CASCADE)
    sesion = models.ForeignKey(SesionClase, on_delete=models.CASCADE)
    presente = models.BooleanField(default=False) 

    class Meta:
        unique_together = ('alumno', 'sesion') 
        
    def __str__(self):
        estado = "✅ Presente" if self.presente else "❌ Ausente"
        return f"{self.alumno} - {self.sesion.modulo} ({estado})"


class PlanillaSPD(models.Model):
    """Modelo para subir y procesar el Excel oficial de la SPD"""
    grupo = models.CharField(max_length=50, help_text="Ej: FGS352026. Se vinculará a este grupo.")
    archivo_excel = models.FileField(upload_to='planillas_spd/', help_text="Sube el archivo .xlsx de la SPD aquí")
    fecha_subida = models.DateTimeField(auto_now_add=True)
    procesado = models.BooleanField(default=False, help_text="Indica si el sistema ya leyó y creó las clases de este Excel")

    class Meta:
        verbose_name = "Planilla SPD"
        verbose_name_plural = "Planillas SPD (Carga de Clases)"

    def __str__(self):
        return f"Planilla Grupo {self.grupo} - Subida: {self.fecha_subida.strftime('%d/%m/%Y')}"