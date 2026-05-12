import os
import random
import string
import openpyxl # 👈 LIBRERÍA NUEVA PARA LEER EXCEL
from datetime import timedelta

from django.contrib import admin, messages
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.core.mail import EmailMessage
from django.db.models import OuterRef, Subquery, Sum
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.utils import timezone
from django.utils.html import format_html
from django.conf import settings

from .models import (
    Alumno, Inscripcion, Auditoria, Aviso, Pago, Cuota, GastoOperacional,
    PerfilUsuario, Modulo, SesionClase, Asistencia, PlanillaSPD
)

# ==========================================
# 1. INTEGRACIÓN MOODLE Y FUNCIONES ÚTILES
# ==========================================

def enviar_a_moodle(inscripcion):
    MOODLE_URL = "https://virtual.otecuno.cl/webservice/rest/server.php"
    MOODLE_TOKEN = "401791078af1d393dce611bd34c9549e" 
    
    CURSOS_MOODLE = {'FGS': 73, 'CCTV': 71, 'SSPP': 72}
    
    try:
        sigla_curso = None
        grupo_str = str(inscripcion.grupo).upper() if inscripcion.grupo else ""
        curso_str = str(inscripcion.curso).upper() if inscripcion.curso else ""
        
        if "FGS" in grupo_str: sigla_curso = 'FGS'
        elif "CCTV" in curso_str: sigla_curso = 'CCTV'
        elif "SSPP" in curso_str: sigla_curso = 'SSPP'
        
        if not sigla_curso or sigla_curso not in CURSOS_MOODLE:
            return False, f"No reconocí la sigla del curso en: '{curso_str}' o '{grupo_str}'"

        curso_id_moodle = CURSOS_MOODLE[sigla_curso]
        
        correo_limpio = str(inscripcion.alumno.correo).strip().lower()
        nombres_limpios = str(inscripcion.alumno.nombres).strip()
        apellidos_limpios = str(inscripcion.alumno.apellidos).strip()
        rut_original = str(inscripcion.alumno.rut).strip()
        
        rut_solo_numeros = rut_original.split('-')[0].replace('.', '').strip()
        username = rut_solo_numeros.lower()
        password = username 
        
        params_buscar = {
            'wstoken': MOODLE_TOKEN, 'wsfunction': 'core_user_get_users_by_field',
            'moodlewsrestformat': 'json', 'field': 'username', 'values[0]': username
        }
        busqueda = requests.post(MOODLE_URL, data=params_buscar).json()
        
        moodle_user_id = None
        if isinstance(busqueda, list) and len(busqueda) > 0:
            moodle_user_id = busqueda[0]['id']
        else:
            params_crear = {
                'wstoken': MOODLE_TOKEN, 'wsfunction': 'core_user_create_users',
                'moodlewsrestformat': 'json', 'users[0][username]': username,
                'users[0][password]': password, 'users[0][firstname]': nombres_limpios,
                'users[0][lastname]': apellidos_limpios, 'users[0][email]': correo_limpio,
                'users[0][idnumber]': rut_original, 
            }
            creacion = requests.post(MOODLE_URL, data=params_crear).json()
            if isinstance(creacion, dict) and 'exception' in creacion:
                return False, f"🔴 Falló la creación en Moodle | Detalle: {creacion.get('message', '')}"
            if isinstance(creacion, list) and len(creacion) > 0 and 'id' in creacion[0]:
                moodle_user_id = creacion[0]['id']
            else:
                return False, "No se obtuvo ID al crear usuario."
        
        params_matricular = {
            'wstoken': MOODLE_TOKEN, 'wsfunction': 'enrol_manual_enrol_users',
            'moodlewsrestformat': 'json', 'enrolments[0][roleid]': 5, 
            'enrolments[0][userid]': moodle_user_id, 'enrolments[0][courseid]': curso_id_moodle
        }
        matricula = requests.post(MOODLE_URL, data=params_matricular).json()
        if isinstance(matricula, dict) and 'exception' in matricula:
            return False, f"Error al matricular: {matricula.get('message')}"
            
    except Exception as error_general:
        return False, f"Falló: {str(error_general)}"
        
    try:
        cuerpo_bienvenida = f"Estimad@ {nombres_limpios}:\n\nSu acceso a la plataforma virtual (http://virtual.otecuno.cl) ha sido habilitado.\nUsuario y Contraseña: Su RUN sin puntos (Ej: 12345678-9).\n\nSaludos,\nOTEC UNO"
        correo_bienvenida = EmailMessage(
            subject='Acceso a Plataforma Virtual - OTEC Uno', body=cuerpo_bienvenida,
            from_email=settings.DEFAULT_FROM_EMAIL, to=[correo_limpio],
        )
        ruta_pdf = os.path.join(settings.BASE_DIR, 'manual_aula_virtual.pdf')
        if os.path.exists(ruta_pdf):
            correo_bienvenida.attach_file(ruta_pdf)
        correo_bienvenida.send(fail_silently=False)
    except Exception as error_correo:
        return False, "Matriculado en Moodle, pero falló el correo."
        
    return True, "Matriculado con éxito en Moodle y correo enviado."

