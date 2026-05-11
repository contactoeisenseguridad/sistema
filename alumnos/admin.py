from django.contrib import admin, messages
from django.db.models import OuterRef, Subquery, Sum
from django.utils.html import format_html
from django.http import HttpResponseRedirect
from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone
from datetime import timedelta
import random
import requests
import string

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


# --- FUNCIÓN DE INTEGRACIÓN CON MOODLE (BÚSQUEDA INTELIGENTE DEFINITIVA) ---
def enviar_a_moodle(inscripcion):
    MOODLE_URL = "https://virtual.otecuno.cl/webservice/rest/server.php"
    
    # 👇 PON TU TOKEN AQUÍ ADENTRO (Borra este texto y pega los números/letras)
    MOODLE_TOKEN = "401791078af1d393dce611bd34c9549e" 
    
    CURSOS_MOODLE = {
        'FGS': 73,  
        'CCTV': 71, 
        'SSPP': 72  
    }
    
    try:
        # 1. Identificamos el curso
        sigla_curso = None
        grupo_str = str(inscripcion.grupo).upper() if inscripcion.grupo else ""
        curso_str = str(inscripcion.curso).upper() if inscripcion.curso else ""
        
        if "FGS" in grupo_str: sigla_curso = 'FGS'
        elif "CCTV" in curso_str: sigla_curso = 'CCTV'
        elif "SSPP" in curso_str: sigla_curso = 'SSPP'
        
        if not sigla_curso or sigla_curso not in CURSOS_MOODLE:
            return False, f"No reconocí la sigla del curso en: '{curso_str}' o '{grupo_str}'"

        curso_id_moodle = CURSOS_MOODLE[sigla_curso]
        
        # 2. Limpieza extrema y REGLA DEL RUT (Sin puntos, sin guion, sin DV)
        correo_limpio = str(inscripcion.alumno.correo).strip().lower()
        nombres_limpios = str(inscripcion.alumno.nombres).strip()
        apellidos_limpios = str(inscripcion.alumno.apellidos).strip()
        rut_original = str(inscripcion.alumno.rut).strip()
        
        # Extraemos solo los números antes del guion (Ej: 12.345.678-9 -> 12345678)
        rut_solo_numeros = rut_original.split('-')[0].replace('.', '').strip()
        username = rut_solo_numeros.lower()
        password = username 
        
        # 3. BÚSQUEDA INTELIGENTE: ¿Ya existe en Moodle?
        params_buscar = {
            'wstoken': MOODLE_TOKEN,
            'wsfunction': 'core_user_get_users_by_field',
            'moodlewsrestformat': 'json',
            'field': 'username',
            'values[0]': username
        }
        busqueda = requests.post(MOODLE_URL, data=params_buscar).json()
        
        moodle_user_id = None
        
        # Si la lista tiene datos, ¡EL ALUMNO YA EXISTÍA! (Como Gisel)
        if isinstance(busqueda, list) and len(busqueda) > 0:
            moodle_user_id = busqueda[0]['id']
        else:
            # SI NO EXISTE, PROCEDEMOS A CREARLO (Solo con los datos vitales)
            params_crear = {
                'wstoken': MOODLE_TOKEN,
                'wsfunction': 'core_user_create_users',
                'moodlewsrestformat': 'json',
                'users[0][username]': username,
                'users[0][password]': password,
                'users[0][firstname]': nombres_limpios,
                'users[0][lastname]': apellidos_limpios,
                'users[0][email]': correo_limpio,
                'users[0][idnumber]': rut_original, 
            }
            
            creacion = requests.post(MOODLE_URL, data=params_crear).json()
            
            if isinstance(creacion, dict) and 'exception' in creacion:
                mensaje = creacion.get('message', '')
                return False, f"🔴 Falló la creación en Moodle | Detalle: {mensaje} | Revisa si el correo ya lo usa otro alumno."
            
            # Volvemos a buscar para obtener su ID interno
            busqueda_nueva = requests.post(MOODLE_URL, data=params_buscar).json()
            if isinstance(busqueda_nueva, list) and len(busqueda_nueva) > 0:
                moodle_user_id = busqueda_nueva[0]['id']
            else:
                return False, "Se creó el alumno, pero Moodle no me devuelve su ID interno."
        
        # 4. MATRICULAR AL ALUMNO EN EL CURSO (Funciona para nuevos y antiguos)
        params_matricular = {
            'wstoken': MOODLE_TOKEN,
            'wsfunction': 'enrol_manual_enrol_users',
            'moodlewsrestformat': 'json',
            'enrolments[0][roleid]': 5, 
            'enrolments[0][userid]': moodle_user_id,
            'enrolments[0][courseid]': curso_id_moodle
        }
        matricula = requests.post(MOODLE_URL, data=params_matricular).json()
        
        if isinstance(matricula, dict) and 'exception' in matricula:
            return False, f"Error al matricular en el curso de Moodle: {matricula.get('message')}"
            
    except Exception as error_general:
        return False, f"El código de integración falló: {str(error_general)}"
        
    # 5. ENVIAR CORREO DE BIENVENIDA AL AULA
    try:
        cuerpo_bienvenida = f"""Estimad@ {nombres_limpios}:

Junto con saludar, le informamos que ha sido exitosamente incorporad@ al curso que ha contratado, el cual ya ha sido debidamente informado a la Subsecretaría de Prevención del Delito (SPD).

Le recordamos que solo los módulos de Primeros Auxilios, Correcto Uso de Elementos Defensivos y Técnicas de Reducción se desarrollarán de manera presencial. El resto de las actividades se realizará conforme a la modalidad informada.

Asimismo, le informamos que su acceso a nuestra plataforma virtual ya se encuentra habilitado en:
http://virtual.otecuno.cl

Su nombre de usuario y contraseña corresponden a los datos que fueron informados al momento de su matrícula (su número de RUN sin puntos).

Ejemplo:  
RUN: 12.345.678-9
Usuario: 12345678
Contraseña: 12345678

Ante cualquier duda o dificultad de acceso, puede comunicarse con nosotros a través de nuestros canales oficiales.

Saludos cordiales,  
UNO OTEC
contacto@otecuno.cl"""

        correo_bienvenida = EmailMessage(
            subject='Acceso a Plataforma Virtual - OTEC Uno',
            body=cuerpo_bienvenida,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[correo_limpio],
        )
        correo_bienvenida.send(fail_silently=False)
        
    except Exception as error_correo:
        return False, f"Matriculado con éxito en Moodle, pero falló el envío del correo: {str(error_correo)}"
        
    return True, "Matriculado con éxito en Moodle y correo enviado."

