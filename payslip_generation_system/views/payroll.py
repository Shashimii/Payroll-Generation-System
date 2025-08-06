import json
from django.shortcuts import render, redirect, get_object_or_404
from django.db import connection
from django.db import transaction
from django.http import JsonResponse
from django.contrib import messages
from django.utils.dateparse import parse_date
from django.core.paginator import Paginator
from django.db.models import Q, Count, F, Sum, Case, When, Value, IntegerField, Exists, OuterRef
from decimal import Decimal
from datetime import datetime
from payslip_generation_system.models import Employee, BatchAssignment, Adjustment, ReturnedAdjustment, ReturnRemark
from payslip_generation_system.decorators import restrict_roles
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

        # Employees on the current payroll
        employee_ids = list(BatchAssignment.objects.filter(
            batch_number=batch_number,
            cutoff=cutoff,
            cutoff_month=cutoff_month,
            cutoff_year=cutoff_year
        ).values_list('employee_id', flat=True))

        # Employees who have submitted adjustments
        adjusted_ids = list(Adjustment.objects.filter(
            employee_id__in=employee_ids,
            cutoff=cutoff,
            month=cutoff_month,
            cutoff_year=cutoff_year
        ).values_list('employee_id', flat=True).distinct())

        # Find employees without adjustments
        missing_ids = list(set(employee_ids) - set(adjusted_ids))

        if missing_ids:
            # Optionally get full names
            missing_employees = Employee.objects.filter(id__in=missing_ids).values('id', 'fullname')
            return JsonResponse({
                'status': 'incomplete',
                'message': f'{len(missing_ids)} employee(s) have not submitted adjustments.',
                'missing_employees': list(missing_employees)
            }, status=400)

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
def approve(request):
    if request.method == 'POST':
        # Payroll information
        cutoff = request.POST.get('cutoff')
        cutoff_month = request.POST.get('cutoff_month')
        cutoff_year = request.POST.get('cutoff_year')
        batch_number = request.POST.get('batch_number')

        # Employees on the current payroll
        employee_ids = list(BatchAssignment.objects.filter(
            batch_number=batch_number,
            cutoff=cutoff,
            cutoff_month=cutoff_month,
            cutoff_year=cutoff_year
        ).values_list('employee_id', flat=True))

        # Update their adjustment statuses
        Adjustment.objects.filter(
            employee_id__in=employee_ids,
            cutoff=cutoff,
            month=cutoff_month,
            cutoff_year=cutoff_year
        ).update(status="Approved")

        return JsonResponse({'status': 'OK'}, status=200)

    return JsonResponse({'error': 'Invalid request method'}, status=405)

@login_required
@restrict_roles(disallowed_roles=['employee'])
def reject(request):
    if request.method == 'POST':
        cutoff = request.POST.get('cutoff')
        cutoff_month = request.POST.get('cutoff_month')
        cutoff_year = request.POST.get('cutoff_year')
        batch_number = request.POST.get('batch_number')
        remarks = request.POST.get('remarks')

        assignments = BatchAssignment.objects.filter(
            batch_number=batch_number,
            cutoff=cutoff,
            cutoff_month=cutoff_month,
            cutoff_year=cutoff_year
        )

        employee_ids = assignments.values_list('employee_id', flat=True)

        adjustments = Adjustment.objects.filter(
            employee_id__in=employee_ids,
            cutoff=cutoff,
            month=cutoff_month,
            cutoff_year=cutoff_year
        )

        # Save to ReturnedAdjustments
        for adj in adjustments:
            ReturnedAdjustment.objects.create(
                employee=adj.employee,
                name=adj.name,
                type=adj.type,
                amount=adj.amount,
                details=adj.details,
                month=adj.month,
                cutoff=adj.cutoff,
                cutoff_year=adj.cutoff_year,
                status="Returned",
            )
        
        # Save one remark for the batch
        ReturnRemark.objects.create(
            batch_number=batch_number,
            cutoff=cutoff,
            cutoff_month=cutoff_month,
            cutoff_year=cutoff_year,
            remark=remarks
        )

        # Update the Adjustments
        Adjustment.objects.filter(
            employee_id__in=employee_ids,
            cutoff=cutoff,
            month=cutoff_month,
            cutoff_year=cutoff_year
        ).update(status="Returned")


        return JsonResponse({'status': 'OK'}, status=200)

    return JsonResponse({'error': 'Invalid request method'}, status=405)

