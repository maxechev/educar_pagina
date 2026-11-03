from core.models import PersonalAdministrativo, Tutor


def mobile_role_for_user(user):
    admin_profile = PersonalAdministrativo.objects.filter(
        id_persona__id_usuario=user
    ).exists()
    tutor_profile = Tutor.objects.filter(id_persona__id_usuario=user).exists()

    if user.rol == "administrativo" and admin_profile:
        return "administrativo"
    if user.rol == "padre" and tutor_profile:
        return "padre"

    # Older accounts may have no explicit role stored; infer only when exactly
    # one of the two mobile profiles is present.
    if not user.rol:
        if admin_profile and not tutor_profile:
            return "administrativo"
        if tutor_profile and not admin_profile:
            return "padre"
    return None
