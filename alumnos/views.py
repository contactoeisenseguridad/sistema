from datetime import datetime
from io import BytesIO

from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.template.loader import get_template

import openpyxl
from xhtml2pdf import pisa

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

    if not request.user.has_perm('alumnos.view_alumno'):
        return HttpResponse("No autorizado", status=403)

    inscripciones = alumno.inscripciones.all()

    now = datetime.now()
    fecha = now.strftime("%d-%m-%Y")
    hora = now.strftime("%H:%M")

    template = get_template('contrato.html')
    html = template.render({
        'alumno': alumno,
        'inscripciones': inscripciones,
        'fecha': fecha,
        'hora': hora
    })

    resultado = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode("utf-8")), resultado)

    if pdf.err:
        return HttpResponse("Error al generar PDF", status=500)

    response = HttpResponse(resultado.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="contrato_{alumno.id}.pdf"'

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