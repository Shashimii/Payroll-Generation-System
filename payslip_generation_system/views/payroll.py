import json
from django.shortcuts import render, redirect, get_object_or_404
from django.db import connection
from django.db import transaction
from django.http import JsonResponse
from django.contrib import messages
from django.core.exceptions import ValidationError
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
    batches = BatchAssignment.objects.exclude(batch_number=0)\
        .values_list('batch_number', flat=True).distinct().order_by('batch_number')

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

        # Remove the ReturnRemark if it exists
        ReturnRemark.objects.filter(
            cutoff=cutoff,
            cutoff_month=cutoff_month,
            cutoff_year=cutoff_year,
            batch_number=batch_number
        ).delete()

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

    has_pending_adjustments = Adjustment.objects.filter(
        batch_number=batch_number,
        cutoff=cutoff,
        month=cutoff_month,
        cutoff_year=cutoff_year,
        status="Pending"
    ).exists()

    has_approved_adjustments = Adjustment.objects.filter(
        batch_number=batch_number,
        cutoff=cutoff,
        month=cutoff_month,
        cutoff_year=cutoff_year,
        status="Approved"
    ).exists()

    has_credited_adjustments = Adjustment.objects.filter(
        batch_number=batch_number,
        cutoff=cutoff,
        month=cutoff_month,
        cutoff_year=cutoff_year,
        status="Credited"
    ).exists()

    remark = ReturnRemark.objects.filter(
        batch_number=batch_number,
        cutoff=cutoff,
        cutoff_month=cutoff_month,
        cutoff_year=cutoff_year
    ).values_list('remark', flat=True).first()

    employees = []

    for assignment in assignments:
        employee = assignment.employee

        # Base salary
        basic_salary = employee.salary
        basic_salary_annual = basic_salary * 12
        basic_salary_cutoff = basic_salary / 2

        # Tax - use TAX adjustment as percentage for salary-based computation
        tax_adjustments = Adjustment.objects.filter(
            employee=employee,
            name="TAX",
            month=cutoff_month,
            cutoff=cutoff,
            cutoff_year=cutoff_year,
            status__in=["Pending", "Approved", "Credited"]
        )
        tax_percentage = tax_adjustments.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
        
        # Apply tax calculation logic with custom percentage or default
        tax_deduction = basic_salary_cutoff * (tax_percentage / 100)

        # Philhealth - fetch from Philhealth adjustments
        philhealth_adjustments = Adjustment.objects.filter(
            employee=employee,
            name="Philhealth",
            month=cutoff_month,
            cutoff=cutoff,
            cutoff_year=cutoff_year,
            status__in=["Pending", "Approved", "Credited"]
        )
        philhealth = philhealth_adjustments.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')

        # SSS - fetch from SSS adjustments
        sss_adjustments = Adjustment.objects.filter(
            employee=employee,
            name="SSS",
            month=cutoff_month,
            cutoff=cutoff,
            cutoff_year=cutoff_year,
            status__in=["Pending", "Approved", "Credited"]
        )
        sss = sss_adjustments.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')

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
        ).exclude(name__in=["Late", "Absent", "TAX", "Philhealth", "SSS"])
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

        # Get detailed incomes and deductions for breakdown
        detailed_incomes = list(incomes.values('name', 'amount', 'details'))
        detailed_deductions = list(other_deductions.values('name', 'amount', 'details'))

        # Final calculation
        total_deductions = tax_deduction + philhealth + sss + late_amt_total + absent_amt_total + total_other_deductions
        net_salary = basic_salary_cutoff - total_deductions + total_income

        # Check if the employee's previous batch has been submitted (for removed employees)
        previous_batch = assignment.previous_batch
        previous_batch_submitted = False
        
        if previous_batch is not None:
            # Check if the previous batch has any adjustments with status Pending, Approved, or Credited
            previous_batch_submitted = Adjustment.objects.filter(
                batch_number=previous_batch,
                cutoff=cutoff,
                month=cutoff_month,
                cutoff_year=cutoff_year,
                status__in=["Pending", "Approved", "Credited"]
            ).exists()

        # Build data
        emp_data = model_to_dict(employee, fields=[
            'id', 'employee_number', 'fullname', 'position', 'salary', 'tax_declaration'
        ])
        emp_data['late_assigned'] = assignment.late_assigned
        emp_data['removed'] = assignment.removed
        emp_data['has_adjustments'] = assignment.has_adjustments
        emp_data['previous_batch'] = previous_batch
        emp_data['previous_batch_submitted'] = previous_batch_submitted
        emp_data['basic_salary_cutoff'] = f"{basic_salary_cutoff:.2f}"
        emp_data['tax_deduction'] = f"{tax_deduction:.2f}"
        emp_data['philhealth'] = f"{philhealth:.2f}"
        emp_data['sss'] = f"{sss:.2f}"
        emp_data['late_amount'] = f"{late_amt_total:.2f}"
        emp_data['late_minutes'] = f"{late_min_total:.2f}"
        emp_data['absent_amount'] = f"{absent_amt_total:.2f}"
        emp_data['absent_minutes'] = f"{absent_min_total:.2f}"
        emp_data['other_deductions'] = f"{total_other_deductions:.2f}"
        emp_data['total_deductions'] = f"{total_deductions:.2f}"
        emp_data['income'] = f"{total_income:.2f}"
        emp_data['net_salary'] = f"{net_salary:.2f}"
        emp_data['incomes'] = detailed_incomes
        emp_data['deductions'] = detailed_deductions

        employees.append(emp_data)

    return JsonResponse({
        'employees': employees,
        'cutoff': cutoff,
        'cutoff_month': cutoff_month,
        'cutoff_year': cutoff_year,
        'batch_number': batch_number,
        'has_pending_adjustments': has_pending_adjustments,
        'has_approved_adjustments': has_approved_adjustments,
        'has_credited_adjustments': has_credited_adjustments,
        'remark': remark or "", 
    })

