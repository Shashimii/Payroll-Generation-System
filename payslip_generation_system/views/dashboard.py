from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.db import connection
from django.http import JsonResponse
from datetime import datetime
from payslip_generation_system.models import UserRole, Employee  

from django.contrib.auth.decorators import login_required

@login_required
def dashboard(request):
    user = request.user
    username = user.username
    user_role = request.session.get('role')
    current_datetime = datetime.now()
    employee_count = Employee.objects.count()

    return render(request, 'dashboard/index.html', {
        'user_role': user_role,
        'username': username,
        'current_datetime': current_datetime,
        'employee_count': employee_count
    })