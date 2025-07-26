from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.db import connection
from django.http import JsonResponse
from datetime import datetime
from payslip_generation_system.models import UserRole 

from django.contrib.auth.decorators import login_required

@login_required
def dashboard(request):
    user = request.user
    username = user.username
    user_role = request.session.get('role')
    current_datetime = datetime.now()  # gets current date and time

    return render(request, 'dashboard/index.html', {
        'user_role': user_role,
        'username': username,
        'current_datetime': current_datetime,
    })