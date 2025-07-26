from django.shortcuts import render, redirect
from django.db import connection
from django.http import JsonResponse
from django.contrib import messages
from django.utils.dateparse import parse_date
from payslip_generation_system.models import Employee, EmployeeAttachment, UserRole
from django.contrib.auth.models import User

from django.contrib.auth.decorators import login_required

@login_required
def index(request):
    return render(request, 'employee/index.html')

def create(request):
    with connection.cursor() as cursor:
        cursor.execute('SELECT * FROM systems_division')
        divisions = cursor.fetchall()

    with connection.cursor() as cursor:
        cursor.execute('SELECT * FROM systems_section')
        sections = cursor.fetchall()
    return render(request, 'employee/create.html', {
        'divisions': divisions,
        'sections': sections,
    })

def store(request):
    if request.method == 'POST':
        # Employee Profile
        Employee.objects.create(
            fullname=request.POST.get('fullname'),
            birthdate=request.POST.get('birthdate'),
            address=request.POST.get('address'),
            contact=request.POST.get('contact'),
            education=request.POST.get('education'),
            gender=request.POST.get('gender'),
            employee_number=request.POST.get('employee_number'),
            position=request.POST.get('position'),
            date_hired=request.POST.get('date_hired'),
            division=request.POST.get('division'),
            section=request.POST.get('section'),
            fund_source=request.POST.get('fund_source'),
            salary=request.POST.get('salary'),
            tax_declaration=request.POST.get('tax_declaration'),
            eligibility=request.POST.get('eligibility')
        )

        # Employee Attachment


        # Employee Account
        fullname = request.POST.get('fullname').replace(" ", "")
        birthdate = request.POST.get('birthdate')
        username = fullname
        password =  birthdate.strip() if birthdate else 'defaultpass'
        user = User(username=username)
        user.set_password(password) # hashes the password
        user.save()

        # Employee Role
        UserRole.objects.create(
            user=user,
            role='employee'
        )

        # Redirect
        messages.success(request, 'Employee added successfully!')
        return redirect('dashboard')
    
    return JsonResponse({'error': 'Invalid request method'}, status=400)