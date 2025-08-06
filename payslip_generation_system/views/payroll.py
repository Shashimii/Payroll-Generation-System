from django.shortcuts import render, redirect, get_object_or_404
from django.db import connection
from django.db import transaction
from django.http import JsonResponse
from django.contrib import messages
from django.utils.dateparse import parse_date
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from decimal import Decimal
from datetime import datetime
from payslip_generation_system.models import Employee, BatchAssignment, Adjustment
from payslip_generation_system.decorators import restrict_roles
from django.db.models import Case, When, Value, IntegerField
from django.forms.models import model_to_dict

from django.contrib.auth.decorators import login_required

@login_required
@restrict_roles(disallowed_roles=['employee'])
def index(request):
    months = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]

    years = list(range(2020, 2031))

    # Get only distinct batch numbers
    batches = BatchAssignment.objects.values_list('batch_number', flat=True).distinct().order_by('batch_number')

    return render(request, 'payroll/index.html', {
        'months': months,
        'years': years,
        'batches': batches,
    })

@login_required
@restrict_roles(disallowed_roles=['employee'])
def submit(request):
    if request.method == 'POST':
        # Payroll information
        cutoff = request.POST.get('cutoff')
        cutoff_month = request.POST.get('cutoff_month')
        cutoff_year = request.POST.get('cutoff_year')
        batch_number = request.POST.get('batch_number')

        ## Get the id of the employees on the batch
        ## then change the adjustment statuses of the employees 

        # Employees on the current payroll
        employee_ids = BatchAssignment.objects.filter(
            batch_number=batch_number,
            cutoff=cutoff,
            cutoff_month=cutoff_month,
            cutoff_year=cutoff_year
        ).values_list('employee_id', flat=True)

        # Update their adjustment statuses
        Adjustment.objects.filter(
            employee_id__in=employee_ids,
            cutoff=cutoff,
            month=cutoff_month,
            cutoff_year=cutoff_year
        ).update(status="Pending")


        return JsonResponse({'status': 'OK'}, status=200)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)

@login_required
@restrict_roles(disallowed_roles=['employee'])
def batch_data(request):
    batch_number = request.GET.get('batch_number')
    cutoff = request.GET.get('cutoff')
    cutoff_month = request.GET.get('cutoff_month')
    cutoff_year = request.GET.get('cutoff_year')

    batch_number = int(batch_number) if batch_number else 1
    cutoff = cutoff if cutoff else '1st'
    cutoff_month = cutoff_month if cutoff_month else 'January'
    cutoff_year = int(cutoff_year) if cutoff_year else datetime.now().year


    assignments = BatchAssignment.objects.filter(
        batch_number=batch_number,
        cutoff=cutoff,
        cutoff_month=cutoff_month,
        cutoff_year=cutoff_year
    ).select_related('employee').annotate(
        late_order=Case(
            When(late_assigned='NO', then=Value(0)),
            When(late_assigned='YES', then=Value(1)),
            default=Value(2),
            output_field=IntegerField()
        )
    ).order_by('late_order', 'employee__fullname')

    employees = []
    for assignment in assignments:
        emp_data = model_to_dict(assignment.employee, fields=[
            'id', 'employee_number', 'fullname', 'position', 'division'
        ])
        emp_data['late_assigned'] = assignment.late_assigned
        employees.append(emp_data)

    return JsonResponse({
        'employees': employees,
        'cutoff': cutoff,
        'cutoff_month': cutoff_month,
        'cutoff_year': cutoff_year,
        'batch_number': batch_number,
    })

@login_required
@restrict_roles(disallowed_roles=['employee'])
def batch_create(request, batch_size=15):
    employees = Employee.objects.order_by('fullname')
    cutoff=request.POST.get('cutoff')
    cutoff_month=request.POST.get('cutoff_month')
    cutoff_year=request.POST.get('cutoff_year')
    batch_number = 1

    if not cutoff or not cutoff_month or not cutoff_year:
        return JsonResponse({'error': 'Missing cutoff, month, or year.'}, status=400)

    if BatchAssignment.objects.filter(
        cutoff=cutoff,
        cutoff_month=cutoff_month,
        cutoff_year=cutoff_year
    ).exists():
        return JsonResponse({'error': f'Batches already exist for {cutoff_month} {cutoff} cutoff {cutoff_year}.'}, status=400)

    for index, employee in enumerate(employees, start=1):
        BatchAssignment.objects.create(
            employee=employee,
            batch_number=batch_number,
            cutoff=cutoff,
            cutoff_month=cutoff_month,
            cutoff_year=cutoff_year
        )

        if index % batch_size == 0:
            batch_number += 1

    return JsonResponse({'message': f'Batches successfully created for {cutoff} {cutoff_year} {cutoff_year}.'})