@login_required
@restrict_roles(disallowed_roles=['employee'])
def batch_create(request, batch_size=15):
    cutoff = request.POST.get('cutoff')
    cutoff_month = request.POST.get('cutoff_month')
    cutoff_year = request.POST.get('cutoff_year')

    if not cutoff or not cutoff_month or not cutoff_year:
        return JsonResponse({'error': 'Missing cutoff, month, or year.'}, status=400)

    # Check if batches already exist for the given period
    if BatchAssignment.objects.filter(
        cutoff=cutoff,
        cutoff_month=cutoff_month,
        cutoff_year=cutoff_year
    ).exists():
        return JsonResponse({
            'error': f'Batches already exist for {cutoff_month} {cutoff}, {cutoff_year}.'
        }, status=400)

    # Get all employees grouped by assigned office
    employees_by_office = {}
    all_employees = Employee.objects.order_by('fullname')
    
    for employee in all_employees:
        office = employee.assigned_office or 'unassigned'
        if office not in employees_by_office:
            employees_by_office[office] = []
        employees_by_office[office].append(employee)

    # Check if there are employees to assign
    if not all_employees.exists():
        return JsonResponse({'error': 'No employees found to create batches.'}, status=400)

    total_batches_created = 0
    
    # Create batches for each office separately
    for office, employees in employees_by_office.items():
        if not employees:  # Skip if no employees in this office
            continue
            
        batch_number = 1
        
        for index, employee in enumerate(employees, start=1):
            BatchAssignment.objects.create(
                employee=employee,
                batch_number=batch_number,
                cutoff=cutoff,
                cutoff_month=cutoff_month,
                cutoff_year=cutoff_year,
                assigned_office=employee.assigned_office
            )

            if index % batch_size == 0:
                batch_number += 1
        
        total_batches_created += batch_number - 1 if batch_number > 1 else 1

    return JsonResponse({
        'message': f'Batches successfully created for {cutoff_month} {cutoff}, {cutoff_year}. '
                   f'Total batches created: {total_batches_created} across all offices.'
    })