def formato_clp(valor): return f"$ {valor:,.0f}.-".replace(",", ".") if valor else "$ 0.-"

def validar_rut_chileno(rut):
    rut = rut.upper().replace(".", "").replace("-", "").strip()
    if len(rut) < 2 or not rut[:-1].isdigit(): return False
    suma, multiplo = 0, 2
    for numero in reversed(rut[:-1]):
        suma += int(numero) * multiplo
        multiplo = 2 if multiplo == 7 else multiplo + 1
    dv_calculado = 11 - (suma % 11)
    dv_calculado = "0" if dv_calculado == 11 else "K" if dv_calculado == 10 else str(dv_calculado)
    return rut[-1] == dv_calculado

def formatear_rut(rut):
    rut = rut.upper().replace(".", "").replace("-", "").strip()
    return f"{rut[:-1]}-{rut[-1]}"


# ==========================================
# 2. INLINES Y PANELES BÁSICOS
# ==========================================

class InscripcionInline(admin.TabularInline):
    model = Inscripcion
    extra = 1

class PagoInline(admin.TabularInline):
    model = Pago
    extra = 0
    fields = ('inscripcion', 'metodo_pago', 'monto_total', 'cantidad_cuotas', 'fecha_pago', 'enlace_detalle')
    readonly_fields = ('enlace_detalle',)
    
    def enlace_detalle(self, obj):
        if obj.pk: return format_html('<a class="button" href="/admin/alumnos/pago/{}/change/" target="_blank">💸 Administrar Cuotas</a>', obj.pk)
        return "Guarde el alumno para generar pagos"

class CuotaInline(admin.TabularInline):
    model = Cuota
    extra = 0
    fields = ('numero_cuota', 'monto', 'fecha_vencimiento', 'fecha_pago', 'estado')
    def get_readonly_fields(self, request, obj=None):
        if not request.user.is_superuser and obj: return ('numero_cuota', 'monto', 'fecha_vencimiento', 'fecha_pago')
        return super().get_readonly_fields(request, obj)
    def has_delete_permission(self, request, obj=None): return request.user.is_superuser


# ==========================================
# 3. PANELES DE ADMINISTRACIÓN (ADMINS)
# ==========================================

admin.site.register(Aviso)

@admin.register(Alumno)
class AlumnoAdmin(admin.ModelAdmin):
    list_display = ('apellidos', 'nombres', 'rut', 'estado_rut', 'estado_correo')
    search_fields = ('nombres', 'apellidos', 'rut', 'correo')
    list_filter = ('correo_confirmado', 'rut_confirmado')
    ordering = ('apellidos', 'nombres')
    inlines = [InscripcionInline, PagoInline]
    
    def estado_rut(self, obj): return "✅ Válido" if obj.rut_confirmado else "❌ Pendiente"
    def estado_correo(self, obj): return "✅ Confirmado" if obj.correo_confirmado else "❌ Pendiente"

    def save_model(self, request, obj, form, change):
        if obj.rut:
            rut_limpio = obj.rut.upper().replace(".", "").replace("-", "").strip()
            if validar_rut_chileno(rut_limpio):
                obj.rut = formatear_rut(rut_limpio)
                obj.rut_confirmado = True
            else:
                obj.rut_confirmado = False
                messages.error(request, f"RUT Inválido: {obj.rut}")
        super().save_model(request, obj, form, change)


@admin.register(Inscripcion)
class InscripcionAdmin(admin.ModelAdmin):
    list_display = ('alumno', 'curso', 'grupo', 'fecha_inicio', 'estado')
    search_fields = ('alumno__nombres', 'alumno__apellidos', 'alumno__rut', 'grupo')
    list_filter = ('grupo', 'curso')
    actions = ['matricular_masivamente_moodle']

    def matricular_masivamente_moodle(self, request, queryset):
        exitos, errores = 0, 0
        for i in queryset:
            if not i.alumno.correo:
                messages.error(request, f"❌ {i.alumno} no tiene correo.")
                continue
            exito, msj = enviar_a_moodle(i)
            if exito: exitos += 1
            else: messages.error(request, f"❌ Error en {i.alumno}: {msj}")
        if exitos > 0: messages.success(request, f"✅ {exitos} alumnos matriculados.")
    matricular_masivamente_moodle.short_description = "🎓 Matricular seleccionados en Moodle"


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = ('alumno', 'metodo_pago', 'monto_total', 'cantidad_cuotas', 'fecha_pago')
    search_fields = ('alumno__nombres', 'alumno__apellidos', 'alumno__rut')
    list_filter = ('metodo_pago', 'fecha_pago')
    inlines = [CuotaInline]


