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
from payslip_generation_system.models.batch import Batch
from django.contrib.auth.decorators import login_required

@login_required
@restrict_roles(disallowed_roles=['employee', 'accounting'])
def index(request):
    return render(request, 'employee/index.html')

@login_required
@restrict_roles(disallowed_roles=['employee', 'accounting'])
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
@restrict_roles(disallowed_roles=['employee', 'accounting'])
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
            has_philhealth=request.POST.get('philhealth'),
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
        # preparator_denr_nec
        # preparator_denr_prcmo
        # preparator_meo_s = 43
        # preparator_meo_e = 42
        # preparator_meo_w = 44
        # preparator_meo_n = 45
        # employee (default)

        # Redirect
        messages.success(request, 'Employee added successfully!')
        return redirect('employee')
    
    return JsonResponse({'error': 'Invalid request method'}, status=400)

@login_required
@restrict_roles(disallowed_roles=['employee', 'accounting'])
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
@restrict_roles(disallowed_roles=['employee', 'accounting'])
def update(request, emp_id):    
    if request.method == "POST":
        employee = get_object_or_404(Employee, id=emp_id)

        # Existing Check - exclude current user when checking for duplicates
        check_username = request.POST.get('fullname').replace(" ", "")
        existing_user_query = User.objects.filter(username=check_username)
        
        # If employee has a user_id, exclude that user from the duplicate check
        if employee.user_id:
            existing_user_query = existing_user_query.exclude(id=employee.user_id)
        
        if existing_user_query.exists():
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
        philhealth=request.POST.get('philhealth')
        eligibility=request.POST.get('eligibility')

        # Update Data
        employee.fullname = fullname
        employee.birthdate = birthdate
        employee.address = address
        employee.contact = contact
        employee.education = education
        employee.gender = gender
        employee.employee_number = employee_number
        employee.position = position
        employee.date_hired = date_hired
        employee.division = division
        employee.section = section
        employee.fund_source = fund_source
        employee.salary = salary
        employee.tax_declaration = tax_declaration
        employee.has_philhealth = philhealth
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
@restrict_roles(disallowed_roles=['employee', 'accounting'])
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
@restrict_roles(disallowed_roles=['employee', 'accounting'])
def attachment_delete(request, attachment_id):
    if request.method == "POST":
        attachment = get_object_or_404(EmployeeAttachment, id=attachment_id)
        attachment.delete()
        return JsonResponse({"success": True, "message": "Attachment deleted."})
    return JsonResponse({"success": False, "message": "Invalid request."})

