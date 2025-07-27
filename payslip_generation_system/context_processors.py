from .models import Employee
from datetime import datetime

def global_user_context(request):
    username = request.user.username
    user_role = request.session.get('role', '')
    current_datetime = datetime.now()

    try:
        if request.user.is_authenticated:
            employee = Employee.objects.get(user_id=request.user.id)
            username = employee.fullname
    except Employee.DoesNotExist:
        username = request.user.username

    return {
        'username': username,
        'user_role': user_role,
        'current_datetime': current_datetime,
    }
