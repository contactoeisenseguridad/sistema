from django.contrib import admin
from django.db.models import OuterRef, Subquery
from django.utils.html import format_html
from django.http import HttpResponseRedirect
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

    # 🔥 BOTÓN FICHA
    readonly_fields = ('ficha_alumno',)

    def ficha_alumno(self, obj):
        if obj.id:
            return format_html(
                '<a class="button" href="/alumno/{}/" target="_blank">🔎 Ver ficha / Generar contrato</a>',
                obj.id
            )
        return "Primero debe guardar el alumno."

    ficha_alumno.short_description = "Ficha del alumno"

    # 🔵 QUERY OPTIMIZADA (tu código intacto)
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

    # 🔍 BÚSQUEDA POR GRUPO (tu código intacto)
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

    # 🔒 PERMISOS
    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    # 🧾 AUDITORÍA + 🔥 REDIRECCIÓN AUTOMÁTICA
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

    # 🔥 REDIRECCIÓN AUTOMÁTICA DESPUÉS DE CREAR
    def response_add(self, request, obj, post_url_continue=None):
        return HttpResponseRedirect(f"/alumno/{obj.id}/")


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