@login_required
@restrict_roles(disallowed_roles=['employee', 'accounting'])
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
    fields = ['id', 'employee_number', 'fullname', 'position', 'fund_source', 'salary', 'tax_declaration', 'has_philhealth', 'eligibility', 'section', 'division', 'assigned_office', 'batch_number']

    # Roles
    role = request.session.get('role')

    # Offices
    denrncrnec = 'denr_ncr_nec'
    denrncrprcmo = 'denr_ncr_prcmo'
    meos = 'meo_s'
    meoe = 'meo_e'
    meow = 'meo_w'
    meon = 'meo_n'
    
    # Data
    match role:
        case "admin":
            queryset = Employee.objects.values(*fields)
        case "checker":
            queryset = Employee.objects.values(*fields)
        case "accounting":
            queryset = Employee.objects.values(*fields)
        case "preparator_denr_nec":
            queryset = Employee.objects.filter(assigned_office=denrncrnec).values(*fields)
        case "preparator_denr_prcmo":
            queryset = Employee.objects.filter(assigned_office=denrncrprcmo).values(*fields)
        case "preparator_meo_s":
            queryset = Employee.objects.filter(assigned_office=meos).values(*fields)
        case "preparator_meo_e":
            queryset = Employee.objects.filter(assigned_office=meoe).values(*fields)
        case "preparator_meo_w":
            queryset = Employee.objects.filter(assigned_office=meow).values(*fields)
        case "preparator_meo_n":
            queryset = Employee.objects.filter(assigned_office=meon).values(*fields)
        case _:
            return JsonResponse({
                'draw': draw,
                'recordsTotal': 0,
                'recordsFiltered': 0,
                'data': []
            })

    SEARCH_OFFICE_NAME_MAP = {
        'DENR NCR NEC': 'denr_ncr_nec',
        'DENR NCR PRCMO': 'denr_ncr_prcmo',
        'MEO East': 'meo_e',
        'MEO South': 'meo_s',
        'MEO West': 'meo_w',
        'MEO North': 'meo_n',
    }

    # Search filter
    if search_value:
        search_value = search_value.strip()

        # Check if the search value matches a formatted office name
        mapped_office = SEARCH_OFFICE_NAME_MAP.get(search_value)

        queryset = queryset.filter(
            Q(employee_number__icontains=search_value) |
            Q(fullname__icontains=search_value) |
            Q(position__icontains=search_value) |
            Q(fund_source__icontains=search_value) |
            Q(tax_declaration__icontains=search_value) |
            Q(eligibility__icontains=search_value) |
            (
                Q(assigned_office__iexact=mapped_office)
                if mapped_office
                else Q(assigned_office__icontains=search_value.lower())
            )
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

    OFFICE_NAME_MAP = {
        'denr_ncr_nec': 'DENR NCR NEC',
        'denr_ncr_prcmo': 'DENR NCR PRCMO',
        'meo_e': 'MEO East',
        'meo_s': 'MEO South',
        'meo_w': 'MEO West',
        'meo_n': 'MEO North',
    }

    data = []
    for emp in page:
        salary = f"₱{emp['salary']:,.2f}" if emp.get('salary') else ""
        
        # Get batch name if batch_number exists
        batch_display = 'Not Assigned'
        if emp.get('batch_number'):
            try:
                from payslip_generation_system.models.batch import Batch
                batch = Batch.objects.filter(batch_number=emp['batch_number']).first()
                if batch:
                    batch_display = f"{batch.batch_name} (#{batch.batch_number})"
            except:
                batch_display = f"Batch #{emp['batch_number']}"

        data.append([
            emp.get('employee_number', ''),
            emp.get('fullname', ''),
            emp.get('position', ''),
            emp.get('fund_source', ''),
            salary,
            OFFICE_NAME_MAP.get(emp.get('assigned_office', '')),
            emp.get('tax_declaration', ''),
            emp.get('has_philhealth', ''),
            emp.get('eligibility', ''),
            batch_display,
            f"""
            <button class='btn btn-info btn-sm view-btn' data-id='{emp['id']}' title='Information' data-toggle='modal' data-target='#viewModal'>
                <i class="fas fa-eye"></i>
            </button> 
            <button class='edit-btn btn btn-primary btn-sm view-btn' title='Edit' data-id='{emp['id']}'>
                <i class="fas fa-pen"></i>
            </button> 
            <button class='set-batch-btn btn btn-warning btn-sm' title='Set Batch' data-id='{emp['id']}' data-name='{emp.get('fullname', '')}'>
                <i class="fas fa-layer-group"></i>
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
@restrict_roles(disallowed_roles=['employee', 'accounting'])
def show(request, emp_id):
    OFFICE_NAME_MAP = {
    'denr_ncr_nec': 'DENR NCR NEC',
    'denr_ncr_prcmo': 'DENR NCR PRCMO',
    'meo_e': 'MEO East',
    'meo_s': 'MEO South',
    'meo_w': 'MEO West',
    'meo_n': 'MEO North',
}

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
        'assigned_office': OFFICE_NAME_MAP.get(employee.assigned_office, employee.assigned_office),
        'has_philhealth': employee.has_philhealth,
        'eligibility': employee.eligibility,
        'batch_number': 'Not Assigned',
        'attachments': [
            {
                'file_url': attachment.file.url,
                'file_name': attachment.file.name.split('/')[-1],
                'attachment_id': attachment.id
            }
            for attachment in attachments
        ]
    }
    
    # Get batch name if batch_number exists
    if employee.batch_number:
        try:
            from payslip_generation_system.models.batch import Batch
            batch = Batch.objects.filter(batch_number=employee.batch_number).first()
            if batch:
                employee_data['batch_number'] = f"{batch.batch_name} (#{batch.batch_number})"
        except:
            employee_data['batch_number'] = f"Batch #{employee.batch_number}"

    return JsonResponse({'employee': employee_data})

@login_required
@restrict_roles(disallowed_roles=['employee', 'accounting'])
def assign_batch(request, emp_id):
    if request.method == 'POST':
        try:
            employee = get_object_or_404(Employee, id=emp_id)
            batch_id = request.POST.get('batch_id')
            
            if not batch_id:
                return JsonResponse({'success': False, 'error': 'Batch ID is required.'})
            
            batch = get_object_or_404(Batch, id=batch_id)
            
            # Check if the batch belongs to the user's office
            user_role = request.session.get('role', '')
            user_office = get_user_assigned_office(user_role)
            
            if not user_office or batch.batch_assigned_office != user_office:
                return JsonResponse({'success': False, 'error': 'You can only assign employees to batches in your office.'})
            
            # Update employee's batch number
            employee.batch_number = batch.batch_number
            employee.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Employee {employee.fullname} has been assigned to batch {batch.batch_name} (#{batch.batch_number})'
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'An error occurred: {str(e)}'})
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)

@login_required
@restrict_roles(disallowed_roles=['employee', 'accounting'])
def get_available_batches(request):
    try:
        user_role = request.session.get('role', '')
        user_office = get_user_assigned_office(user_role)
        
        if not user_office:
            return JsonResponse({'success': False, 'error': 'Unable to determine your office.'})
        
        # Get batches for the user's office
        from payslip_generation_system.models.batch import Batch
        batches = Batch.objects.filter(batch_assigned_office=user_office).order_by('batch_number')
        
        batch_data = []
        for batch in batches:
            batch_data.append({
                'id': batch.id,
                'batch_number': batch.batch_number,
                'batch_name': batch.batch_name
            })
        
        return JsonResponse({
            'success': True,
            'batches': batch_data
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'An error occurred: {str(e)}'})

def get_user_assigned_office(user_role):
    role_to_office = {
        'preparator_denr_nec': 'denr_ncr_nec',
        'preparator_denr_prcmo': 'denr_ncr_prcmo',
        'preparator_meo_s': 'meo_s',
        'preparator_meo_e': 'meo_e',
        'preparator_meo_w': 'meo_w',
        'preparator_meo_n': 'meo_n',
    }
    return role_to_office.get(user_role)