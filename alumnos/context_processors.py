from .models import Aviso

def aviso_global(request):
    aviso = Aviso.objects.filter(activo=True).order_by('-fecha').first()
    return {'aviso': aviso}