# --- Funciones de Utilidad ---

def formato_clp(valor):
    """Convierte un número a formato peso chileno Ej: $ 130.000.-"""
    if valor is None:
        return "$ 0.-"
    return f"$ {valor:,.0f}.-".replace(",", ".")

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


# --- Inlines ---

class InscripcionInline(admin.TabularInline):
    model = Inscripcion
    extra = 1

class PagoInline(admin.TabularInline):
    model = Pago
    extra = 0
    # 👇 MODIFICADO: Se restauró 'inscripcion' a los campos
    fields = ('inscripcion', 'metodo_pago', 'monto_total', 'cantidad_cuotas', 'fecha_pago', 'enlace_detalle')
    readonly_fields = ('enlace_detalle',)
    verbose_name = "Pago"
    verbose_name_plural = "Pagos del alumno"

    def enlace_detalle(self, obj):
        if obj.pk:
            return format_html(
                '<a class="button" href="/admin/alumnos/pago/{}/change/" target="_blank">💸 Administrar Cuotas</a>', 
                obj.pk
            )
        return "Guarde el alumno para generar pagos"
    enlace_detalle.short_description = "Acción"

class CuotaInline(admin.TabularInline):
    model = Cuota
    extra = 0  # Sin filas vacías por defecto
    fields = ('numero_cuota', 'monto', 'fecha_vencimiento', 'fecha_pago', 'estado')

    # 🔒 SEGURIDAD: Bloquear edición para operadores si el pago ya existe
    def get_readonly_fields(self, request, obj=None):
        # Si NO es superusuario, bloqueamos monto y fechas. Solo pueden cambiar el Estado.
        if not request.user.is_superuser and obj:
            return ('numero_cuota', 'monto', 'fecha_vencimiento', 'fecha_pago')
        return super().get_readonly_fields(request, obj)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


