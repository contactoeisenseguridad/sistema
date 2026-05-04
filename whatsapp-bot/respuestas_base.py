def responder_mensaje(mensaje: str) -> str:
    mensaje = mensaje.lower().strip()

    if not mensaje:
        return "Estimado/a, no hemos recibido el contenido del mensaje. ¿Nos puede indicar su consulta?"

    if any(palabra in mensaje for palabra in ["hola", "buenas", "buenos días", "buenas tardes"]):
        return (
            "Estimado/a, junto con saludar, gracias por comunicarse con OTEC UNO. "
            "¿Sobre qué curso desea recibir información?"
        )

    if any(palabra in mensaje for palabra in ["valor", "precio", "cuánto sale", "cuanto sale", "costo"]):
        return (
            "Estimado/a, el valor depende del curso que desea realizar. "
            "Contamos con cursos OS10 de Formación, Perfeccionamiento, Supervisor, CCTV y Conserje. "
            "Indíquenos cuál necesita y le enviaremos el detalle."
        )

    if any(palabra in mensaje for palabra in ["duración", "duracion", "cuánto dura", "cuanto dura", "días", "dias"]):
        return (
            "La duración depende del curso. En el caso del curso de Formación Guardia de Seguridad OS10, "
            "la duración es de 90 horas. También contamos con cursos de menor duración según el programa."
        )

    if any(palabra in mensaje for palabra in ["online", "presencial", "modalidad", "clases"]):
        return (
            "Nuestros cursos pueden considerar clases online y presenciales, según el programa. "
            "En cursos OS10, algunas actividades deben realizarse de forma presencial conforme a la normativa vigente."
        )

    if any(palabra in mensaje for palabra in ["inscripción", "inscripcion", "inscribirme", "matricular", "matrícula", "matricula"]):
        return (
            "Para la inscripción necesitamos sus datos personales y el curso que desea realizar. "
            "Un ejecutivo puede continuar el proceso por esta misma vía."
        )

    if any(palabra in mensaje for palabra in ["dirección", "direccion", "ubicación", "ubicacion", "donde están", "donde estan"]):
        return (
            "Nuestra oficina se encuentra en Melipilla. "
            "Si desea, podemos enviarle la dirección exacta y los horarios de atención."
        )

    if any(palabra in mensaje for palabra in ["fecha", "inicio", "cuándo empieza", "cuando empieza"]):
        return (
            "Contamos con inicios semanales, dependiendo del curso y disponibilidad de cupos. "
            "Indíquenos qué curso necesita para informarle la fecha más próxima."
        )

    return (
        "Estimado/a, gracias por escribirnos. Para entregarle una respuesta precisa, "
        "su consulta será derivada a un ejecutivo de OTEC UNO."
    )