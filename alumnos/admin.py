from django.contrib import admin
from .models import Alumno, Inscripcion, Auditoria, Aviso


admin.site.register(Aviso)


class InscripcionInline(admin.TabularInline):
    model = Inscripcion
    extra = 1


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
    list_display = ('nombres', 'apellidos', 'rut', 'grupo_actual', 'correo')
    search_fields = ('nombres', 'apellidos', 'rut', 'correo')
    list_filter = (GrupoAlumnoFilter,)
    list_per_page = 100
    ordering = ('apellidos', 'nombres')
    inlines = [InscripcionInline]

    def grupo_actual(self, obj):
        inscripcion = (
            Inscripcion.objects
            .filter(alumno=obj)
            .order_by('-fecha_inicio')
            .first()
        )
        if inscripcion:
            return inscripcion.grupo
        return '-'

    grupo_actual.short_description = 'Grupo'

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