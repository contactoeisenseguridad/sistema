from django.contrib import admin, messages
from django.db.models import OuterRef, Subquery
from django.utils.html import format_html
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone
from datetime import timedelta
import ssl
import random

from .models import (
    Alumno,
    Inscripcion,
    Auditoria,
    Aviso,
    Pago,
    Cuota,
    GastoOperacional,
)


admin.site.register(Aviso)


def validar_rut_chileno(rut):
    rut = rut.upper().replace(".", "").replace("-", "").strip()

    if len(rut) < 2:
        return False

    cuerpo = rut[:-1]
    dv = rut[-1]

    if not cuerpo.isdigit():
        return False

    suma = 0
    multiplo = 2

    for numero in reversed(cuerpo):
        suma += int(numero) * multiplo
        multiplo += 1
        if multiplo > 7:
            multiplo = 2

    resto = suma % 11
    dv_calculado = 11 - resto

    if dv_calculado == 11:
        dv_calculado = "0"
    elif dv_calculado == 10:
        dv_calculado = "K"
    else:
        dv_calculado = str(dv_calculado)

    return dv == dv_calculado


def formatear_rut(rut):
    rut = rut.upper().replace(".", "").replace("-", "").strip()
    cuerpo = rut[:-1]
    dv = rut[-1]

    return f"{cuerpo}-{dv}"


class InscripcionInline(admin.TabularInline):
    model = Inscripcion
    extra = 1

class PagoInline(admin.TabularInline):
    model = Pago
    extra = 0
    fields = (
        'metodo_pago',
        'monto_total',
        'cantidad_cuotas',
        'fecha_pago',
        'observaciones',
    )
    verbose_name = "Pago"
    verbose_name_plural = "Pagos del alumno"

    def has_add_permission(self, request, obj):
        if obj and obj.inscripciones.exists():
            return True
        return True


class CuotaInline(admin.TabularInline):
    model = Cuota
    extra = 1
    fields = (
        'numero_cuota',
        'monto',
        'fecha_vencimiento',
        'fecha_pago',
        'estado',
    )


class GrupoAlumnoFilter(admin.SimpleListFilter):
    title = 'Grupo'
    parameter_name = 'grupo'

    def lookups(self, request, model_admin):
        grupos = (
            Inscripcion.objects
            .exclude(grupo__isnull=True)
            .exclude(grupo='')
            .values_list('grupo', flat=True)
            .distinct()
            .order_by('grupo')
        )
        return [(grupo, grupo) for grupo in grupos]

    def queryset(self, request, queryset):
        if self.value():
            alumnos_ids = (
                Inscripcion.objects
                .filter(grupo=self.value())
                .values_list('alumno_id', flat=True)
            )
            return queryset.filter(id__in=alumnos_ids)
        return queryset


@admin.register(Alumno)
class AlumnoAdmin(admin.ModelAdmin):
    list_display = (
        'nombres',
        'apellidos',
        'rut',
        'estado_rut',
        'grupo_actual',
        'correo',
        'estado_correo',
    )

    search_fields = ('nombres', 'apellidos', 'rut', 'correo')
    list_filter = (GrupoAlumnoFilter, 'correo_confirmado', 'rut_confirmado')
    list_per_page = 100
    ordering = ('apellidos', 'nombres')
    inlines = [InscripcionInline, PagoInline]

    fields = (
        'nombres',
        'apellidos',
        'rut',
        'rut_confirmado',
        'direccion',
        'comuna',
        'correo',
        'telefono',
        'fecha_registro',
        'boton_enviar_codigo',
        'correo_confirmado',
        'codigo_ingresado',
        'boton_validar_codigo',
        'ficha_alumno',
    )

    readonly_fields = (
        'fecha_registro',
        'rut_confirmado',
        'correo_confirmado',
        'boton_enviar_codigo',
        'boton_validar_codigo',
        'ficha_alumno',
    )

    def estado_rut(self, obj):
        return "✅ Válido" if obj.rut_confirmado else "❌ Pendiente/Inválido"

    estado_rut.short_description = "RUT"

    def estado_correo(self, obj):
        return "✅ Confirmado" if obj.correo_confirmado else "❌ Pendiente"

    estado_correo.short_description = "Correo"

    def boton_enviar_codigo(self, obj):
        if obj.id:
            return format_html(
                '<a class="button" href="/admin/alumnos/alumno/enviar-codigo/{}/">📧 Enviar código al correo</a>',
                obj.id
            )
        return "Primero debe guardar el alumno."

    boton_enviar_codigo.short_description = "Confirmación de correo"

    def boton_validar_codigo(self, obj):
        if obj.id:
            return format_html(
                '<button type="submit" name="_validar_codigo" class="button">{}</button>',
                "✅ Validar código"
            )
        return "Primero debe guardar el alumno."

    boton_validar_codigo.short_description = "Validar correo"

    def ficha_alumno(self, obj):
        if obj.id:
            return format_html(
                '<a class="button" href="/alumno/{}/" target="_blank">🔎 Ver ficha / Generar contrato</a>',
                obj.id
            )
        return "Primero debe guardar el alumno."

    ficha_alumno.short_description = "Ficha del alumno"

    def get_urls(self):
        from django.urls import path

        urls = super().get_urls()
        custom_urls = [
            path(
                'enviar-codigo/<int:alumno_id>/',
                self.admin_site.admin_view(self.enviar_codigo),
            ),
        ]
        return custom_urls + urls

