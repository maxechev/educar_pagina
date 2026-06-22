from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.index, name='index'),

    # Páginas generales
    path('bienestar/', views.bienestar, name='bienestar'),
    path('contacto/', views.contacto, name='contacto'),
    path('inscripcion/', views.inscripcion, name='inscripcion'),
    path('niveles/', views.niveles, name='niveles'),
    path('noticias/', views.noticias, name='noticias'),
    # Login
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    # Dashboards
    path('alumno/', views.dashboard_alumno, name='dashboard-alumno'),
    path('docente/', views.dashboard_docente, name='dashboard-docente'),
    path('directivo/', views.dashboard_directivo, name='dashboard-directivo'),
    path('padres/', views.dashboard_padres, name='dashboard-padres'),
    path('preceptor/', views.dashboard_preceptor, name='dashboard-preceptor'),
    # Dashboards docente-tareas
    path('docente/tareas/', views.list_tareas, name='list-tareas'),
    path('docente/tareas/nueva/', views.crear_tarea, name='crear-tarea'),
    path('docente/tareas/<int:tarea_id>/editar/', views.editar_tarea, name='editar-tarea'),
    path('docente/tareas/<int:tarea_id>/borrar/', views.borrar_tarea, name='borrar-tarea'),
    # Dashboard docente
    path('horario-docente/', views.horario_docente, name='horario_docente'),
    path('postulacion/',views.postulacion,name='postulacion'),
    path('enviar-postulacion/',views.enviar_postulacion,name='enviar-postulacion'),
    path('enviar-consulta/',views.enviar_consulta,name='enviar-consulta'),
    path('crear-reserva/',views.crear_reserva,name='crear-reserva'),
    path('docente/guardar-nota/', views.guardar_nota, name='guardar-nota'),
    # Dashboards administrativos
    path('administrativo/', views.dashboard_administrativo, name='dashboard-administrativo'),
    path('aprobar-pago/<int:id_pago>/',views.aprobar_pago,name='aprobar-pago'),
    path('aprobar-inscripcion/<int:id_solicitud>/',views.aprobar_inscripcion,name='aprobar-inscripcion'),
    path('registrar-pago/',views.registrar_pago,name='registrar_pago'),
    path('enviar-documentacion/',views.enviar_documentacion,name='enviar_documentacion'),
    path('aprobar-documentacion/<int:id_documentacion>/',views.aprobar_documentacion,name='aprobar_documentacion'),
    path('rechazar-documentacion/<int:id_documentacion>/',views.rechazar_documentacion,name='rechazar_documentacion'),
    path('crear-usuario/',views.crear_usuario,name='crear-usuario'),
    # Comunicaciones - noticias y comunicados
    path('contacto/opinion/', views.guardar_opinion, name='guardar-opinion'),
    path('crear-comunicado/',views.crear_comunicado,name='crear-comunicado'),
    path('eliminar-opinion/<int:indice>/',views.eliminar_opinion,name='eliminar-opinion'),
    path('crear-noticia/',views.crear_noticia,name='crear-noticia'),
    path('postulacion/programar-publicacion', views.programar_publicacion, name='programar_publicacion'),
    path('rechazar-inscripcion/<int:id_solicitud>/',views.rechazar_inscripcion,name='rechazar-inscripcion'),
    path('guardar-observacion-justificacion/', views.guardar_observacion_justificacion, name='guardar-observacion-justificacion'),
]
if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )
