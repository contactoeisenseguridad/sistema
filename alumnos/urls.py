from django.urls import path
from .views import (
    inicio,
    buscar_alumno,
    detalle_alumno,
    generar_pdf,
    formulario_exportar_excel,
    exportar_excel_grupo,
    carga_masiva_alumnos,
    portal_asistencia,
    buzon_masivo,  # 👈 1. Agrégala aquí
)

urlpatterns = [
    path('', inicio, name='inicio'),
    path('buscar/', buscar_alumno, name='buscar_alumno'),
    path('alumno/<int:alumno_id>/', detalle_alumno, name='detalle_alumno'),
    path('alumno/<int:alumno_id>/pdf/', generar_pdf, name='generar_pdf'),
    path('exportar-excel/formulario/', formulario_exportar_excel, name='formulario_exportar_excel'),
    path('exportar-excel/', exportar_excel_grupo, name='exportar_excel_grupo'),
    path('asistencia/', portal_asistencia, name='portal_asistencia'), # 👈 2. Quita el "views."
    path('carga-masiva/', carga_masiva_alumnos, name='carga_masiva_alumnos'),
    path('buzon_masivo/', buzon_masivo, name='buzon_masivo'),
    path('repositorio-documentos/', views.visor_repositorio_documentos, name='repositorio_documentos'),
]