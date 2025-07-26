from django.shortcuts import render, redirect
from django.db import connection
from django.db import transaction
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
        # Formatted
        fullname = request.POST.get('fullname').replace(" ", "")
        birthdate = request.POST.get('birthdate')

        # Existing Check
        if User.objects.filter(username=fullname).exists():
            messages.error(request, 'A user already exists.')
            return redirect('employee_create')
        
        # Employee Profile
        employee = Employee.objects.create(
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
        uploaded_files = request.FILES.getlist('attachments')
        # Save each file in the "employee_attachments" folder inside the media directory
        for f in uploaded_files:
            # Django will handle saving the file with a random name
            EmployeeAttachment.objects.create(
                employee=employee,  # Associate with the employee
                file=f              # Save the file in the "employee_attachments" folder inside the media directory
            )

        # Employee Account
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

        # admin
        # checker
        # preparator_denr
        # preparator_meo_s = 43
        # preparator_meo_e = 42
        # preparator_meo_w = 44
        # preparator_meo_n = 45
        # employee (default)

        # Redirect
        messages.success(request, 'Employee added successfully!')
        return redirect('dashboard')
    
    return JsonResponse({'error': 'Invalid request method'}, status=400)