@login_required
@restrict_roles(disallowed_roles=['employee'])
def batch_delete(request):
    cutoff_month = request.POST.get('cutoff_month')
    cutoff = request.POST.get('cutoff')
    cutoff_year = request.POST.get('cutoff_year')

    if not (cutoff_month and cutoff and cutoff_year):
        return JsonResponse({'error': 'Missing required data'}, status=400)
    
    try:
        batch_deleted, _ = BatchAssignment.objects.filter(
            cutoff_month=cutoff_month,
            cutoff=cutoff,
            cutoff_year=cutoff_year
        ).delete()

        adj_deleted, _ = Adjustment.objects.filter(
            month=cutoff_month,
            cutoff=cutoff,
            cutoff_year=cutoff_year
        ).delete()

        remark_deleted, _ = ReturnRemark.objects.filter(
            cutoff_month=cutoff_month,
            cutoff=cutoff,
            cutoff_year=cutoff_year
        ).delete()

        if batch_deleted == 0 and adj_deleted == 0 and remark_deleted == 0:
            return JsonResponse({'error': 'No matching records found'}, status=404)

        return JsonResponse({
            'message': f'{batch_deleted} batch assignments, '
                       f'{adj_deleted} adjustments, and '
                       f'{remark_deleted} return remarks removed successfully.'
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

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
        ## If employee is marked as late in the last existing batch, move them to a new batch
        ## Otherwise, move them to the last batch if it's not full, or create a new batch if it is

        # Get existing batch_number before changing
        previous_batch = BatchAssignment.objects.filter(
            employee=employee,
            cutoff=cutoff,
            cutoff_month=cutoff_month,
            cutoff_year=cutoff_year,
        ).values_list('batch_number', flat=True).first()

        # Get the last batch number for the selected payroll period and office
        last_batch = (
            BatchAssignment.objects
            .filter(
                cutoff=cutoff, 
                cutoff_month=cutoff_month, 
                cutoff_year=cutoff_year,
                assigned_office=employee.assigned_office
            )
            .order_by('-batch_number') # desc
            .first()
        )

        if last_batch:
            last_batch_number = last_batch.batch_number
            
            # Check if the employee is currently in the last batch
            if previous_batch == last_batch_number:
                # Employee is in the last batch, so mark them as late in a NEW batch
                batch_number = last_batch_number + 1
            else:
                # Employee is not in the last batch, so move them to the last batch
                # Count the number of employees on the last batch for this office
                count = BatchAssignment.objects.filter(
                    cutoff=cutoff,
                    cutoff_month=cutoff_month,
                    cutoff_year=cutoff_year,
                    batch_number=last_batch_number,
                    assigned_office=employee.assigned_office
                ).count()

                if count < 15:
                    # If last batch not full, move to the last batch
                    batch_number = last_batch_number
                else:
                    # If last batch full, create new batch
                    batch_number = last_batch_number + 1
        else:
            # No existing batches for this office, create first batch
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
                'assigned_office': employee.assigned_office,
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
                'assigned_office': employee.assigned_office,
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
                'assigned_office': employee.assigned_office,
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
                'assigned_office': employee.assigned_office,
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
        employee = get_object_or_404(Employee, id=emp_id)

        late = request.POST.get('late')
        absence = request.POST.get('absence')
        philhealth = request.POST.get('philhealth')
        sss = request.POST.get('sss')
        tax = request.POST.get('tax')
        late_id = request.POST.get('late_id')
        absence_id = request.POST.get('absence_id')
        philhealth_id = request.POST.get('philhealth_id')
        sss_id = request.POST.get('sss_id')
        tax_id = request.POST.get('tax_id')
        deleted_ids = request.POST.getlist('deleted_ids[]')

        # Get multiple income and deduction data
        import json
        incomes_data = request.POST.get('incomes', '[]')
        deductions_data = request.POST.get('deductions', '[]')
        
        try:
            incomes = json.loads(incomes_data) if incomes_data else []
            deductions = json.loads(deductions_data) if deductions_data else []
        except json.JSONDecodeError:
            incomes = []
            deductions = []

        cutoff = request.POST.get('cutoff')
        cutoff_month = request.POST.get('cutoff_month')
        cutoff_year = request.POST.get('cutoff_year')
        batch_number = request.POST.get('batch_number')
        remarks = request.POST.get('remarks', '')

        # ## Conditions here if there is this data
        # ## Make this adjustment and insert to database
        # ## if not
        # ## Skip it dont make that empty adjustment
        # ## Check the next one
        # ## then status of every adjustment is Pending

        def parse_decimal(val):
            try:
                return Decimal(val)
            except:
                return Decimal('0.00')

        if deleted_ids:
            try:
                Adjustment.objects.filter(id__in=deleted_ids).delete()
            except (ValueError, ValidationError):
                pass 

        def save_adjustment(adj_id, name, adj_type, amount, details=''):
            if not name or amount in [None, '', 'null']:
                return

            amount = parse_decimal(amount)

            if adj_id:
                try:
                    adjustment = Adjustment.objects.get(id=adj_id)
                    adjustment.name = name
                    adjustment.type = adj_type
                    adjustment.amount = amount
                    adjustment.details = details
                    adjustment.status = 'Waiting'
                    adjustment.remarks = remarks
                    adjustment.save()
                except Adjustment.DoesNotExist:
                    # If ID is invalid (not found), fallback to create new
                    Adjustment.objects.create(
                        employee=employee,
                        name=name,
                        type=adj_type,
                        amount=amount,
                        details=details,
                        status='Waiting',
                        remarks=remarks,
                        cutoff=cutoff,
                        month=cutoff_month,
                        cutoff_year=cutoff_year,
                        batch_number=batch_number
                    )
            else:
                # Create new if no ID provided
                Adjustment.objects.create(
                    employee=employee,
                    name=name,
                    type=adj_type,
                    amount=amount,
                    details=details,
                    status='Waiting',
                    remarks=remarks,
                    cutoff=cutoff,
                    month=cutoff_month,
                    cutoff_year=cutoff_year,
                    batch_number=batch_number
                )

        # Save Late
        if late:
            try:
                minutes_late = float(late)
                daily_rate = float(employee.salary) / 22
                per_minute_rate = daily_rate / (8 * 60)
                late_amount = round(per_minute_rate * minutes_late, 2)
            except Exception:
                late_amount = Decimal('0.00')

            save_adjustment(late_id, 'Late', 'Deduction', late_amount, details=late)

        # Save Absent
        if absence:
            try:
                minutes_absent = float(absence) * 480
                daily_rate = float(employee.salary) / 22
                per_minute_rate = daily_rate / (8 * 60)
                absent_amount = round(per_minute_rate * minutes_absent, 2)
            except Exception:
                absent_amount = Decimal('0.00')

            save_adjustment(absence_id, 'Absent', 'Deduction', absent_amount, details=absence)

        # Save Philhealth
        if philhealth:
            save_adjustment(philhealth_id, 'Philhealth', 'Deduction', philhealth)

        # Save SSS
        if sss:
            save_adjustment(sss_id, 'SSS', 'Deduction', sss)

        # Save TAX
        if tax:
            save_adjustment(tax_id, 'TAX', 'Deduction', tax)

        # Save multiple Income adjustments
        for income in incomes:
            if income.get('name') and income.get('amount'):
                save_adjustment(None, income['name'], 'Income', income['amount'])

        # Save multiple Deduction adjustments
        for deduction in deductions:
            if deduction.get('name') and deduction.get('amount'):
                save_adjustment(None, deduction['name'], 'Deduction', deduction['amount'])

        return JsonResponse({
            'status': 'OK',
            'message': f'Processed {len(incomes)} income and {len(deductions)} deduction adjustments'
        }, status=200)

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

    # Get employees assigned to this batch first
    assignments = BatchAssignment.objects.filter(
        cutoff=cutoff,
        cutoff_month=cutoff_month,
        cutoff_year=cutoff_year,
        batch_number=batch_number,
        removed=removed
    ).select_related('employee')

    # Get the employee IDs for removed employees
    removed_employee_ids = [a.employee.id for a in assignments]

    # Check for adjustment statuses for removed employees
    has_pending_adjustments = Adjustment.objects.filter(
        employee_id__in=removed_employee_ids,
        cutoff=cutoff,
        month=cutoff_month,
        cutoff_year=cutoff_year,
        status="Pending"
    ).exists()

    has_approved_adjustments = Adjustment.objects.filter(
        employee_id__in=removed_employee_ids,
        cutoff=cutoff,
        month=cutoff_month,
        cutoff_year=cutoff_year,
        status="Approved"
    ).exists()

    has_credited_adjustments = Adjustment.objects.filter(
        employee_id__in=removed_employee_ids,
        cutoff=cutoff,
        month=cutoff_month,
        cutoff_year=cutoff_year,
        status="Credited"
    ).exists()

    employees = []

    for a in assignments:
        emp = a.employee
        
        # Check if the employee's previous batch has been submitted
        previous_batch = a.previous_batch
        previous_batch_submitted = False
        
        if previous_batch is not None:
            # Check if the previous batch has any adjustments with status Pending, Approved, or Credited
            previous_batch_submitted = Adjustment.objects.filter(
                batch_number=previous_batch,
                cutoff=cutoff,
                month=cutoff_month,
                cutoff_year=cutoff_year,
                status__in=["Pending", "Approved", "Credited"]
            ).exists()

        employees.append({
            'id': emp.id,
            'employee_number': emp.employee_number,
            'fullname': emp.fullname,
            'position': emp.position,
            'salary': float(emp.salary),
            'tax_declaration': emp.tax_declaration,
            'removed': a.removed,
            'previous_batch': previous_batch,
            'previous_batch_submitted': previous_batch_submitted
        })

    print(employees)

    return JsonResponse({
        'employees': employees,
        'cutoff': cutoff,
        'cutoff_month': cutoff_month,
        'cutoff_year': cutoff_year,
        'batch_number': batch_number,
        'has_pending_adjustments': has_pending_adjustments,
        'has_approved_adjustments': has_approved_adjustments,
        'has_credited_adjustments': has_credited_adjustments,
    })