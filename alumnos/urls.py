from django.urls import path
from .views import (
    inicio,
    buscar_alumno,
    detalle_alumno,
    generar_pdf,
    formulario_exportar_excel,
    exportar_excel_grupo,
)

urlpatterns = [
    path('', inicio, name='inicio'),

    path('buscar/', buscar_alumno, name='buscar_alumno'),
    path('alumno/<int:alumno_id>/', detalle_alumno, name='detalle_alumno'),
    path('alumno/<int:alumno_id>/pdf/', generar_pdf, name='generar_pdf'),

    path('exportar-excel/formulario/', formulario_exportar_excel, name='formulario_exportar_excel'),
    path('exportar-excel/', exportar_excel_grupo, name='exportar_excel_grupo'),
]