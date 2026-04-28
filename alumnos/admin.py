from django.contrib import admin
from .models import Alumno, Inscripcion, Auditoria, Aviso


admin.site.register(Aviso)


class InscripcionInline(admin.TabularInline):
    model = Inscripcion
    extra = 1


@admin.register(Alumno)
class AlumnoAdmin(admin.ModelAdmin):
    list_display = ('nombres', 'apellidos', 'rut', 'grupo_actual', 'correo')
    search_fields = ('nombres', 'apellidos', 'rut', 'correo')
    list_filter = ('inscripcion__grupo',)
    list_per_page = 100
    ordering = ('apellidos', 'nombres')
    inlines = [InscripcionInline]

    def grupo_actual(self, obj):
        inscripcion = obj.inscripcion_set.order_by('-fecha_inicio').first()
        if inscripcion:
            return inscripcion.grupo
        return '-'

    grupo_actual.short_description = 'Grupo'
    grupo_actual.admin_order_field = 'inscripcion__grupo'

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        return False

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        return False

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        if not change:
            Auditoria.objects.create(
                usuario=request.user.username,
                accion="CREAR ALUMNO",
                modelo="Alumno",
                objeto_id=obj.id,
                descripcion=f"Se creó el alumno {obj.nombres} {obj.apellidos}, RUT {obj.rut}"
            )


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
        if request.user.is_superuser:
            return True
        return False

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        return False

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        if not change:
            Auditoria.objects.create(
                usuario=request.user.username,
                accion="CREAR INSCRIPCION",
                modelo="Inscripcion",
                objeto_id=obj.id,
                descripcion=f"Se creó inscripción para {obj.alumno.nombres} {obj.alumno.apellidos}, curso {obj.curso}, grupo {obj.grupo}"
            )


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


# 🔵 PERSONALIZACIÓN DEL ADMIN
admin.site.site_header = "Sistema de Matrícula - OTEC Uno"
admin.site.site_title = "Sistema de Matrícula - OTEC Uno"
admin.site.index_title = "Panel de administración"