@login_required
@restrict_roles(disallowed_roles=['employee'])
def batch_late(request):
    if request.method == 'POST':
        employee_id = request.POST.get('employee_id')
        employee = get_object_or_404(Employee, id=employee_id)
        cutoff = request.POST.get('cutoff')
        cutoff_month = request.POST.get('cutoff_month')
        cutoff_year = request.POST.get('cutoff_year')
        batch_number = request.POST.get('batch_number')

        ## Save the previous batch number update YES to assignment_late
        ## Change the employee batch number for the cutoff, month, year selected
        ## move it to the last batch if the last batch is not yet 15 employees
        ## if its already full create a new batch for it 

        # Get existing batch_number before changing
        previous_batch = BatchAssignment.objects.filter(
            employee=employee,
            cutoff=cutoff,
            cutoff_month=cutoff_month,
            cutoff_year=cutoff_year,
        ).values_list('batch_number', flat=True).first()

        # last batch number for the selected payroll period
        last_batch = (
            BatchAssignment.objects
            .filter(cutoff=cutoff, cutoff_month=cutoff_month, cutoff_year=cutoff_year)
            .order_by('-batch_number') # desc
            .first()
        )

        # Count the number of employees on the last batch
        if last_batch:
            last_batch_number = last_batch.batch_number # batch_number
            count = BatchAssignment.objects.filter(
                cutoff=cutoff,
                cutoff_month=cutoff_month,
                cutoff_year=cutoff_year,
                batch_number=last_batch_number
            ).count()

            if count <= 15:
                # if last batch not full reassign to the last batch
                batch_number = last_batch_number
            else:
                # if last batch full create new batch
                batch_number = last_batch_number + 1
        else:
            # create a default to prevent error
            batch_number = 1

        # Update or create the batch assignment of employee
        BatchAssignment.objects.update_or_create(
            employee=employee,
            cutoff=cutoff,
            cutoff_month=cutoff_month,
            cutoff_year=cutoff_year,
            defaults={
                'batch_number': batch_number,
                'late_assigned': 'YES',
                'previous_batch': previous_batch,
            }
        )

        # Check for adjustment if theres any
        adjustments = Adjustment.objects.filter(
            employee=employee,
            cutoff=cutoff,
            month=cutoff_month,
            cutoff_year=cutoff_year
        )

        # Adjustment exists update the adjustment batch_number identifier
        if adjustments.exists():
            adjustments.update(batch_number=batch_number)

        return JsonResponse({'status': 'OK'}, status=200)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)

@login_required
@restrict_roles(disallowed_roles=['employee'])
def batch_unlate(request):
    if request.method == 'POST':
        employee_id = request.POST.get('employee_id')
        employee = get_object_or_404(Employee, id=employee_id)
        cutoff = request.POST.get('cutoff')
        cutoff_month = request.POST.get('cutoff_month')
        cutoff_year = request.POST.get('cutoff_year')
        batch_number = request.POST.get('batch_number')

        ## Get the previous_batch
        ## Revert the employee batch number for the cutoff, month, year selected
        ## Use the previous_number to revert the batch_number
        ## Revert the assigned_late to NO

        # Get the previous_batch
        previous_batch = BatchAssignment.objects.filter(
            employee=employee,
            cutoff=cutoff,
            cutoff_month=cutoff_month,
            cutoff_year=cutoff_year,
        ).values_list('previous_batch', flat=True).first()

        # Update or create the batch assignment of employee
        BatchAssignment.objects.update_or_create(
            employee=employee,
            cutoff=cutoff,
            cutoff_month=cutoff_month,
            cutoff_year=cutoff_year,
            defaults={
                'batch_number': previous_batch,
                'late_assigned': 'NO',
                'previous_batch': None,
            }
        )

        # Check for adjustment if theres any
        adjustments = Adjustment.objects.filter(
            employee=employee,
            cutoff=cutoff,
            month=cutoff_month,
            cutoff_year=cutoff_year
        )

        # Adjustment exists update the adjustment batch_number identifier
        if adjustments.exists():
            adjustments.update(batch_number=previous_batch)

        return JsonResponse({'status': 'OK'}, status=200)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)

