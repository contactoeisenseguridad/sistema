from datetime import datetime

from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse

import openpyxl

from .models import Alumno, Inscripcion, Auditoria


def limpiar(valor):
    if valor is None:
        return ''
    return str(valor).strip()


@login_required
def inicio(request):
    return render(request, 'inicio.html')


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

    return render(request, 'buscar.html', {
        'alumnos': alumnos,
        'query': query
    })

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

    return render(request, 'detalle.html', {
        'alumno': alumno,
        'inscripciones': inscripciones
    })


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
    ).select_related('alumno').order_by(
        'alumno__apellidos',
        'alumno__nombres'
    )

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Alumnos"

    ws.append([
        "RUN",
        "APELLIDOS",
        "NOMBRES",
        "EMAIL",
        "DIRECCION",
        "COMUNA",
        "TELEFONO"
    ])

    for ins in inscripciones:
        a = ins.alumno
        ws.append([
            a.rut,
            a.apellidos,
            a.nombres,
            a.correo,
            a.direccion,
            a.comuna,
            a.telefono
        ])

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
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

        creados = 0
        actualizados = 0
        inscripciones_creadas = 0
        errores = []

        encabezados = [
            limpiar(cell.value).lower()
            for cell in ws[1]
        ]

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

                if creado:
                    creados += 1
                else:
                    actualizados += 1

                curso = limpiar(datos.get('curso'))
                grupo = limpiar(datos.get('grupo'))

                if curso and grupo:
                    _, inscripcion_creada = Inscripcion.objects.get_or_create(
                        alumno=alumno,
                        curso=curso,
                        grupo=grupo,
                        defaults={
                            'fecha_inicio': datos.get('fecha_inicio') or None,
                            'fecha_fin': datos.get('fecha_fin') or None,
                            'estado': limpiar(datos.get('estado')),
                            'observaciones': limpiar(datos.get('observaciones')),
                        }
                    )

                    if inscripcion_creada:
                        inscripciones_creadas += 1

            except Exception as e:
                errores.append(f"Fila {idx}: {str(e)}")

        Auditoria.objects.create(
            usuario=request.user.username,
            accion="CARGA MASIVA",
            modelo="Alumno",
            objeto_id=0,
            descripcion=f"Carga masiva: {creados} creados, {actualizados} actualizados, {inscripciones_creadas} inscripciones creadas."
        )

        resultado = {
            'creados': creados,
            'actualizados': actualizados,
            'inscripciones_creadas': inscripciones_creadas,
            'errores': errores,
        }

    return render(request, 'carga_masiva.html', {
        'resultado': resultado
    })