@admin.register(Cuota)
class CuotaAdmin(admin.ModelAdmin):
    list_display = ('pago', 'numero_cuota', 'monto', 'fecha_vencimiento', 'estado')
    list_filter = ('estado', 'fecha_vencimiento')


# ==========================================
# 4. NUEVOS PANELES: PROGRAMACIÓN Y EXCEL
# ==========================================

@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ('user', 'rut', 'rol', 'bloqueado', 'intentos_fallidos')
    list_filter = ('rol', 'bloqueado')
    search_fields = ('user__username', 'user__first_name')
    actions = ['desbloquear_usuarios']

    def desbloquear_usuarios(self, request, queryset):
        queryset.update(bloqueado=False, intentos_fallidos=0)
        messages.success(request, "✅ Usuarios desbloqueados exitosamente.")
    desbloquear_usuarios.short_description = "🔓 Desbloquear Relatores seleccionados"


@admin.register(Modulo)
class ModuloAdmin(admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)


@admin.register(SesionClase)
class SesionClaseAdmin(admin.ModelAdmin):
    # 👇 ESTA ES LA VISTA DE PROGRAMACIÓN (Calendario visual)
    date_hierarchy = 'fecha' 
    list_display = ('fecha', 'ver_horario', 'modulo', 'ver_relator', 'grupo', 'modalidad')
    list_filter = ('modalidad', 'relator', 'grupo')
    search_fields = ('grupo', 'modulo__nombre', 'relator__first_name', 'relator__last_name')
    ordering = ('-fecha', 'bloque_horario')

    def ver_horario(self, obj):
        return format_html('<b>{}</b>', obj.bloque_horario)
    ver_horario.short_description = "Horario"

    def ver_relator(self, obj):
        if obj.relator:
            return f"{obj.relator.first_name} {obj.relator.last_name}"
        return format_html('<span style="color: red;">⚠️ Sin Asignar</span>')
    ver_relator.short_description = "Relator"


@admin.register(Asistencia)
class AsistenciaAdmin(admin.ModelAdmin):
    list_display = ('alumno', 'sesion', 'presente')
    list_filter = ('presente', 'sesion__grupo', 'sesion__fecha')
    search_fields = ('alumno__rut', 'alumno__apellidos', 'sesion__modulo__nombre')

    def get_readonly_fields(self, request, obj=None):
        # 👇 SI ES SUPERUSUARIO, TIENE ACCESO TOTAL SIEMPRE
        if request.user.is_superuser:
            return []  # Este espacio es el que faltaba
    
        # Si no es superusuario, verificamos si tiene perfil de fiscalizador
        try:
            if request.user.perfilusuario.rol == 'FISCALIZADOR':
                return [f.name for f in self.model._meta.fields]
        except:
            pass
        
        return super().get_readonly_fields(request, obj)