@login_required
@restrict_roles(disallowed_roles=['employee'])
def adjustment_create(request, emp_id):
    if request.method == 'POST':
        # Form
        id = emp_id
        late = request.POST.get('late')
        absence = request.POST.get('absence')
        income_name = request.POST.get('income_name')
        income_ammount = request.POST.get('income_ammount')
        deduction_name = request.POST.get('deduction_name')
        deduction_ammount = request.POST.get('deduction_ammount')

        # Static
        employee = get_object_or_404(Employee, id=id)
        cutoff = request.POST.get('cutoff')
        cutoff_month = request.POST.get('cutoff_month')
        cutoff_year = request.POST.get('cutoff_year')
        batch_number = request.POST.get('batch_number')

        ## Conditions here if there is this data
        ## Make this adjustment and insert to database
        ## if not
        ## Skip it dont make that empty adjustment
        ## Check the next one
        ## then status of every adjustment is Pending

        if late:
            try:
                minutes_late = float(late)
                daily_rate = float(employee.salary) / 22
                per_minute_rate = daily_rate / (8 * 60)
                late_amount = round(per_minute_rate * minutes_late, 2)
            except Exception:
                late_amount = Decimal('0.00')

            Adjustment.objects.create(
                employee=employee,
                name="Late",
                type="Deduction",
                amount=late_amount,
                details=late,
                month=cutoff_month,
                cutoff=cutoff,
                status="Waiting",
                remarks=request.POST.get('remarks', ''),
                cutoff_year=cutoff_year,
                batch_number=batch_number,
            )

        if absence:
            try:
                minutes_absent = float(absence) * 480
                daily_rate = float(employee.salary) / 22
                per_minute_rate = daily_rate / (8 * 60)
                absent_amount = round(per_minute_rate * minutes_absent, 2)
            except Exception:
                absent_amount = Decimal('0.00')

            Adjustment.objects.create(
                employee=employee,
                name="Absent",
                type="Deduction",
                amount=absent_amount,
                details=absence,
                month=cutoff_month,
                cutoff=cutoff,
                status="Waiting",
                remarks=request.POST.get('remarks', ''),
                cutoff_year=cutoff_year,
                batch_number=batch_number,
            )

        if income_name and income_ammount:
            Adjustment.objects.create(
                employee=employee,
                name=income_name,
                type="Income",
                amount=income_ammount,
                details="",
                month=cutoff_month,
                cutoff=cutoff,
                status="Waiting",
                remarks=request.POST.get('remarks', ''),
                cutoff_year=cutoff_year,
                batch_number=batch_number,
            )

        if deduction_name and deduction_ammount:
            Adjustment.objects.create(
                employee=employee,
                name=deduction_name,
                type="Deduction",
                amount=deduction_ammount,
                details="",
                month=cutoff_month,
                cutoff=cutoff,
                status="Waiting",
                remarks=request.POST.get('remarks', ''),
                cutoff_year=cutoff_year,
                batch_number=batch_number,
            )


        return JsonResponse({'status': 'OK'}, status=200)

    return JsonResponse({'error': 'Invalid request method'}, status=405)

@login_required
@restrict_roles(disallowed_roles=['employee'])
def adjustment_show(request, emp_id):
    if request.method == 'GET':
        batch_number = request.GET.get('batch_number')
        cutoff = request.GET.get('cutoff')
        cutoff_month = request.GET.get('cutoff_month')
        cutoff_year = request.GET.get('cutoff_year')

        adjustments = Adjustment.objects.filter(
            employee_id=emp_id,
            batch_number=batch_number,
            cutoff=cutoff,
            month=cutoff_month,
            cutoff_year=cutoff_year
        )

        if not adjustments.exists():
            return JsonResponse({
                'adjustments': None,
                'cutoff': cutoff,
                'cutoff_month': cutoff_month,
                'cutoff_year': cutoff_year,
                'batch_number': batch_number,
            }, status=200)

        data = list(adjustments.values())

        return JsonResponse({
            'adjustments': data,
            'cutoff': cutoff,
            'cutoff_month': cutoff_month,
            'cutoff_year': cutoff_year,
            'batch_number': batch_number,
        }, status=200)

    return JsonResponse({'error': 'Invalid request method'}, status=405)