def enviar_codigo(self, request, alumno_id):
    alumno = Alumno.objects.get(id=alumno_id)

    if not alumno.correo:
        messages.error(
            request,
            "El alumno no tiene correo registrado."
        )
        return HttpResponseRedirect(
            f"/admin/alumnos/alumno/{alumno.id}/change/"
        )

    alumno.codigo_confirmacion = str(random.randint(1000, 9999))
    alumno.fecha_codigo = timezone.now()
    alumno.intentos_codigo = 0
    alumno.codigo_ingresado = None
    alumno.correo_confirmado = False
    alumno.save()

    email = EmailMessage(
        subject='Código de confirmación de correo',
        body=(
            f'Estimado/a {alumno.nombres},\n\n'
            f'Su código de confirmación es: '
            f'{alumno.codigo_confirmacion}\n\n'
            f'Este código tendrá una vigencia de 10 minutos.\n\n'
            f'OTEC Uno EIRL\n'
            f'Preocupados por tu futuro'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[alumno.correo],
    )

    try:
        email.send(fail_silently=False)

        Auditoria.objects.create(
            usuario=request.user.username,
            accion="ENVIAR CODIGO CORREO",
            modelo="Alumno",
            objeto_id=alumno.id,
            descripcion=(
                f"Se generó y envió nuevo código "
                f"a {alumno.correo}"
            )
        )

        messages.success(
            request,
            f"Código enviado correctamente a {alumno.correo}."
        )

    except Exception as e:
        messages.error(
            request,
            f"No se pudo enviar el correo: {e}"
        )

    return HttpResponseRedirect(
        f"/admin/alumnos/alumno/{alumno.id}/change/"
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        ultima_inscripcion = (
            Inscripcion.objects
            .filter(alumno=OuterRef('pk'))
            .order_by('-fecha_inicio')
        )

        return qs.annotate(
            grupo_orden=Subquery(ultima_inscripcion.values('grupo')[:1])
        )

    def grupo_actual(self, obj):
        return obj.grupo_orden or '-'

    grupo_actual.short_description = 'Grupo'
    grupo_actual.admin_order_field = 'grupo_orden'

    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(
            request,
            queryset,
            search_term
        )

        if search_term:
            alumnos_por_grupo = Inscripcion.objects.filter(
                grupo__icontains=search_term
            ).values_list('alumno_id', flat=True)

            queryset |= self.model.objects.filter(
                id__in=alumnos_por_grupo
            )

        return queryset, use_distinct

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def save_model(self, request, obj, form, change):
        rut_original = obj.rut

        if obj.rut:
            rut_limpio = obj.rut.upper().replace(".", "").replace("-", "").strip()

            if validar_rut_chileno(rut_limpio):
                obj.rut = formatear_rut(rut_limpio)
                obj.rut_confirmado = True
            else:
                obj.rut_confirmado = False
                messages.error(request, f"El RUT ingresado no es válido: {rut_original}")

                Auditoria.objects.create(
                    usuario=request.user.username,
                    accion="RUT INVALIDO",
                    modelo="Alumno",
                    objeto_id=obj.id or 0,
                    descripcion=f"RUT inválido ingresado: {rut_original}"
                )

        if "_validar_codigo" in request.POST:
            codigo_ingresado = str(obj.codigo_ingresado).strip() if obj.codigo_ingresado else ""
            codigo_real = str(obj.codigo_confirmacion).strip() if obj.codigo_confirmacion else ""

            if obj.intentos_codigo >= 3:
                messages.error(request, "Demasiados intentos. Debe enviar un nuevo código.")

                Auditoria.objects.create(
                    usuario=request.user.username,
                    accion="CODIGO BLOQUEADO",
                    modelo="Alumno",
                    objeto_id=obj.id or 0,
                    descripcion=f"Validación bloqueada por exceso de intentos para {obj.correo}"
                )

            elif not obj.fecha_codigo:
                messages.error(request, "Debe enviar primero un código al correo.")

                Auditoria.objects.create(
                    usuario=request.user.username,
                    accion="VALIDACION SIN CODIGO",
                    modelo="Alumno",
                    objeto_id=obj.id or 0,
                    descripcion=f"Intento de validación sin código enviado para {obj.correo}"
                )

            elif timezone.now() > obj.fecha_codigo + timedelta(minutes=10):
                messages.error(request, "El código expiró. Debe enviar un nuevo código.")

                Auditoria.objects.create(
                    usuario=request.user.username,
                    accion="CODIGO EXPIRADO",
                    modelo="Alumno",
                    objeto_id=obj.id or 0,
                    descripcion=f"Código expirado para {obj.correo}"
                )

            elif codigo_ingresado and codigo_ingresado == codigo_real:
                obj.correo_confirmado = True
                obj.codigo_ingresado = None
                obj.intentos_codigo = 0

                messages.success(request, "Correo confirmado correctamente ✅")

                Auditoria.objects.create(
                    usuario=request.user.username,
                    accion="CONFIRMAR CORREO",
                    modelo="Alumno",
                    objeto_id=obj.id or 0,
                    descripcion=f"Correo confirmado para {obj.correo}"
                )

            else:
                obj.intentos_codigo += 1

                messages.error(
                    request,
                    f"Código incorrecto ❌ Intento {obj.intentos_codigo} de 3."
                )

                Auditoria.objects.create(
                    usuario=request.user.username,
                    accion="ERROR CODIGO",
                    modelo="Alumno",
                    objeto_id=obj.id or 0,
                    descripcion=f"Código incorrecto para {obj.correo}. Intento {obj.intentos_codigo} de 3"
                )

        super().save_model(request, obj, form, change)

        if obj.rut_confirmado:
            Auditoria.objects.create(
                usuario=request.user.username,
                accion="RUT VALIDADO",
                modelo="Alumno",
                objeto_id=obj.id,
                descripcion=f"RUT validado correctamente: {obj.rut}"
            )

        if not change:
            Auditoria.objects.create(
                usuario=request.user.username,
                accion="CREAR ALUMNO",
                modelo="Alumno",
                objeto_id=obj.id,
                descripcion=f"Se creó el alumno {obj.nombres} {obj.apellidos}"
            )

    def response_change(self, request, obj):
        if "_validar_codigo" in request.POST:
            return HttpResponseRedirect(f"/admin/alumnos/alumno/{obj.id}/change/")
        return super().response_change(request, obj)

    def response_add(self, request, obj, post_url_continue=None):
        return HttpResponseRedirect(f"/admin/alumnos/alumno/{obj.id}/")


@admin.register(Inscripcion)
class InscripcionAdmin(admin.ModelAdmin):
    list_display = ('alumno', 'curso', 'grupo', 'fecha_inicio', 'estado')
    search_fields = (
        'alumno__nombres',
        'alumno__apellidos',
        'alumno__rut',
        'curso',
        'grupo',
    )
    list_filter = ('grupo', 'curso', 'estado', 'fecha_inicio')
    list_per_page = 100
    ordering = ('-fecha_inicio', 'grupo', 'alumno__apellidos')

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = (
        'alumno',
        'metodo_pago',
        'monto_total',
        'cantidad_cuotas',
        'fecha_pago',
        'total_cuotas',
        'saldo_pendiente',
    )

    search_fields = (
        'alumno__nombres',
        'alumno__apellidos',
        'alumno__rut',
    )

    list_filter = (
        'metodo_pago',
        'fecha_pago',
    )

    inlines = [CuotaInline]

    def total_cuotas(self, obj):
        return sum(c.monto for c in obj.cuotas.all())

    total_cuotas.short_description = "Total cuotas"

    def saldo_pendiente(self, obj):
        total_pagado = sum(
            c.monto for c in obj.cuotas.all()
            if c.estado == 'PAGADA'
        )
        return obj.monto_total - total_pagado

    saldo_pendiente.short_description = "Saldo pendiente"

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(GastoOperacional)
class GastoOperacionalAdmin(admin.ModelAdmin):
    list_display = (
        'concepto',
        'grupo',
        'monto',
        'fecha',
    )

    list_filter = (
        'grupo',
        'fecha',
    )

    search_fields = (
        'concepto',
        'grupo',
    )

    list_per_page = 100
    ordering = ('-fecha',)


@admin.register(Auditoria)
class AuditoriaAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'accion', 'modelo', 'objeto_id', 'fecha')
    search_fields = ('usuario', 'accion', 'modelo', 'descripcion')
    list_filter = ('accion', 'modelo', 'fecha')
    list_per_page = 100
    ordering = ('-fecha',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.site_header = "Sistema de Matrícula - OTEC Uno"
admin.site.site_title = "Sistema de Matrícula - OTEC Uno"
admin.site.index_title = "Panel de administración"