class GrupoAlumnoFilter(admin.SimpleListFilter):
    title = 'Grupo'
    parameter_name = 'grupo'

    def lookups(self, request, model_admin):
        grupos = (
            Inscripcion.objects.exclude(grupo__isnull=True)
            .exclude(grupo='')
            .values_list('grupo', flat=True)
            .distinct()
            .order_by('grupo')
        )
        return [(grupo, grupo) for grupo in grupos]

    def queryset(self, request, queryset):
        if self.value():
            alumnos_ids = Inscripcion.objects.filter(
                grupo=self.value()
            ).values_list('alumno_id', flat=True)
            return queryset.filter(id__in=alumnos_ids)
        return queryset


# --- Admins ---

@admin.register(Alumno)
class AlumnoAdmin(admin.ModelAdmin):
    list_display = (
        'apellidos', 'nombres', 'rut', 'estado_rut', 'grupo_actual', 'estado_correo'
    )
    search_fields = ('nombres', 'apellidos', 'rut', 'correo')
    list_filter = (GrupoAlumnoFilter, 'correo_confirmado', 'rut_confirmado')
    list_per_page = 100
    ordering = ('apellidos', 'nombres') # 🔤 Orden Alfabético PDF
    
    inlines = [InscripcionInline, PagoInline]
    
    fields = (
        'nombres', 'apellidos', 'rut', 'rut_confirmado', 'direccion', 'comuna', 
        'correo', 'telefono', 'fecha_registro', 'boton_enviar_codigo', 
        'correo_confirmado', 'codigo_ingresado', 'boton_validar_codigo', 'ficha_alumno'
    )
    readonly_fields = (
        'fecha_registro', 'rut_confirmado', 'correo_confirmado', 
        'boton_enviar_codigo', 'boton_validar_codigo', 'ficha_alumno'
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
            path('enviar-codigo/<int:alumno_id>/', self.admin_site.admin_view(self.enviar_codigo))
        ]
        return custom_urls + urls

    def enviar_codigo(self, request, alumno_id):
        alumno = Alumno.objects.get(id=alumno_id)
        if not alumno.correo:
            messages.error(request, "El alumno no tiene correo registrado.")
            return HttpResponseRedirect(f"/admin/alumnos/alumno/{alumno.id}/change/")
            
        alumno.codigo_confirmacion = str(random.randint(1000, 9999))
        alumno.fecha_codigo = timezone.now()
        alumno.intentos_codigo = 0
        alumno.codigo_ingresado = None
        alumno.correo_confirmado = False
        alumno.save()
        
        email = EmailMessage(
            subject='Código de confirmación de correo',
            body=(f'Estimado/a {alumno.nombres},\n\n'
                  f'Su código de confirmación es: {alumno.codigo_confirmacion}\n\n'
                  f'Este código tendrá una vigencia de 10 minutos.\n\n'
                  f'OTEC Uno EIRL\nPreocupados por tu futuro'),
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
                descripcion=f"Se generó y envió nuevo código a {alumno.correo}"
            )
            messages.success(request, f"Código enviado correctamente a {alumno.correo}.")
        except Exception as e:
            messages.error(request, f"No se pudo enviar el correo: {e}")
            
        return HttpResponseRedirect(f"/admin/alumnos/alumno/{alumno.id}/change/")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        ultima_inscripcion = Inscripcion.objects.filter(alumno=OuterRef('pk')).order_by('-fecha_inicio')
        return qs.annotate(grupo_orden=Subquery(ultima_inscripcion.values('grupo')[:1]))

    def grupo_actual(self, obj): 
        return obj.grupo_orden or '-'
    grupo_actual.short_description = 'Grupo'
    grupo_actual.admin_order_field = 'grupo_orden'

    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        if search_term:
            alumnos_por_grupo = Inscripcion.objects.filter(
                grupo__icontains=search_term
            ).values_list('alumno_id', flat=True)
            queryset |= self.model.objects.filter(id__in=alumnos_por_grupo)
        return queryset, use_distinct

    def has_change_permission(self, request, obj=None): 
        return super().has_change_permission(request, obj)
        
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
            elif not obj.fecha_codigo: 
                messages.error(request, "Debe enviar primero un código al correo.")
            elif timezone.now() > (obj.fecha_codigo + timedelta(minutes=10)): 
                messages.error(request, "El código expiró. Debe enviar un nuevo código.")
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
                messages.error(request, f"Código incorrecto ❌ Intento {obj.intentos_codigo} de 3.")
                
        super().save_model(request, obj, form,