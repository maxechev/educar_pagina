"""Patrones de diseño usados por los servicios de la aplicación."""

from abc import ABC


class UsuarioFactory(ABC):
    """Factory Method para crear cuentas con un rol concreto."""

    rol = None

    def __init__(self, modelo_usuario):
        self.modelo_usuario = modelo_usuario

    def crear(self, *, nombre_usuario, contrasenia, correo=None, estado='Activo'):
        return self.modelo_usuario.objects.create(
            nombre_usuario=nombre_usuario,
            contrasenia=contrasenia,
            correo=correo,
            rol=self.rol,
            estado=estado,
        )


class AdministradorFactory(UsuarioFactory):
    rol = 'administrativo'


class PadreFactory(UsuarioFactory):
    rol = 'padre'


class AlumnoFactory(UsuarioFactory):
    rol = 'alumno'


class ProfesorFactory(UsuarioFactory):
    rol = 'docente'


class PreceptorFactory(UsuarioFactory):
    rol = 'preceptor'


class DirectivoFactory(UsuarioFactory):
    rol = 'directivo'


class UsuarioFactoryMethod:
    """Selecciona la fábrica concreta a partir del rol solicitado."""

    FABRICAS = {
        'administrativo': AdministradorFactory,
        'padre': PadreFactory,
        'alumno': AlumnoFactory,
        'docente': ProfesorFactory,
        'preceptor': PreceptorFactory,
        'directivo': DirectivoFactory,
    }

    @classmethod
    def crear(cls, rol, **datos):
        try:
            fabrica = cls.FABRICAS[rol.lower()]
        except (AttributeError, KeyError) as exc:
            raise ValueError(f'Rol no soportado: {rol}') from exc
        return fabrica(datos.pop('modelo_usuario')).crear(**datos)


class ReporteFactory:
    """Factory Method para construir reportes sin exponer sus consultas."""

    @staticmethod
    def alumnos(modelos, tipo='', filtro=''):
        Alumno = modelos['Alumno']
        qs = Alumno.objects.select_related('id_persona', 'id_curso__nivel_educativo')
        if tipo == 'curso' and str(filtro).isdigit():
            qs = qs.filter(id_curso_id=int(filtro))
        elif tipo == 'materia' and str(filtro).isdigit():
            qs = qs.filter(id_curso__cursocursamaterias__id_materia_id=int(filtro))
        elif tipo == 'nivel' and str(filtro).isdigit():
            qs = qs.filter(id_curso__nivel_educativo_id=int(filtro))
        elif tipo == 'deporte' and str(filtro).isdigit():
            qs = qs.filter(inscripciones_deportivas__id_grupo__id_disciplina_id=int(filtro))
        elif tipo == 'transporte' and str(filtro).isdigit():
            qs = qs.filter(inscripciones_transporte__id_recorrido_id=int(filtro))
        elif tipo == 'comedor' and str(filtro).isdigit():
            qs = qs.filter(inscripciones_comedor__id_servicio_id=int(filtro))
        return qs.distinct()


class GestionEscolarFacade:
    """Fachada única para las operaciones frecuentes del sistema."""

    def __init__(self, modelos):
        self.modelos = modelos

    def crear_usuario(self, rol, **datos):
        datos['modelo_usuario'] = self.modelos['Usuario']
        return UsuarioFactoryMethod.crear(rol, **datos)

    def reporte_alumnos(self, tipo='', filtro=''):
        return ReporteFactory.alumnos(self.modelos, tipo, filtro)

    def inscripciones_servicio(self, alumno):
        return {
            'transporte': self.modelos['InscripcionTransporte'].objects.filter(
                id_alumno=alumno, estado='Activa'
            ),
            'comedor': self.modelos['InscripcionComedor'].objects.filter(
                id_alumno=alumno, estado='Activa'
            ),
        }
