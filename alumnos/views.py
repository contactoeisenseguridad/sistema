from datetime import datetime
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone

import openpyxl

# Importación de todos tus modelos
from .models import (
    Alumno, Inscripcion, Auditoria, Aviso, 
    PerfilUsuario, Modulo, SesionClase, Asistencia
)

def limpiar(valor):
    if valor is None:
        return ''
    return str(valor).strip()

# ==========================================
# 🔵 FUNCIONES ORIGINALES (MANTENIDAS)
# ==========================================

@login_required
def inicio(request):
    aviso = Aviso.objects.last()
    return render(request, 'inicio.html', {'aviso': aviso})

@login_required
@permission_required('alumnos.view_alumno', raise_exception=True)
def buscar_alumno(request):
    query = request.GET.get('q')
    alumnos = []
    if query:
        alumnos = Alumno.objects.filter(
            apellidos__icontains=query
        ) | Alumno.objects.filter(
            rut__icontains=query
        ) | Alumno.objects.filter(
            nombres__icontains=query
        ) | Alumno.objects.filter(
            inscripciones__grupo__icontains=query
        )
        alumnos = alumnos.distinct()

        Auditoria.objects.create(
            usuario=request.user.username,
            accion="BUSCAR",
            modelo="Alumno",
            objeto_id=0,
            descripcion=f"Búsqueda realizada con término: {query}"
        )
    return render(request, 'buscar.html', {'alumnos': alumnos, 'query': query})

@login_required
@permission_required('alumnos.view_alumno', raise_exception=True)
def detalle_alumno(request, alumno_id):
    alumno = get_object_or_404(Alumno, id=alumno_id)
    inscripciones = alumno.inscripciones.all()
    Auditoria.objects.create(
        usuario=request.user.username,
        accion="VER FICHA",
        modelo="Alumno",
        objeto_id=alumno.id,
        descripcion=f"Se visualizó la ficha del alumno {alumno.nombres} {alumno.apellidos}"
    )
    return render(request, 'detalle.html', {'alumno': alumno, 'inscripciones': inscripciones})

@login_required
@permission_required('alumnos.view_alumno', raise_exception=True)
def generar_pdf(request, alumno_id):
    alumno = get_object_or_404(Alumno, id=alumno_id)
    Auditoria.objects.create(
        usuario=request.user.username,
        accion="VER CONTRATO HTML",
        modelo="Alumno",
        objeto_id=alumno.id,
        descripcion=f"Se visualizó el contrato HTML del alumno {alumno.nombres} {alumno.apellidos}"
    )
    return render(request, 'alumnos/contrato_pdf.html', {
        'alumno': alumno,
        'fecha': datetime.now(),
    })

@login_required
@permission_required('alumnos.view_alumno', raise_exception=True)
def formulario_exportar_excel(request):
    return render(request, 'exportar_excel.html')

@login_required
@permission_required('alumnos.view_alumno', raise_exception=True)
def exportar_excel_grupo(request):
    grupo = request.GET.get('grupo')
    inscripciones = Inscripcion.objects.filter(
        grupo__iexact=grupo
    ).select_related('alumno').order_by('alumno__apellidos', 'alumno__nombres')

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Alumnos"
    ws.append(["RUN", "APELLIDOS", "NOMBRES", "EMAIL", "DIRECCION", "COMUNA", "TELEFONO"])

    for ins in inscripciones:
        a = ins.alumno
        ws.append([a.rut, a.apellidos, a.nombres, a.correo, a.direccion, a.comuna, a.telefono])

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="grupo_{grupo}.xlsx"'
    wb.save(response)

    Auditoria.objects.create(
        usuario=request.user.username,
        accion="EXPORTAR EXCEL",
        modelo="Inscripcion",
        objeto_id=0,
        descripcion=f"Exportación de alumnos del grupo {grupo}"
    )
    return response

@login_required
@permission_required('alumnos.add_alumno', raise_exception=True)
def carga_masiva_alumnos(request):
    resultado = None
    if request.method == 'POST' and request.FILES.get('archivo'):
        archivo = request.FILES['archivo']
        wb = openpyxl.load_workbook(archivo)
        ws = wb.active
        creados, actualizados, inscripciones_creadas = 0, 0, 0
        errores = []
        encabezados = [limpiar(cell.value).lower() for cell in ws[1]]

        for idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            datos = dict(zip(encabezados, row))
            try:
                rut = limpiar(datos.get('rut')).upper()
                if not rut:
                    errores.append(f"Fila {idx}: RUT vacío")
                    continue
                alumno, creado = Alumno.objects.update_or_create(
                    rut=rut,
                    defaults={
                        'apellidos': limpiar(datos.get('apellidos')),
                        'nombres': limpiar(datos.get('nombres')),
                        'correo': limpiar(datos.get('correo')),
                        'direccion': limpiar(datos.get('direccion')),
                        'comuna': limpiar(datos.get('comuna')),
                        'telefono': limpiar(datos.get('telefono')),
                    }
                )
                if creado: creados += 1
                else: actualizados += 1

                curso, grupo = limpiar(datos.get('curso')), limpiar(datos.get('grupo'))
                if curso and grupo:
                    _, ins_creada = Inscripcion.objects.get_or_create(
                        alumno=alumno, curso=curso, grupo=grupo,
                        defaults={
                            'fecha_inicio': datos.get('fecha_inicio') or None,
                            'fecha_fin': datos.get('fecha_fin') or None,
                            'estado': limpiar(datos.get('estado')),
                            'observaciones': limpiar(datos.get('observaciones')),
                        }
                    )
                    if ins_creada: inscripciones_creadas += 1
            except Exception as e:
                errores.append(f"Fila {idx}: {str(e)}")

        Auditoria.objects.create(
            usuario=request.user.username,
            accion="CARGA MASIVA",
            modelo="Alumno",
            objeto_id=0,
            descripcion=f"Carga masiva: {creados} creados, {actualizados} actualizados."
        )
        resultado = {'creados': creados, 'actualizados': actualizados, 'inscripciones_creadas': inscripciones_creadas, 'errores': errores}

    return render(request, 'carga_masiva.html', {'resultado': resultado})

# ==========================================
# 🌐 NUEVO: PORTAL DE ASISTENCIA Y FISCALIZACIÓN
# ==========================================

@login_required
def portal_asistencia(request):
    try:
        perfil = request.user.perfilusuario
    except:
        return render(request, 'error_acceso.html', {'error': 'Usuario sin Perfil configurado.'})

    modulos = Modulo.objects.all()
    context = {'modulos': modulos, 'perfil': perfil, 'hoy': timezone.now().date()}

    if request.method == "POST":
        # 👇 Nueva validación de PIN
        pin_ingresado = request.POST.get('pin_seguridad')
        
        if pin_ingresado != perfil.pin:
            messages.error(request, "PIN de seguridad incorrecto. Verifique sus credenciales.")
            return render(request, 'portal_asistencia.html', context)
            
        # ... (si el PIN es correcto, sigue con la carga de alumnos o guardado) ...
        modulo_id = request.POST.get('modulo')
        grupo_input = request.POST.get('grupo', '').strip().upper() # SIEMPRE MAYÚSCULAS
        
        if not modulo_id or not grupo_input:
            messages.warning(request, "Complete el módulo y el grupo.")
            return render(request, 'portal_asistencia.html', context)

        modulo_obj = get_object_or_404(Modulo, id=modulo_id)
        sesion = SesionClase.objects.filter(
            grupo=grupo_input, modulo=modulo_obj, fecha=timezone.now().date()
        ).first()

        if not sesion:
            messages.error(request, f"No hay clase programada hoy para {grupo_input} en {modulo_obj.nombre}.")
            return render(request, 'portal_asistencia.html', context)

        # SI EL RELATOR ENVÍA LA ASISTENCIA
        if 'btn_guardar' in request.POST:
            if perfil.rol != 'RELATOR':
                messages.error(request, "Solo los Relatores pueden grabar asistencia.")
                return redirect('portal_asistencia')

            alumnos_inscritos = Alumno.objects.filter(inscripciones__grupo=grupo_input).distinct()
            
            for alumno in alumnos_inscritos:
                # radio button: asistencia_{{ alumno.id }}
                estado = request.POST.get(f'asistencia_{alumno.id}')
                es_presente = (estado == 'presente')

                Asistencia.objects.update_or_create(
                    alumno=alumno, sesion=sesion,
                    defaults={'presente': es_presente}
                )

                # Envío de correo automático
                asunto = f"Registro Asistencia - {modulo_obj.nombre}"
                msg = f"Estimado(a) {alumno.nombres}:\n\nSu asistencia hoy ({sesion.fecha}) fue registrada como: {'PRESENTE' if es_presente else 'AUSENTE'}.\n\nDudas a contacto@otecuno.cl"
                send_mail(asunto, msg, settings.DEFAULT_FROM_EMAIL, [alumno.correo], fail_silently=True)

            messages.success(request, f"Asistencia de {grupo_input} guardada. Correos enviados.")
            return render(request, 'portal_asistencia.html', context)

        # VISTA DE LISTADO (Para Relator o Fiscalizador)
        alumnos = Alumno.objects.filter(inscripciones__grupo=grupo_input).distinct().order_by('apellidos')
        asistencias_actuales = Asistencia.objects.filter(sesion=sesion)
        mapa = {a.alumno_id: a.presente for a in asistencias_actuales}

        context.update({
            'alumnos': alumnos,
            'grupo_seleccionado': grupo_input,
            'modulo_seleccionado': modulo_obj,
            'sesion': sesion,
            'mapa_asistencia': mapa,
            'es_fiscalizador': (perfil.rol == 'FISCALIZADOR')
        })

    return render(request, 'portal_asistencia.html', context)