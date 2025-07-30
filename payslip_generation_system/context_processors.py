from .models import Employee
from datetime import datetime

# Global Variables
def global_user_context(request):
    username = request.user.username
    user_role = request.session.get('role', '')
    current_datetime = datetime.now()

    preview_only_roles = [
        'admin',
        'accounting',
        'checker',
    ]

    restricted_roles = [
        'accounting',
        'employee',
        'preparator_denr_nec',
        'preparator_meo_s',
        'preparator_meo_e',
        'preparator_meo_w',
        'preparator_meo_n',
    ]

    hide_card_roles = [
        'employee',
        'accounting',
    ]

    hide_admin_options = [
        'checker'
        'accounting',
        'preparator_denr_nec',
        'preparator_meo_s',
        'preparator_meo_e',
        'preparator_meo_w',
        'preparator_meo_n',
        'employee',
    ]

    ROLE_FORMAT = {
        'admin': 'System Admin',
        'checker': 'Checker',
        'accounting': 'Accounting',
        'preparator_denr_nec': 'Preparator: DENR NCR NEC',
        'preparator_meo_s': 'Preparator: MEO South',
        'preparator_meo_e': 'Preparator: MEO East',
        'preparator_meo_w': 'Preparator: MEO West',
        'preparator_meo_n': 'Preparator: MEO North',
        'employee': 'Employee'
    }

    formatted_role = ROLE_FORMAT.get(user_role)

    try:
        if request.user.is_authenticated:
            employee = Employee.objects.get(user_id=request.user.id)
            username = employee.fullname
    except Employee.DoesNotExist:
        username = request.user.username

    return {
        'username': username,
        'user_role': user_role,
        'formatted_user_role': formatted_role,
        'current_datetime': current_datetime,
        'preview_only_roles': preview_only_roles,
        'hide_card_roles': hide_card_roles,
        'hide_admin_options': hide_admin_options,
        'restricted_roles': restricted_roles,
    }