def procesar_excel_spd(self, request, queryset):
        exitos = 0
        for planilla in queryset:
            try:
                wb = openpyxl.load_workbook(planilla.archivo_excel.path, data_only=True)
                
                # 1. Asegurar Módulos (Pestaña CONTENIDOS DEL CURSO)
                if "CONTENIDOS DEL CURSO" in wb.sheetnames:
                    ws_mod = wb["CONTENIDOS DEL CURSO"]
                    for row in ws_mod.iter_rows(min_row=2, values_only=True):
                        if row[0]: Modulo.objects.get_or_create(nombre=str(row[0]).strip())

                # 2. Leer Clases (Pestaña Hoja1)
                if "Hoja1" in wb.sheetnames:
                    ws = wb["Hoja1"]
                    start_row = 1
                    col_fecha, col_hora, col_mod, col_tipo = None, None, None, None

                    # BUSCADOR DE CABECERAS (Detecta dónde empieza la tabla de la SPD)
                    for r in range(1, 20): # Busca en las primeras 20 filas
                        row_vals = [str(ws.cell(row=r, column=c).value).upper() if ws.cell(row=r, column=c).value else "" for c in range(1, 10)]
                        if "FECHA" in row_vals or "MODULO" in row_vals:
                            start_row = r + 1
                            for idx, val in enumerate(row_vals):
                                if "FECHA" in val: col_fecha = idx + 1
                                if "HORA" in val or "HORARIO" in val: col_hora = idx + 1
                                if "MODULO" in val: col_mod = idx + 1
                                if "MODALIDAD" in val: col_tipo = idx + 1
                            break

                    if col_fecha and col_mod:
                        # Borrar sesiones previas de este grupo para evitar duplicados si re-procesas
                        SesionClase.objects.filter(grupo=planilla.grupo).delete()
                        
                        for r in range(start_row, ws.max_row + 1):
                            f_val = ws.cell(row=r, column=col_fecha).value
                            if not f_val: continue # Si no hay fecha, saltar fila
                            
                            m_nombre = str(ws.cell(row=r, column=col_mod).value).strip()
                            h_val = str(ws.cell(row=r, column=col_hora).value).strip()
                            t_val = str(ws.cell(row=r, column=col_tipo).value).upper() if col_tipo else ""

                            mod_obj, _ = Modulo.objects.get_or_create(nombre=m_nombre)
                            
                            SesionClase.objects.create(
                                grupo=planilla.grupo,
                                fecha=f_val,
                                bloque_horario=h_val,
                                modulo=mod_obj,
                                modalidad='PRESENCIAL' if 'PRESENCIAL' in t_val or 'TERRENO' in t_val else 'ONLINE'
                            )
                            exitos += 1

                planilla.procesado = True
                planilla.save()
                
            except Exception as e:
                messages.error(request, f"Error en {planilla.grupo}: {str(e)}")

        if exitos > 0:
            messages.success(request, f"¡Magia! Se crearon {exitos} clases para el grupo {planilla.grupo}.")
        else:
            messages.warning(request, "El archivo se leyó pero no se encontraron clases. Revisa que la pestaña se llame 'Hoja1'.")
    
    procesar_excel_spd.short_description = "📥 Leer Excel y Generar Calendario de Clases"

@admin.register(PlanillaSPD)
class PlanillaSPDAdmin(admin.ModelAdmin):
    list_display = ('grupo', 'fecha_subida', 'procesado')
    actions = ['procesar_excel_spd_action']

    def procesar_excel_spd_action(self, request, queryset):
        exitos = 0
        for planilla in queryset:
            try:
                # Abrimos el Excel usando la librería openpyxl
                wb = openpyxl.load_workbook(planilla.archivo_excel.path, data_only=True)
                
                # 1. Asegurar que existan los Módulos (Pestaña CONTENIDOS DEL CURSO)
                if "CONTENIDOS DEL CURSO" in wb.sheetnames:
                    ws_mod = wb["CONTENIDOS DEL CURSO"]
                    for row in ws_mod.iter_rows(min_row=2, values_only=True):
                        if row[0]: 
                            Modulo.objects.get_or_create(nombre=str(row[0]).strip())

                # 2. Leer Clases (Pestaña Hoja1 - Formato oficial SPD)
                if "Hoja1" in wb.sheetnames:
                    ws = wb["Hoja1"]
                    start_row = 1
                    col_fecha, col_hora, col_mod, col_tipo = None, None, None, None

                    # BUSCADOR DE CABECERAS: Rastrea las primeras 20 filas para hallar dónde empieza la tabla
                    for r in range(1, 20):
                        row_vals = [str(ws.cell(row=r, column=c).value).upper() if ws.cell(row=r, column=c).value else "" for c in range(1, 10)]
                        if "FECHA" in row_vals or "MODULO" in row_vals:
                            start_row = r + 1
                            for idx, val in enumerate(row_vals):
                                if "FECHA" in val: col_fecha = idx + 1
                                if "HORA" in val or "HORARIO" in val: col_hora = idx + 1
                                if "MODULO" in val: col_mod = idx + 1
                                if "MODALIDAD" in val: col_tipo = idx + 1
                            break

                    if col_fecha and col_mod:
                        # Limpiamos sesiones previas de este grupo para evitar duplicados al re-procesar
                        SesionClase.objects.filter(grupo=planilla.grupo).delete()
                        
                        for r in range(start_row, ws.max_row + 1):
                            f_val = ws.cell(row=r, column=col_fecha).value
                            if not f_val: continue # Si no hay fecha, saltamos la fila
                            
                            m_nombre = str(ws.cell(row=r, column=col_mod).value).strip()
                            h_val = str(ws.cell(row=r, column=col_hora).value).strip() if col_hora else "Sin Horario"
                            t_val = str(ws.cell(row=r, column=col_tipo).value).upper() if col_tipo else ""

                            # Vincular con el modelo Modulo
                            mod_obj, _ = Modulo.objects.get_or_create(nombre=m_nombre)
                            
                            # Crear la sesión en el calendario
                            SesionClase.objects.create(
                                grupo=planilla.grupo,
                                fecha=f_val,
                                bloque_horario=h_val,
                                modulo=mod_obj,
                                modalidad='PRESENCIAL' if 'PRESENCIAL' in t_val or 'TERRENO' in t_val else 'ONLINE'
                            )
                            exitos += 1

                planilla.procesado = True
                planilla.save()
                
            except Exception as e:
                messages.error(request, f"Error procesando el grupo {planilla.grupo}: {str(e)}")

        if exitos > 0:
            messages.success(request, f"✅ ¡Listo! Se crearon {exitos} sesiones de clase para el grupo {planilla.grupo}.")
        else:
            messages.warning(request, "Se leyó el archivo pero no se detectaron filas con el formato de la SPD. Revisa las pestañas.")

    procesar_excel_spd_action.short_description = "📥 Leer Excel y Generar Calendario de Clases"


