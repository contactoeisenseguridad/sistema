from django.contrib import admin
from .models import Alumno, Inscripcion, Auditoria


class InscripcionInline(admin.TabularInline):
    model = Inscripcion
    extra = 1


@admin.register(Alumno)
class AlumnoAdmin(admin.ModelAdmin):
    list_display = ('nombres', 'apellidos', 'rut', 'correo')
    search_fields = ('nombres', 'apellidos', 'rut')
    inlines = [InscripcionInline]

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
    search_fields = ('alumno__nombres', 'alumno__apellidos', 'curso', 'grupo')

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

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# 🔵 PERSONALIZACIÓN DEL ADMIN
admin.site.site_header = "Sistema de Matrícula"
admin.site.site_title = "Sistema de Matrícula"
admin.site.index_title = "Panel de administración"