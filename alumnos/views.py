from datetime import datetime
from io import BytesIO

from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.template.loader import get_template

import openpyxl

from .models import Alumno, Inscripcion, Auditoria


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
        )

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

    template = get_template('alumnos/contrato_pdf.html')

    context = {
        'alumno': alumno,
        'fecha': datetime.now(),
    }

    html = template.render(context)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="contrato_{alumno.id}.pdf"'

    pisa_status = pisa.CreatePDF(
        html,
        dest=response
    )

    if pisa_status.err:
        return HttpResponse(
            'Error al generar el PDF',
            status=500
        )

    Auditoria.objects.create(
        usuario=request.user.username,
        accion="GENERAR PDF",
        modelo="Alumno",
        objeto_id=alumno.id,
        descripcion=f"Se generó el contrato PDF del alumno {alumno.nombres} {alumno.apellidos}"
    )

    return response


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