# ==========================================
# 5. VISTA DEL RELATOR (ASISTENCIA)
# ==========================================
# Nota: Esta función debe ser enlazada en tu archivo urls.py principal
# Ejemplo: path('portal-relator/', views.vista_pasar_asistencia, name='portal_relator')

def vista_pasar_asistencia(request):
    if 'relator_auth' not in request.session:
        if request.method == "POST" and "auth_relator" in request.POST:
            user_input = request.POST.get('usuario')
            pass_input = request.POST.get('clave')
            try:
                perfil = PerfilUsuario.objects.get(user__username=user_input, rol='RELATOR')
                if perfil.bloqueado:
                    return render(request, 'error_asistencia.html', {'error': 'USUARIO BLOQUEADO. Contacte al Superusuario.'})

                user = authenticate(username=user_input, password=pass_input)
                if user is not None:
                    perfil.intentos_fallidos = 0
                    perfil.save()
                    request.session['relator_auth'] = user.id
                else:
                    perfil.intentos_fallidos += 1
                    if perfil.intentos_fallidos >= 2: perfil.bloqueado = True
                    perfil.save()
                    return render(request, 'login_relator.html', {'error': f'Clave incorrecta. Intento {perfil.intentos_fallidos} de 2.'})
            except PerfilUsuario.DoesNotExist:
                return render(request, 'login_relator.html', {'error': 'Usuario no autorizado como Relator.'})

    if request.method == "POST" and "seleccionar_grupo" in request.POST:
        grupo_id = request.POST.get('grupo')
        modulo_id = request.POST.get('modulo')
        alumnos = Alumno.objects.filter(inscripcion__grupo=grupo_id)
        return render(request, 'lista_asistencia.html', {'alumnos': alumnos, 'grupo': grupo_id, 'modulo': modulo_id})

    if request.method == "POST" and "enviar_asistencia" in request.POST:
        grupo_id = request.POST.get('grupo')
        modulo_id = request.POST.get('modulo')
        alumnos_presentes_ids = request.POST.getlist('alumnos_presentes')
        
        # OBTENEMOS LA SESIÓN CORRECTA DEL CALENDARIO
        sesion = SesionClase.objects.filter(grupo=grupo_id, modulo_id=modulo_id, fecha=timezone.now().date()).first()
        
        if not sesion:
            return render(request, 'error_asistencia.html', {'error': 'No hay clases programadas para este grupo y módulo el día de hoy.'})

        for alumno in Alumno.objects.filter(inscripcion__grupo=grupo_id):
            es_presente = str(alumno.id) in alumnos_presentes_ids
            Asistencia.objects.update_or_create(alumno=alumno, sesion=sesion, defaults={'presente': es_presente})
            
            if es_presente:
                email = EmailMessage(
                    subject=f'Asistencia Registrada - {sesion.modulo.nombre}',
                    body=f'Estimado {alumno.nombres},\n\nSu asistencia ha sido registrada exitosamente para el módulo "{sesion.modulo.nombre}" el día {sesion.fecha}.\n\nSaludos,\nOTEC UNO',
                    from_email=settings.DEFAULT_FROM_EMAIL, to=[alumno.correo],
                )
                email.send(fail_silently=True)

        return render(request, 'exito_asistencia.html')

    return render(request, 'login_relator.html')

# ==========================================
# CONFIGURACIÓN VISUAL DEL PANEL
# ==========================================
admin.site.site_header = "Sistema Operativo - OTEC Uno"
admin.site.site_title = "Administración - OTEC Uno"
admin.site.index_title = "Panel de Control General"