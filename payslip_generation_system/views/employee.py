from django.shortcuts import render, redirect, get_object_or_404
from django.db import connection
from django.db import transaction
from django.http import JsonResponse
from django.contrib import messages
from django.utils.dateparse import parse_date
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from payslip_generation_system.models import Employee, EmployeeAttachment, UserRole
from payslip_generation_system.decorators import restrict_roles
from django.contrib.auth.models import User

from django.contrib.auth.decorators import login_required

@login_required
@restrict_roles(disallowed_roles=['employee'])
def index(request):
    return render(request, 'employee/index.html')

@login_required
@restrict_roles(disallowed_roles=['employee'])
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

@login_required
@restrict_roles(disallowed_roles=['employee'])
def store(request):
    if request.method == 'POST':
        # Formatted
        fullname = request.POST.get('fullname').replace(" ", "")
        birthdate = request.POST.get('birthdate')

        # Existing Check
        if User.objects.filter(username=fullname).exists():
            messages.error(request, 'A user already exists.')
            return redirect('employee_create')
        
        # Employee Account
        username = fullname
        password =  birthdate.strip() if birthdate else 'defaultpass'
        user = User(username=username)
        user.set_password(password) # hashes the password
        user.save()
        
        # Employee Profile
        employee = Employee.objects.create(
            user=user,  
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
            eligibility=request.POST.get('eligibility'),
            assigned_office=request.POST.get('assigned_office'),
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

        # Employee Role
        UserRole.objects.create(
            user=user,
            role='employee' # New accounts default role
        )

        # Change it on the database using this roles
        # admin (System IT only)
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

@login_required
@restrict_roles(disallowed_roles=['employee'])
def edit(request, emp_id):
    with connection.cursor() as cursor:
        cursor.execute('SELECT * FROM systems_division')
        divisions = cursor.fetchall()

    with connection.cursor() as cursor:
        cursor.execute('SELECT * FROM systems_section')
        sections = cursor.fetchall()

    employee = get_object_or_404(Employee, id=emp_id)
    attachments = employee.attachments.all()

    return render(request, 'employee/edit.html', {
        'divisions': divisions,
        'sections': sections,
        'employee': employee,
        'attachments': attachments,
    })

@login_required
@restrict_roles(disallowed_roles=['employee'])
def update(request, emp_id):    
    if request.method == "POST":
        employee = get_object_or_404(Employee, id=emp_id)

        # Existing Check
        check_username = request.POST.get('fullname').replace(" ", "")
        if User.objects.filter(username=check_username).exists():
            messages.error(request, 'Full Name already exists.')
            return redirect('employee_edit', emp_id)
        
        # Formatted
        account_fullname = request.POST.get('fullname').replace(" ", "")
        account_birthdate = request.POST.get('birthdate')

        # Update Employee Account
        if employee.user_id:
            user = get_object_or_404(User, id=employee.user_id)
            username = account_fullname
            password =  account_birthdate.strip() if account_birthdate else 'defaultpass'

            user.username = username
            user.set_password(password)  # hashes the password
            user.save()
    
        # Update Employee
        # New Data
        fullname=request.POST.get('fullname')
        birthdate=request.POST.get('birthdate')
        address=request.POST.get('address')
        contact=request.POST.get('contact')
        education=request.POST.get('education')
        gender=request.POST.get('gender')
        employee_number=request.POST.get('employee_number')
        position=request.POST.get('position')
        date_hired=request.POST.get('date_hired')
        division=request.POST.get('division')
        section=request.POST.get('section')
        fund_source=request.POST.get('fund_source')
        salary=request.POST.get('salary')
        tax_declaration=request.POST.get('tax_declaration')
        eligibility=request.POST.get('eligibility')

        # Update Data
        employee.fullname = fullname
        employee.birthdate = birthdate
        employee.address = address
        employee.contact = contact
        employee.education = education
        employee.gender = gender
        employee_number = employee_number
        employee.position = position
        employee.date_hired = date_hired
        employee.division = division
        employee.section = section
        employee.fund_source = fund_source
        employee.salary = salary
        employee.tax_declaration = tax_declaration
        employee.eligibility = eligibility
        employee.save()

        # Handle new attachments
        files = request.FILES.getlist('attachments')
        for file in files:
            # Create the EmployeeAttachment object
            EmployeeAttachment.objects.create(employee=employee, file=file)
            
        # Send response back
        messages.success(request, "Employee details updated successfully.")
    return redirect('dashboard')

@login_required
@restrict_roles(disallowed_roles=['employee'])
def destroy(request, emp_id):
    employee = get_object_or_404(Employee, id=emp_id)

    if request.method == "POST":
        # Delete all associated attachments
        for attachment in employee.attachments.all():
            attachment.delete()  # Delete the file from the storage

        # Delete all adjustments connected to this employee
        # Adjustment.objects.filter(employee=employee).delete()
        
        # Delete Employee Account
        if employee.user_id:
            try:
                user = User.objects.get(id=employee.user_id)
                user.delete()
            except User.DoesNotExist:
                pass

        # Now delete the employee
        employee.delete()
        return JsonResponse({"success": True, "message": "Employee deleted successfully!"})

    return JsonResponse({"success": False, "message": "Invalid request method!"})

@login_required
@restrict_roles(disallowed_roles=['employee'])
def attachment_delete(request, attachment_id):
    if request.method == "POST":
        attachment = get_object_or_404(EmployeeAttachment, id=attachment_id)
        attachment.delete()
        return JsonResponse({"success": True, "message": "Attachment deleted."})
    return JsonResponse({"success": False, "message": "Invalid request."})

@login_required
@restrict_roles(disallowed_roles=['employee'])
def data(request):
    user_role = request.session.get('role')

    # DataTable parameters
    draw = int(request.GET.get('draw', 1))
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 10))
    search_value = request.GET.get('search[value]', '')
    order_col_index = int(request.GET.get('order[0][column]', 0))
    order_dir = request.GET.get('order[0][dir]', 'asc')

    # Fields to retrieve
    fields = ['id', 'employee_number', 'fullname', 'position', 'fund_source', 'salary', 'tax_declaration', 'eligibility']

    # Roles
    role = request.session.get('role')
    
    # Data
    match role:
        case "admin":
            queryset = Employee.objects.values(*fields)
        case "checker":
            queryset = Employee.objects.values(*fields)
        case _:
            return JsonResponse({
                'draw': draw,
                'recordsTotal': 0,
                'recordsFiltered': 0,
                'data': []
            })

    # Search filter
    if search_value:
        queryset = queryset.filter(
            Q(employee_number__icontains=search_value) |
            Q(fullname__icontains=search_value) |
            Q(position__icontains=search_value) |
            Q(fund_source__icontains=search_value) |
            Q(tax_declaration__icontains=search_value) |
            Q(eligibility__icontains=search_value)
        )

    total_records = queryset.count()

    # Ordering logic
    order_columns = fields
    order_column = order_columns[order_col_index] if order_col_index < len(order_columns) else 'date_hired'
    if order_dir == 'desc':
        order_column = f'-{order_column}'
    queryset = queryset.order_by(order_column)

    # Pagination
    paginator = Paginator(queryset, length)
    page_number = (start // length) + 1
    page = paginator.get_page(page_number)

    data = []
    for emp in page:
        salary = f"₱{emp['salary']:,.2f}" if emp.get('salary') else ""

        data.append([
            emp.get('employee_number', ''),
            emp.get('fullname', ''),
            emp.get('position', ''),
            emp.get('fund_source', ''),
            salary,
            emp.get('tax_declaration', ''),
            emp.get('eligibility', ''),
            f"""
            <button class='btn btn-info btn-sm view-btn' data-id='{emp['id']}' title='Information' data-toggle='modal' data-target='#viewModal'>
                <i class="fas fa-eye"></i>
            </button> 
            <button class='edit-btn btn btn-primary btn-sm view-btn' title='Edit' data-id='{emp['id']}'>
                <i class="fas fa-pen"></i>
            </button> 
            <button class='delete-btn btn btn-danger btn-sm view-btn' title='Delete' data-id='{emp['id']}'>
                <i class="fas fa-trash"></i>
            </button>
            """
        ])

    return JsonResponse({
        'draw': draw,
        'recordsTotal': total_records,
        'recordsFiltered': total_records,
        'data': data
    })

@login_required
@restrict_roles(disallowed_roles=['employee'])
def show(request, emp_id):
    employee = get_object_or_404(Employee, id=emp_id)
    attachments = EmployeeAttachment.objects.filter(employee=employee)

    # Prepare the employee data to send as JSON
    employee_data = {
        'employee_number': employee.employee_number,
        'fullname': employee.fullname,
        'date_hired': employee.date_hired.strftime('%Y-%m-%d'),
        'position': employee.position,
        'education': employee.education,
        'birthdate': employee.birthdate.strftime('%Y-%m-%d'),
        'gender': employee.gender,
        'fund_source': employee.fund_source,
        'tax_declaration': employee.tax_declaration,
        'salary': f"₱{employee.salary:,.2f}",
        'eligibility': employee.eligibility,
        'attachments': [
            {
                'file_url': attachment.file.url,
                'file_name': attachment.file.name.split('/')[-1],
                'attachment_id': attachment.id
            }
            for attachment in attachments
        ]
    }

    return JsonResponse({'employee': employee_data})