@login_required
@restrict_roles(disallowed_roles=['employee'])
def release(request):
    if request.method == 'POST':
        # Payroll information
        cutoff = request.POST.get('cutoff')
        cutoff_month = request.POST.get('cutoff_month')
        cutoff_year = request.POST.get('cutoff_year')
        batch_number = request.POST.get('batch_number')

        # Employees on the current payroll
        employee_ids = list(BatchAssignment.objects.filter(
            batch_number=batch_number,
            cutoff=cutoff,
            cutoff_month=cutoff_month,
            cutoff_year=cutoff_year
        ).values_list('employee_id', flat=True))

        # Update their adjustment statuses
        Adjustment.objects.filter(
            employee_id__in=employee_ids,
            cutoff=cutoff,
            month=cutoff_month,
            cutoff_year=cutoff_year
        ).update(status="Credited")

        return JsonResponse({'status': 'OK'}, status=200)

    return JsonResponse({'error': 'Invalid request method'}, status=405)

@login_required
@restrict_roles(disallowed_roles=['employee'])
def batch_data(request):
    batch_number = request.GET.get('batch_number')
    cutoff = request.GET.get('cutoff') or '1st'
    cutoff_month = request.GET.get('cutoff_month') or 'January'
    cutoff_year = int(request.GET.get('cutoff_year') or datetime.now().year)
    batch_number = int(batch_number or 1)

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
        ),
        removed_order=Case(
            When(removed='NO', then=Value(0)),
            When(removed='YES', then=Value(1)),
            default=Value(2),
            output_field=IntegerField()
        ),
        has_adjustments=Exists(
            Adjustment.objects.filter(
                employee=OuterRef('employee'),
                batch_number=batch_number,
                cutoff=cutoff,
                month=cutoff_month,
                cutoff_year=cutoff_year
            )
        )
    ).order_by('late_order', 'employee__fullname')

    employees = []

    for assignment in assignments:
        employee = assignment.employee

        # Base salary
        basic_salary = employee.salary
        basic_salary_annual = basic_salary * 12
        basic_salary_cutoff = basic_salary / 2

        # Tax
        if employee.tax_declaration.lower() == "yes":
            tax_deduction = Decimal('0.00')
        else:
            tax_deduction = basic_salary_cutoff * Decimal('0.027') if basic_salary_annual >= 250000 else Decimal('0.00')

        # Philhealth
        if employee.has_philhealth.lower() == "yes":
            philhealth = basic_salary_cutoff * Decimal('0.05') if basic_salary_cutoff > Decimal('9999') else Decimal('500')
        else:
            philhealth = Decimal('0.00')

        # Late adjustments
        late_adjustments = Adjustment.objects.filter(
            employee=employee,
            name="Late",
            month=cutoff_month,
            cutoff=cutoff,
            cutoff_year=cutoff_year,
            status__in=["Pending", "Approved", "Credited"]
        )
        late_amt_total = late_adjustments.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
        late_min_total = late_adjustments.aggregate(Sum('details'))['details__sum'] or Decimal('0.00')

        # Absent adjustments
        absent_adjustments = Adjustment.objects.filter(
            employee=employee,
            name="Late",
            month=cutoff_month,
            cutoff=cutoff,
            cutoff_year=cutoff_year,
            status__in=["Pending", "Approved", "Credited"]
        )

        absent_amt_total = absent_adjustments.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
        absent_min_total = absent_adjustments.aggregate(Sum('details'))['details__sum'] or Decimal('0.00')

        # Other deductions
        other_deductions = Adjustment.objects.filter(
            employee=employee,
            type="Deduction",
            month=cutoff_month,
            cutoff=cutoff,
            cutoff_year=cutoff_year,
            status__in=["Pending", "Approved", "Credited"]
        ).exclude(name__in=["Late", "Absent"])
        total_other_deductions = other_deductions.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')

        # Incomes
        incomes = Adjustment.objects.filter(
            employee=employee,
            type="Income",
            month=cutoff_month,
            cutoff=cutoff,
            cutoff_year=cutoff_year,
            status__in=["Pending", "Approved", "Credited"]
        )
        total_income = incomes.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')

        # Final calculation
        total_deductions = tax_deduction + philhealth + late_amt_total + total_other_deductions
        net_salary = basic_salary_cutoff - total_deductions + total_income

        # Build data
        emp_data = model_to_dict(employee, fields=[
            'id', 'employee_number', 'fullname', 'position', 'salary', 'tax_declaration'
        ])
        emp_data['late_assigned'] = assignment.late_assigned
        emp_data['removed'] = assignment.removed
        emp_data['has_adjustments'] = assignment.has_adjustments
        emp_data['basic_salary_cutoff'] = f"{basic_salary_cutoff:.2f}"
        emp_data['tax_deduction'] = f"{tax_deduction:.2f}"
        emp_data['philhealth'] = f"{philhealth:.2f}"
        emp_data['late_amount'] = f"{late_amt_total:.2f}"
        emp_data['late_minutes'] = f"{late_min_total:.2f}"
        emp_data['absent_amount'] = f"{absent_amt_total:.2f}"
        emp_data['absent_minutes'] = f"{absent_min_total:.2f}"
        emp_data['other_deductions'] = f"{total_other_deductions:.2f}"
        emp_data['total_deductions'] = f"{total_deductions:.2f}"
        emp_data['income'] = f"{total_income:.2f}"
        emp_data['net_salary'] = f"{net_salary:.2f}"

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
def batch_remove(request):
    if request.method == 'POST':
        employee_id = request.POST.get('employee_id')
        employee = get_object_or_404(Employee, id=employee_id)
        cutoff = request.POST.get('cutoff')
        cutoff_month = request.POST.get('cutoff_month')
        cutoff_year = request.POST.get('cutoff_year')
        batch_number = request.POST.get('batch_number')

        ## Same logic on the late

        # Get existing batch_number before changing
        previous_batch = BatchAssignment.objects.filter(
            employee=employee,
            cutoff=cutoff,
            cutoff_month=cutoff_month,
            cutoff_year=cutoff_year,
        ).values_list('batch_number', flat=True).first()

        # Set the batch number to 0
        batch_number = 0

        # Update or create the batch assignment of employee
        BatchAssignment.objects.update_or_create(
            employee=employee,
            cutoff=cutoff,
            cutoff_month=cutoff_month,
            cutoff_year=cutoff_year,
            defaults={
                'batch_number': batch_number,
                'removed': 'YES',
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
def batch_unremove(request):
    if request.method == 'POST':
        employee_id = request.POST.get('employee_id')
        employee = get_object_or_404(Employee, id=employee_id)
        cutoff = request.POST.get('cutoff')
        cutoff_month = request.POST.get('cutoff_month')
        cutoff_year = request.POST.get('cutoff_year')

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
                'removed': 'NO',
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

@login_required
@restrict_roles(disallowed_roles=['employee'])
def adjustment_update(request):
    if request.method == 'POST':
        try:
            adjustments = json.loads(request.POST.get('adjustments', '[]'))
            for adj in adjustments:
                Adjustment.objects.filter(id=adj['id']).update(
                    name=adj['name'],
                    type=adj['type'],
                    amount=adj['amount']
                )
            return JsonResponse({'status': 'OK'}, status=200)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Invalid request method'}, status=405)

@login_required
@restrict_roles(disallowed_roles=['employee'])
def pending(request):
    return render(request, 'payroll/pending.html')

@login_required
@restrict_roles(disallowed_roles=['employee'])
def data(request):
    # Get all batches
    all_batches = BatchAssignment.objects.values(
        'batch_number',
        'cutoff',
        'cutoff_month',
        'cutoff_year'
    ).distinct()

    valid_batches = []

    for batch in all_batches:
        # Get all employee IDs in this batch
        employee_ids = BatchAssignment.objects.filter(
            batch_number=batch['batch_number'],
            cutoff=batch['cutoff'],
            cutoff_month=batch['cutoff_month'],
            cutoff_year=batch['cutoff_year']
        ).values_list('employee_id', flat=True)

        # Count how many of them have at least one Pending adjustment
        pending_adjustments = Adjustment.objects.filter(
            employee_id__in=employee_ids,
            cutoff=batch['cutoff'],
            month=batch['cutoff_month'],
            cutoff_year=batch['cutoff_year'],
            status="Pending"
        ).values('employee_id').distinct().count()

        # Only include the batch if ALL employees have Pending adjustments
        if pending_adjustments == len(employee_ids):
            valid_batches.append(batch)

    return JsonResponse({'batches': valid_batches}, status=200)

def show(request):
    context = {
        'cutoff': request.GET.get('cutoff'),
        'cutoff_month': request.GET.get('cutoff_month'),
        'cutoff_year': request.GET.get('cutoff_year'),
        'batch_number': request.GET.get('batch_number'),
    }
    return render(request, 'payroll/view.html', context)

@login_required
@restrict_roles(disallowed_roles=['employee'])
def approved_list(request):
    return render(request, 'payroll/approve.html')

@login_required
@restrict_roles(disallowed_roles=['employee'])
def approve_data(request):
    # Get all batches
    all_batches = BatchAssignment.objects.values(
        'batch_number',
        'cutoff',
        'cutoff_month',
        'cutoff_year'
    ).distinct()

    valid_batches = []

    for batch in all_batches:
        # Get all employee IDs in this batch
        employee_ids = BatchAssignment.objects.filter(
            batch_number=batch['batch_number'],
            cutoff=batch['cutoff'],
            cutoff_month=batch['cutoff_month'],
            cutoff_year=batch['cutoff_year']
        ).values_list('employee_id', flat=True)

        # Count how many of them have at least one Pending adjustment
        pending_adjustments = Adjustment.objects.filter(
            employee_id__in=employee_ids,
            cutoff=batch['cutoff'],
            month=batch['cutoff_month'],
            cutoff_year=batch['cutoff_year'],
            status="Approved"
        ).values('employee_id').distinct().count()

        # Only include the batch if ALL employees have Pending adjustments
        if pending_adjustments == len(employee_ids):
            valid_batches.append(batch)

    return JsonResponse({'batches': valid_batches}, status=200)


@login_required
@restrict_roles(disallowed_roles=['employee'])
def approve_show(request):
    context = {
        'cutoff': request.GET.get('cutoff'),
        'cutoff_month': request.GET.get('cutoff_month'),
        'cutoff_year': request.GET.get('cutoff_year'),
        'batch_number': request.GET.get('batch_number'),
    }
    return render(request, 'payroll/releasing.html', context)

@login_required
@restrict_roles(disallowed_roles=['employee'])
def removed_employee_data(request):
    cutoff = request.GET.get('cutoff') or '1st'
    cutoff_month = request.GET.get('cutoff_month') or 'January'
    cutoff_year = int(request.GET.get('cutoff_year') or datetime.now().year)
    batch_number = 0
    removed= 'YES'

    # Get employees assigned to this batch
    assignments = BatchAssignment.objects.filter(
        cutoff=cutoff,
        cutoff_month=cutoff_month,
        cutoff_year=cutoff_year,
        batch_number=batch_number,
        removed=removed
    ).select_related('employee')

    employees = []

    for a in assignments:
        emp = a.employee

        employees.append({
            'id': emp.id,
            'employee_number': emp.employee_number,
            'fullname': emp.fullname,
            'position': emp.position,
            'salary': float(emp.salary),
            'tax_declaration': emp.tax_declaration,
            'removed': a.removed
        })

    print(employees)

    return JsonResponse({
        'employees': employees,
        'cutoff': cutoff,
        'cutoff_month': cutoff_month,
        'cutoff_year': cutoff_year,
        'batch_number': batch_number,
    })