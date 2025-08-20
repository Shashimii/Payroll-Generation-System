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
from payslip_generation_system.models import Employee, BatchAssignment, Adjustment, ReturnedAdjustment, ReturnRemark, Batch
from payslip_generation_system.decorators import restrict_roles
from django.forms.models import model_to_dict

from django.contrib.auth.decorators import login_required

def get_user_assigned_office(user_role):
    """
    Helper function to get the assigned office based on user role
    """
    role_to_office = {
        'preparator_denr_nec': 'denr_ncr_nec',
        'preparator_denr_prcmo': 'denr_ncr_prcmo',
        'preparator_meo_s': 'meo_s',
        'preparator_meo_e': 'meo_e',
        'preparator_meo_w': 'meo_w',
        'preparator_meo_n': 'meo_n',
    }
    return role_to_office.get(user_role)

def get_formatted_office_name(office_code):
    """
    Helper function to get formatted office name from office code
    """
    office_name_map = {
        'denr_ncr_nec': 'DENR NCR NEC',
        'denr_ncr_prcmo': 'DENR NCR PRCMO',
        'meo_s': 'MEO South',
        'meo_e': 'MEO East',
        'meo_w': 'MEO West',
        'meo_n': 'MEO North',
    }
    return office_name_map.get(office_code, office_code)

def get_payroll_title(office_code):
    """
    Helper function to get the payroll title based on office
    """
    if not office_code:
        return "General Payroll DENR NCR"
    
    office_name_map = {
        'denr_ncr_nec': 'General Payroll DENR NCR NEC',
        'denr_ncr_prcmo': 'General Payroll DENR NCR PRCMO',
        'meo_s': 'General Payroll DENR NCR MEO South',
        'meo_e': 'General Payroll DENR NCR MEO East',
        'meo_w': 'General Payroll DENR NCR MEO West',
        'meo_n': 'General Payroll DENR NCR MEO North',
    }
    return office_name_map.get(office_code, "General Payroll DENR NCR")

@login_required
@restrict_roles(disallowed_roles=['employee'])
def index(request):
    months = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]

    years = list(range(2020, 2031))

    # Get user role and filter batches accordingly
    user_role = request.session.get('role', '')
    
    # Get assigned office for the current user
    assigned_office = get_user_assigned_office(user_role)

    # Provide batches from Batch model, filtered by office when applicable
    if assigned_office and user_role not in ['admin', 'checker']:
        batch_rows = Batch.objects.filter(batch_assigned_office=assigned_office)
    else:
        batch_rows = Batch.objects.all()

    # Order and map to minimal dicts
    batches = list(
        batch_rows.order_by('batch_number').values('batch_number', 'batch_name')
    )

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

        # Get user role and filter batches accordingly
        user_role = request.session.get('role', '')
        
        # Get assigned office for the current user
        assigned_office = get_user_assigned_office(user_role)
        
        # Filter batch assignments based on user role
        batch_assignments = BatchAssignment.objects.filter(
            batch_number=batch_number,
            cutoff=cutoff,
            cutoff_month=cutoff_month,
            cutoff_year=cutoff_year
        )
        
        if assigned_office and user_role != 'admin' and user_role != 'checker':
            # For office-specific preparators, filter by their assigned office
            batch_assignments = batch_assignments.filter(assigned_office=assigned_office)
        
        # Employees on the current payroll
        employee_ids = list(batch_assignments.values_list('employee_id', flat=True))

        # Get the assigned_office for this batch
        batch_assigned_office = None
        if batch_assignments.exists():
            batch_assigned_office = batch_assignments.first().assigned_office

        # Employees who have submitted adjustments (filter by assigned_office)
        adjustment_filter = {
            'employee_id__in': employee_ids,
            'cutoff': cutoff,
            'month': cutoff_month,
            'cutoff_year': cutoff_year
        }
        if batch_assigned_office:
            adjustment_filter['assigned_office'] = batch_assigned_office

        adjusted_ids = list(Adjustment.objects.filter(**adjustment_filter).values_list('employee_id', flat=True).distinct())

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

        # Update their adjustment statuses (filter by assigned_office)
        Adjustment.objects.filter(**adjustment_filter).update(status="Pending")

        # Get user role and assigned office for remark removal
        user_role = request.session.get('role', '')
        assigned_office = get_user_assigned_office(user_role)
        
        # Remove the ReturnRemark if it exists (filter by assigned_office for preparators)
        remark_filter = {
            'cutoff': cutoff,
            'cutoff_month': cutoff_month,
            'cutoff_year': cutoff_year,
            'batch_number': batch_number
        }
        
        # For office-specific preparators, only remove remarks for their assigned office
        if assigned_office and user_role != 'admin' and user_role != 'checker':
            remark_filter['assigned_office'] = assigned_office
        
        ReturnRemark.objects.filter(**remark_filter).delete()

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
        assigned_office = request.POST.get('assigned_office')

        # Employees on the current payroll
        employee_ids = list(BatchAssignment.objects.filter(
            batch_number=batch_number,
            cutoff=cutoff,
            cutoff_month=cutoff_month,
            cutoff_year=cutoff_year,
            assigned_office=assigned_office
        ).values_list('employee_id', flat=True))

        # Update their adjustment statuses
        Adjustment.objects.filter(
            employee_id__in=employee_ids,
            cutoff=cutoff,
            month=cutoff_month,
            cutoff_year=cutoff_year,
            assigned_office=assigned_office
        ).update(status="Approved")

        return JsonResponse({'status': 'OK'}, status=200)

    return JsonResponse({'error': 'Invalid request method'}, status=405)

# Will Be Refactored Soon - Shashimii@08172025
@login_required
@restrict_roles(disallowed_roles=['employee'])
def reject(request):
    if request.method == 'POST':
        cutoff = request.POST.get('cutoff')
        cutoff_month = request.POST.get('cutoff_month')
        cutoff_year = request.POST.get('cutoff_year')
        batch_number = request.POST.get('batch_number')
        remarks = request.POST.get('remarks')
        assigned_office = request.POST.get('assigned_office')

        assignments = BatchAssignment.objects.filter(
            batch_number=batch_number,
            cutoff=cutoff,
            cutoff_month=cutoff_month,
            cutoff_year=cutoff_year,
            assigned_office=assigned_office
        )

        employee_ids = assignments.values_list('employee_id', flat=True)

        adjustments = Adjustment.objects.filter(
            employee_id__in=employee_ids,
            cutoff=cutoff,
            month=cutoff_month,
            cutoff_year=cutoff_year,
            assigned_office=assigned_office
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
                assigned_office=assigned_office,
                status="Returned",
            )
        
        # Save one remark for the batch
        ReturnRemark.objects.create(
            batch_number=batch_number,
            cutoff=cutoff,
            cutoff_month=cutoff_month,
            cutoff_year=cutoff_year,
            assigned_office=assigned_office,
            remark=remarks
        )

        # Update the Adjustments
        Adjustment.objects.filter(
            employee_id__in=employee_ids,
            cutoff=cutoff,
            month=cutoff_month,
            cutoff_year=cutoff_year,
            assigned_office=assigned_office
        ).update(status="Returned")


        return JsonResponse({'status': 'OK'}, status=200)

    return JsonResponse({'error': 'Invalid request method'}, status=405)
# Will Be Refactored Soon - Shashimii@08172025 End

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
    
    # Get assigned_office from URL if coming from pending page
    url_assigned_office = request.GET.get('assigned_office')

    # Get user role and filter batches accordingly
    user_role = request.session.get('role', '')
    
    # Get assigned office for the current user
    assigned_office = get_user_assigned_office(user_role)
    
    # If we have url_assigned_office (coming from pending page), filter by employees with pending or approved adjustments for that office
    if url_assigned_office:
        # Get employees with pending or approved adjustments for the specific assigned_office
        # For checker role, show both pending and approved adjustments
        status_filter = ["Pending"]
        if user_role in ['admin', 'checker', 'accounting']:
            status_filter.append("Approved")
            
        employees_with_adjustments = Adjustment.objects.filter(
            batch_number=batch_number,
            cutoff=cutoff,
            month=cutoff_month,
            cutoff_year=cutoff_year,
            status__in=status_filter,
            assigned_office=url_assigned_office
        ).values_list('employee_id', flat=True).distinct()
        
        # Filter assignments to only include employees with pending or approved adjustments for the specific office
        assignments = BatchAssignment.objects.filter(
            batch_number=batch_number,
            cutoff=cutoff,
            cutoff_month=cutoff_month,
            cutoff_year=cutoff_year,
            employee_id__in=employees_with_adjustments,
            assigned_office=url_assigned_office
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
                    cutoff_year=cutoff_year,
                    assigned_office=url_assigned_office
                )
            )
        ).order_by('late_order', 'employee__fullname')
        batch_assigned_office = url_assigned_office
    else:
        # Filter assignments based on user role
        if assigned_office and user_role not in ['admin', 'checker', 'accounting']:
            # For office-specific preparators, show only their office batches
            assignments = BatchAssignment.objects.filter(
                batch_number=batch_number,
                cutoff=cutoff,
                cutoff_month=cutoff_month,
                cutoff_year=cutoff_year,
                assigned_office=assigned_office
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
            batch_assigned_office = assigned_office
        else:
            # For admin and checker, show all batches
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
            batch_assigned_office = None

    # Get the assigned_office for this batch (all employees in a batch should have the same assigned_office)
    # batch_assigned_office = None
    # if assignments.exists():
    #     batch_assigned_office = assignments.first().assigned_office

    # Use url_assigned_office if available, otherwise use batch_assigned_office
    office_to_check = url_assigned_office if url_assigned_office else assigned_office

    # Filter adjustment status checks by assigned_office
    adjustment_filter = {
        'batch_number': batch_number,
        'cutoff': cutoff,
        'month': cutoff_month,
        'cutoff_year': cutoff_year,
    }
    
    # Only filter by assigned_office if we have a specific office to check
    if office_to_check:
        adjustment_filter['assigned_office'] = office_to_check
    
    has_pending_adjustments = Adjustment.objects.filter(
        **adjustment_filter,
        status="Pending"
    ).exists()

    has_approved_adjustments = Adjustment.objects.filter(
        **adjustment_filter,
        status="Approved"
    ).exists()

    has_credited_adjustments = Adjustment.objects.filter(
        **adjustment_filter,
        status="Credited"
    ).exists()

    # Filter remarks based on user role and assigned office
    remark_query = ReturnRemark.objects.filter(
        batch_number=batch_number,
        cutoff=cutoff,
        cutoff_month=cutoff_month,
        cutoff_year=cutoff_year
    )
    
    # Apply assigned_office filter based on user role
    if url_assigned_office:
        # If coming from pending page, filter by the specific office
        remark_query = remark_query.filter(assigned_office=url_assigned_office)
    elif assigned_office and user_role != 'admin' and user_role != 'checker':
        # For office-specific preparators, only show remarks for their assigned office
        remark_query = remark_query.filter(assigned_office=assigned_office)
    # For admin and checker, show all remarks (no additional filter)
    
    remark = remark_query.values_list('remark', flat=True).first()

    employees = []

    for assignment in assignments:
        employee = assignment.employee

        # Base salary
        basic_salary = employee.salary
        basic_salary_annual = basic_salary * 12
        basic_salary_cutoff = basic_salary / 2

        # Tax - use TAX adjustment as percentage for salary-based computation
        # tax_adjustments = Adjustment.objects.filter(
        #     employee=employee,
        #     name="TAX",
        #     month=cutoff_month,
        #     cutoff=cutoff,
        #     cutoff_year=cutoff_year,
        #     status__in=["Pending", "Approved", "Credited"]
        # )
        # if url_assigned_office:
        #     tax_adjustments = tax_adjustments.filter(assigned_office=url_assigned_office)
        # tax_percentage = tax_adjustments.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
        
        # TAX DEDUCTION 
        if (employee.tax_declaration == "yes"):
                tax_deduction = Decimal('0.00')
        else:
            tax_deduction = basic_salary_cutoff * Decimal('0.03') # TAX

        # Philhealth - fetch from Philhealth adjustments
        # philhealth_adjustments = Adjustment.objects.filter(
        #     employee=employee,
        #     name="Philhealth",
        #     month=cutoff_month,
        #     cutoff=cutoff,
        #     cutoff_year=cutoff_year,
        #     status__in=["Pending", "Approved", "Credited"]
        # )
        # if url_assigned_office:
        #     philhealth_adjustments = philhealth_adjustments.filter(assigned_office=url_assigned_office)
        # philhealth = philhealth_adjustments.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')

        # PHILHEALTH DEDUCTION 
        if employee.has_philhealth == "yes":
            philhealth = basic_salary_cutoff * Decimal('0.05')
        else:
            philhealth = Decimal('0')

        # PREVIOUS PHILHEALTH
        philhealth_previous = Adjustment.objects.filter(
            employee=employee,
            name__icontains="Philhealth",  # Matches any name containing "Philhealth"
            month=cutoff_month,
            cutoff=cutoff,
            cutoff_year=cutoff_year,
            status__in=["Pending", "Approved", "Credited"]
        )
        if url_assigned_office:
            philhealth_previous = philhealth_previous.filter(assigned_office=url_assigned_office)
        additional_philhealth = philhealth_previous.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')

        # SSS - fetch from SSS adjustments
        sss_adjustments = Adjustment.objects.filter(
            employee=employee,
            name="SSS",
            month=cutoff_month,
            cutoff=cutoff,
            cutoff_year=cutoff_year,
            status__in=["Pending", "Approved", "Credited"]
        )
        if url_assigned_office:
            sss_adjustments = sss_adjustments.filter(assigned_office=url_assigned_office)
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
        if url_assigned_office:
            late_adjustments = late_adjustments.filter(assigned_office=url_assigned_office)
        late_amt_total = late_adjustments.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
        late_min_total = late_adjustments.aggregate(Sum('details'))['details__sum'] or Decimal('0.00')

        # Absent adjustments
        absent_adjustments = Adjustment.objects.filter(
            employee=employee,
            name="Absent",
            month=cutoff_month,
            cutoff=cutoff,
            cutoff_year=cutoff_year,
            status__in=["Pending", "Approved", "Credited"]
        )
        if url_assigned_office:
            absent_adjustments = absent_adjustments.filter(assigned_office=url_assigned_office)

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
        if url_assigned_office:
            other_deductions = other_deductions.filter(assigned_office=url_assigned_office)
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
        if url_assigned_office:
            incomes = incomes.filter(assigned_office=url_assigned_office)
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
            # Check if the previous batch has any adjustments with status Pending, Approved, or Credited (filter by assigned_office)
            previous_batch_query = Adjustment.objects.filter(
                batch_number=previous_batch,
                cutoff=cutoff,
                month=cutoff_month,
                cutoff_year=cutoff_year,
                status__in=["Pending", "Approved", "Credited"]
            )
            
            # Apply assigned_office filter based on user role and context
            if url_assigned_office:
                # If coming from pending page, filter by the specific office
                previous_batch_query = previous_batch_query.filter(assigned_office=url_assigned_office)
            elif assigned_office and user_role != 'admin' and user_role != 'checker':
                # For office-specific preparators, only check adjustments for their assigned office
                previous_batch_query = previous_batch_query.filter(assigned_office=assigned_office)
            elif batch_assigned_office:
                # If we have a batch_assigned_office, use that for filtering
                previous_batch_query = previous_batch_query.filter(assigned_office=batch_assigned_office)
            
            previous_batch_submitted = previous_batch_query.exists()

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
        emp_data['previous_philhealth'] = f"{additional_philhealth}"
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

    # Determine if current batch is the last batch for the office
    office_to_check = url_assigned_office if url_assigned_office else assigned_office
    
    if office_to_check and user_role != 'admin' and user_role != 'checker':
        # For office-specific preparators, check last batch for their office
        last_batch_for_office = BatchAssignment.objects.filter(
            cutoff=cutoff,
            cutoff_month=cutoff_month,
            cutoff_year=cutoff_year,
            assigned_office=office_to_check
        ).order_by('-batch_number').first()
        
        is_last_batch = last_batch_for_office and last_batch_for_office.batch_number == batch_number
    else:
        # For admin and checker, check last batch across all offices
        last_batch_overall = BatchAssignment.objects.filter(
            cutoff=cutoff,
            cutoff_month=cutoff_month,
            cutoff_year=cutoff_year
        ).order_by('-batch_number').first()
        
        is_last_batch = last_batch_overall and last_batch_overall.batch_number == batch_number

    # Check if all adjustments in this batch are approved
    approval_filter = {
        'batch_number': batch_number,
        'cutoff': cutoff,
        'month': cutoff_month,
        'cutoff_year': cutoff_year,
    }
    
    # Only filter by assigned_office if we have a specific office to check
    if office_to_check:
        approval_filter['assigned_office'] = office_to_check
    
    total_adjustments = Adjustment.objects.filter(**approval_filter).count()
    
    approved_adjustments = Adjustment.objects.filter(
        **approval_filter,
        status__in=["Approved", "Credited"]
    ).count()
    
    # Set approval status
    approval_status = ""
    if total_adjustments > 0 and approved_adjustments == total_adjustments:
        approval_status = "Approved"

    # Determine batch_name from Batch model
    batch_name = None
    try:
        batch_qs = Batch.objects.filter(batch_number=batch_number)
        if batch_assigned_office:
            batch_qs = batch_qs.filter(batch_assigned_office=batch_assigned_office)
        batch_obj = batch_qs.first()
        if not batch_obj and batch_assigned_office:
            # Fallback: if not found with office, try without office filter
            batch_obj = Batch.objects.filter(batch_number=batch_number).first()
        if batch_obj:
            batch_name = batch_obj.batch_name
    except Exception:
        batch_name = None

    return JsonResponse({
        'employees': employees,
        'cutoff': cutoff,
        'cutoff_month': cutoff_month,
        'cutoff_year': cutoff_year,
        'batch_number': batch_number,
        'batch_name': batch_name,
        'has_pending_adjustments': has_pending_adjustments,
        'has_approved_adjustments': has_approved_adjustments,
        'has_credited_adjustments': has_credited_adjustments,
        'remark': remark or "",
        'approval_status': approval_status,
        'is_last_batch': is_last_batch,
        'assigned_office': batch_assigned_office,
        'formatted_office_name': get_formatted_office_name(batch_assigned_office),
        'payroll_title': get_payroll_title(batch_assigned_office),
    })

@login_required
@restrict_roles(disallowed_roles=['employee'])
def batch_create(request, batch_size=15):
    cutoff = request.POST.get('cutoff')
    cutoff_month = request.POST.get('cutoff_month')
    cutoff_year = request.POST.get('cutoff_year')

    if not cutoff or not cutoff_month or not cutoff_year:
        return JsonResponse({'error': 'Missing cutoff, month, or year.'}, status=400)

    user_role = request.session.get('role', '')
    assigned_office = get_user_assigned_office(user_role)

    # Check if batches already exist for the given period
    batch_filter = {
        'cutoff': cutoff,
        'cutoff_month': cutoff_month,
        'cutoff_year': cutoff_year
    }

    is_office_specific = bool(assigned_office and user_role not in ['admin', 'checker'])
    if is_office_specific:
        batch_filter['assigned_office'] = assigned_office

    if BatchAssignment.objects.filter(**batch_filter).exists():
        if is_office_specific:
            return JsonResponse({
                'error': f'Batches already exist for {cutoff_month} {cutoff}, {cutoff_year} in {get_formatted_office_name(assigned_office)}.'
            }, status=400)
        else:
            return JsonResponse({
                'error': f'Batches already exist for {cutoff_month} {cutoff}, {cutoff_year}.'
            }, status=400)

    # Get batch_numbers from Batch model based on office
    if is_office_specific:
        batch_numbers = list(
            Batch.objects.filter(batch_assigned_office=assigned_office)
            .values_list('batch_number', flat=True)
        )
    else:
        batch_numbers = list(Batch.objects.values_list('batch_number', flat=True))

    # Select employees whose employee.batch_number matches any of these batch_numbers
    if is_office_specific:
        all_employees = Employee.objects.filter(
            assigned_office=assigned_office,
            batch_number__in=batch_numbers
        ).order_by('fullname')
        employees_by_office = {assigned_office: list(all_employees)}
    else:
        all_employees = Employee.objects.filter(
            batch_number__in=batch_numbers
        ).order_by('fullname')
        employees_by_office = {}
        for employee in all_employees:
            office = employee.assigned_office or 'unassigned'
            employees_by_office.setdefault(office, []).append(employee)

    # Check if there are employees to assign
    if not all_employees.exists():
        if is_office_specific:
            return JsonResponse({'error': f'No employees with assigned batches found in {get_formatted_office_name(assigned_office)} to create batches.'}, status=400)
        else:
            return JsonResponse({'error': 'No employees with assigned batches found to create batches.'}, status=400)

    total_batches_created = 0
    offices_processed = []

    # Create batches for each office separately, grouped by employee.batch_number
    for office, employees in employees_by_office.items():
        if not employees:
            continue

        # Group employees by their assigned batch_number
        grouped_by_batch = {}
        for emp in employees:
            if emp.batch_number is None:
                continue
            grouped_by_batch.setdefault(emp.batch_number, []).append(emp)

        # Create BatchAssignment for each employee in each batch group
        for batch_num, group in grouped_by_batch.items():
            for emp in group:
                BatchAssignment.objects.create(
                    employee=emp,
                    batch_number=batch_num,
                    cutoff=cutoff,
                    cutoff_month=cutoff_month,
                    cutoff_year=cutoff_year,
                    assigned_office=emp.assigned_office
                )

        total_batches_created += len(grouped_by_batch)
        offices_processed.append(f"{get_formatted_office_name(office)} ({len(grouped_by_batch)} batches)")

    # Success message
    if is_office_specific:
        message = f'Batches successfully created for {cutoff_month} {cutoff}, {cutoff_year} in {get_formatted_office_name(assigned_office)}. Total batches created: {total_batches_created}.'
    else:
        message = f'Batches successfully created for {cutoff_month} {cutoff}, {cutoff_year}. Total batches created: {total_batches_created} across all offices.'

    return JsonResponse({'message': message})

@login_required
@restrict_roles(disallowed_roles=['employee'])
def batch_delete(request):
    cutoff_month = request.POST.get('cutoff_month')
    cutoff = request.POST.get('cutoff')
    cutoff_year = request.POST.get('cutoff_year')
    assigned_office = request.POST.get('assigned_office')

    if not (cutoff_month and cutoff and cutoff_year):
        return JsonResponse({'error': 'Missing required data'}, status=400)
    
    try:
        # Filter by assigned_office if provided
        batch_filter = {
            'cutoff_month': cutoff_month,
            'cutoff': cutoff,
            'cutoff_year': cutoff_year
        }
        if assigned_office:
            batch_filter['assigned_office'] = assigned_office

        adj_filter = {
            'month': cutoff_month,
            'cutoff': cutoff,
            'cutoff_year': cutoff_year
        }
        if assigned_office:
            adj_filter['assigned_office'] = assigned_office

        batch_deleted, _ = BatchAssignment.objects.filter(**batch_filter).delete()
        adj_deleted, _ = Adjustment.objects.filter(**adj_filter).delete()

        # Get user role and assigned office for remark removal
        user_role = request.session.get('role', '')
        user_assigned_office = get_user_assigned_office(user_role)
        
        # Filter remarks by assigned_office for preparators
        remark_filter = {
            'cutoff_month': cutoff_month,
            'cutoff': cutoff,
            'cutoff_year': cutoff_year
        }
        
        # For office-specific preparators, only remove remarks for their assigned office
        if user_assigned_office and user_role != 'admin' and user_role != 'checker':
            remark_filter['assigned_office'] = user_assigned_office
        elif assigned_office:
            # If assigned_office is provided in the request, use that
            remark_filter['assigned_office'] = assigned_office
        
        remark_deleted, _ = ReturnRemark.objects.filter(**remark_filter).delete()

        if batch_deleted == 0 and adj_deleted == 0 and remark_deleted == 0:
            return JsonResponse({'error': 'No matching records found'}, status=404)

        office_text = f" for {assigned_office}" if assigned_office else ""
        return JsonResponse({
            'message': f'{batch_deleted} batch assignments, '
                       f'{adj_deleted} adjustments, and '
                       f'{remark_deleted} return remarks removed successfully{office_text}.'
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
                    adjustment.assigned_office = employee.assigned_office
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
                        batch_number=batch_number,
                        assigned_office=employee.assigned_office
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
                    batch_number=batch_number,
                    assigned_office=employee.assigned_office
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
        assigned_office = request.GET.get('assigned_office')

        adjustments = Adjustment.objects.filter(
            employee_id=emp_id,
            batch_number=batch_number,
            cutoff=cutoff,
            month=cutoff_month,
            cutoff_year=cutoff_year,
            assigned_office=assigned_office
        )

        if not adjustments.exists():
            return JsonResponse({
                'adjustments': None,
                'cutoff': cutoff,
                'cutoff_month': cutoff_month,
                'cutoff_year': cutoff_year,
                'batch_number': batch_number,
                'assigned_office': assigned_office,
            }, status=200)

        data = list(adjustments.values())

        return JsonResponse({
            'adjustments': data,
            'cutoff': cutoff,
            'cutoff_month': cutoff_month,
            'cutoff_year': cutoff_year,
            'batch_number': batch_number,
            'assigned_office': assigned_office,
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
    # Get user role and filter batches accordingly
    user_role = request.session.get('role', '')
    
    # Get assigned office for the current user
    assigned_office = get_user_assigned_office(user_role)
    
    # Get all pending adjustments
    pending_adjustments_query = Adjustment.objects.filter(status="Pending")
    
    # Apply assigned_office filter if user is office-specific preparator
    if assigned_office and user_role != 'admin' and user_role != 'checker':
        pending_adjustments_query = pending_adjustments_query.filter(assigned_office=assigned_office)
    
    # Get unique batch identifiers from pending adjustments
    pending_batches = pending_adjustments_query.values(
        'cutoff',
        'month',
        'cutoff_year',
        'assigned_office'
    ).distinct()
    
    valid_batches = []
    
    for pending_batch in pending_batches:
        office = pending_batch['assigned_office']
        if office:  # Skip if office is None
            # Get employees with pending adjustments for this office and batch period
            employees_with_pending = pending_adjustments_query.filter(
                cutoff=pending_batch['cutoff'],
                month=pending_batch['month'],
                cutoff_year=pending_batch['cutoff_year'],
                assigned_office=office
            ).values_list('employee_id', flat=True).distinct()
            
            # Get unique batch numbers for these employees
            batch_numbers = BatchAssignment.objects.filter(
                employee_id__in=employees_with_pending,
                cutoff=pending_batch['cutoff'],
                cutoff_month=pending_batch['month'],
                cutoff_year=pending_batch['cutoff_year'],
                assigned_office=office
            ).values_list('batch_number', flat=True).distinct()
            
            # Add each unique batch number for this office
            for batch_number in batch_numbers:
                # Check if all adjustments in this batch are approved
                total_adjustments = Adjustment.objects.filter(
                    batch_number=batch_number,
                    cutoff=pending_batch['cutoff'],
                    month=pending_batch['month'],
                    cutoff_year=pending_batch['cutoff_year'],
                    assigned_office=office
                ).count()
                
                approved_adjustments = Adjustment.objects.filter(
                    batch_number=batch_number,
                    cutoff=pending_batch['cutoff'],
                    month=pending_batch['month'],
                    cutoff_year=pending_batch['cutoff_year'],
                    status="Approved",
                    assigned_office=office
                ).count()
                
                # Set approval status
                approval_status = ""
                if total_adjustments > 0 and approved_adjustments == total_adjustments:
                    approval_status = "Approved"

                # Get the batch names of the batch
                batch_obj = Batch.objects.filter(
                    batch_number=batch_number,
                    batch_assigned_office=office
                ).first()
                
                # If not found with office filter, try without office filter
                if not batch_obj:
                    batch_obj = Batch.objects.filter(batch_number=batch_number).first()
                
                batch_name = batch_obj.batch_name if batch_obj else f"Batch {batch_number}"  
                
                valid_batches.append({
                    'batch_name': batch_name,
                    'batch_number': batch_number,
                    'cutoff': pending_batch['cutoff'],
                    'cutoff_month': pending_batch['month'],
                    'cutoff_year': pending_batch['cutoff_year'],
                    'assigned_office': office,
                    'approval_status': approval_status
                })
    
    # Remove duplicates based on batch_number, cutoff, cutoff_month, cutoff_year, and assigned_office
    seen = set()
    unique_batches = []
    for batch in valid_batches:
        key = (batch['batch_number'], batch['cutoff'], batch['cutoff_month'], batch['cutoff_year'], batch['assigned_office'])
        if key not in seen:
            seen.add(key)
            # Add formatted office name and payroll title
            batch['formatted_office_name'] = get_formatted_office_name(batch['assigned_office'])
            batch['payroll_title'] = get_payroll_title(batch['assigned_office'])
            unique_batches.append(batch)

    return JsonResponse({'batches': unique_batches}, status=200)

def show(request):
    batch_number = request.GET.get('batch_number')
    assigned_office = request.GET.get('assigned_office')
    
    # If batch_name is not provided in URL, try to fetch it from the database
    batch_name = request.GET.get('batch_name')
    if not batch_name and batch_number:
        try:
            from payslip_generation_system.models.batch import Batch
            batch_obj = Batch.objects.filter(batch_number=batch_number).first()
            if batch_obj:
                batch_name = batch_obj.batch_name
        except Exception:
            batch_name = None
    
    # If still no batch_name, provide a fallback
    if not batch_name and batch_number:
        batch_name = f"Batch {batch_number}"
    
    context = {
        'cutoff': request.GET.get('cutoff'),
        'cutoff_month': request.GET.get('cutoff_month'),
        'cutoff_year': request.GET.get('cutoff_year'),
        'batch_number': batch_number,
        'batch_name': batch_name,
        'assigned_office': assigned_office,
    }
    return render(request, 'payroll/view.html', context)

@login_required
@restrict_roles(disallowed_roles=['employee'])
def approved_list(request):
    return render(request, 'payroll/approve.html')

@login_required
@restrict_roles(disallowed_roles=['employee'])
def approve_data(request):
    # Get approved batches with all needed Adjustment fields
    approved_adjustments = (
        Adjustment.objects.filter(status="Approved")
        .values('batch_number', 'month', 'cutoff', 'cutoff_year')
        .distinct()
    )

    # Get batch details for those batch_numbers
    batch_numbers = [adj['batch_number'] for adj in approved_adjustments]

    batch_details = (
        Batch.objects.filter(batch_number__in=batch_numbers)
        .values('batch_number', 'batch_name', 'batch_assigned_office')
        .order_by('batch_number')
    )

    # Convert to list so we can modify
    batch_list = list(batch_details)

    # Merge the month, cutoff, and cutoff_year into batch_list
    for batch in batch_list:
        adj_info = next((a for a in approved_adjustments if a['batch_number'] == batch['batch_number']), None)
        if adj_info:
            batch['month'] = adj_info['month']
            batch['cutoff'] = adj_info['cutoff']
            batch['cutoff_year'] = adj_info['cutoff_year']

        # Apply formatted office name
        batch['formatted_office_name'] = get_formatted_office_name(batch['batch_assigned_office'])

    return JsonResponse({
        'approved_batches': batch_list
    }, status=200)

@login_required
@restrict_roles(disallowed_roles=['employee'])
def approve_office_to_credited(request):
    """
    Update all adjustments for a specific office from 'Approved' to 'Credited' status.
    This function is called when the cashier confirms the SweetAlert2 dialog.
    """
    if request.method == 'POST':
        assigned_office = request.POST.get('assigned_office')
        
        if not assigned_office:
            return JsonResponse({'success': False, 'message': 'Assigned office is required'}, status=400)
        
        try:
            # Get all batch numbers for this office (excluding batch_number 0)
            office_batches = BatchAssignment.objects.filter(
                assigned_office=assigned_office
            ).exclude(batch_number=0).values(
                'batch_number',
                'cutoff',
                'cutoff_month',
                'cutoff_year'
            ).distinct()
            
            updated_count = 0
            
            for batch in office_batches:
                # Get all employee IDs in this batch for this office
                employee_ids = BatchAssignment.objects.filter(
                    batch_number=batch['batch_number'],
                    cutoff=batch['cutoff'],
                    cutoff_month=batch['cutoff_month'],
                    cutoff_year=batch['cutoff_year'],
                    assigned_office=assigned_office
                ).values_list('employee_id', flat=True)
                
                if not employee_ids:
                    continue
                
                # Update all adjustments for these employees from 'Approved' to 'Credited'
                updated_adjustments = Adjustment.objects.filter(
                    employee_id__in=employee_ids,
                    cutoff=batch['cutoff'],
                    month=batch['cutoff_month'],
                    cutoff_year=batch['cutoff_year'],
                    status="Approved",
                    assigned_office=assigned_office
                ).update(status="Credited")
                
                updated_count += updated_adjustments
            
            if updated_count > 0:
                return JsonResponse({
                    'success': True, 
                    'message': f'Successfully updated {updated_count} adjustments to Credited status for {get_formatted_office_name(assigned_office)}'
                }, status=200)
            else:
                return JsonResponse({
                    'success': False, 
                    'message': f'No adjustments found to update for {get_formatted_office_name(assigned_office)}'
                }, status=404)
                
        except Exception as e:
            return JsonResponse({
                'success': False, 
                'message': f'Error updating adjustments: {str(e)}'
            }, status=500)
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=405)


@login_required
@restrict_roles(disallowed_roles=['employee'])
def approve_show(request):
    context = {
        'cutoff': request.GET.get('cutoff'),
        'cutoff_month': request.GET.get('cutoff_month'),
        'cutoff_year': request.GET.get('cutoff_year'),
        'batch_number': request.GET.get('batch_number'),
        'assigned_office': request.GET.get('assigned_office'),
    }
    return render(request, 'payroll/releasing.html', context)

@login_required
@restrict_roles(disallowed_roles=['employee'])
def removed_employee_data(request):
    cutoff = request.GET.get('cutoff') or '1st'
    cutoff_month = request.GET.get('cutoff_month') or 'January'
    cutoff_year = int(request.GET.get('cutoff_year') or datetime.now().year)
    batch_number = int(request.GET.get('batch_number') or 0)
    removed= 'YES'

    # Get user role and filter batches accordingly
    user_role = request.session.get('role', '')
    
    # Get assigned office for the current user
    assigned_office = get_user_assigned_office(user_role)
    
    # Filter assignments based on user role
    if assigned_office and user_role != 'admin' and user_role != 'checker':
        # For office-specific preparators, show only their office batches
        assignments = BatchAssignment.objects.filter(
            cutoff=cutoff,
            cutoff_month=cutoff_month,
            cutoff_year=cutoff_year,
            previous_batch=batch_number,
            removed=removed,
            assigned_office=assigned_office
        ).select_related('employee')
    else:
        # For admin and checker, show all batches
        assignments = BatchAssignment.objects.filter(
            cutoff=cutoff,
            cutoff_month=cutoff_month,
            cutoff_year=cutoff_year,
            previous_batch=batch_number,
            removed=removed
        ).select_related('employee')

    # Get the employee IDs for removed employees
    removed_employee_ids = [a.employee.id for a in assignments]

    # Get the assigned_office for this batch (all employees in a batch should have the same assigned_office)
    batch_assigned_office = None
    if assignments.exists():
        batch_assigned_office = assignments.first().assigned_office

    # Check for adjustment statuses for removed employees (filter by assigned_office)
    adjustment_filter = {
        'employee_id__in': removed_employee_ids,
        'cutoff': cutoff,
        'month': cutoff_month,
        'cutoff_year': cutoff_year,
    }
    
    # For office-specific preparators, only check adjustments for their assigned office
    if assigned_office and user_role != 'admin' and user_role != 'checker':
        adjustment_filter['assigned_office'] = assigned_office
    elif batch_assigned_office:
        # If we have a batch_assigned_office, use that for filtering
        adjustment_filter['assigned_office'] = batch_assigned_office

    has_pending_adjustments = Adjustment.objects.filter(
        **adjustment_filter,
        status="Pending"
    ).exists()

    has_approved_adjustments = Adjustment.objects.filter(
        **adjustment_filter,
        status__in=["Approved", "Credited"]
    ).exists()

    has_credited_adjustments = Adjustment.objects.filter(
        **adjustment_filter,
        status="Credited"
    ).exists()

    employees = []

    for a in assignments:
        emp = a.employee
        
        # Check if the employee's previous batch has been submitted
        previous_batch = a.previous_batch
        previous_batch_submitted = False
        
        if previous_batch is not None:
            # Check if the previous batch has any adjustments with status Pending, Approved, or Credited (filter by assigned_office)
            previous_batch_filter = {
                'batch_number': previous_batch,
                'cutoff': cutoff,
                'month': cutoff_month,
                'cutoff_year': cutoff_year,
                'status__in': ["Pending", "Approved", "Credited"]
            }
            
            # For office-specific preparators, only check adjustments for their assigned office
            if assigned_office and user_role != 'admin' and user_role != 'checker':
                previous_batch_filter['assigned_office'] = assigned_office
            elif batch_assigned_office:
                # If we have a batch_assigned_office, use that for filtering
                previous_batch_filter['assigned_office'] = batch_assigned_office
            
            previous_batch_submitted = Adjustment.objects.filter(**previous_batch_filter).exists()

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

    # Check if all adjustments in this batch are approved
    total_adjustments = Adjustment.objects.filter(
        employee_id__in=removed_employee_ids,
        cutoff=cutoff,
        month=cutoff_month,
        cutoff_year=cutoff_year,
        assigned_office=batch_assigned_office
    ).count()
    
    approved_adjustments = Adjustment.objects.filter(
        employee_id__in=removed_employee_ids,
        cutoff=cutoff,
        month=cutoff_month,
        cutoff_year=cutoff_year,
        status__in=["Approved", "Credited"],
        assigned_office=batch_assigned_office
    ).count()
    
    # Set approval status
    approval_status = ""
    if total_adjustments > 0 and approved_adjustments == total_adjustments:
        approval_status = "Approved"

    return JsonResponse({
        'employees': employees,
        'cutoff': cutoff,
        'cutoff_month': cutoff_month,
        'cutoff_year': cutoff_year,
        'batch_number': batch_number,
        'has_pending_adjustments': has_pending_adjustments,
        'has_approved_adjustments': has_approved_adjustments,
        'has_credited_adjustments': has_credited_adjustments,
        'approval_status': approval_status,
        'assigned_office': batch_assigned_office,
        'formatted_office_name': get_formatted_office_name(batch_assigned_office),
        'payroll_title': get_payroll_title(batch_assigned_office),
    })

@login_required
@restrict_roles(disallowed_roles=['employee'])
def release_multiple_batch(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body or '{}')
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        batches = data.get('batches', [])

        updated_count = 0
        for batch in batches:
            filter_kwargs = {
                'batch_number': batch.get('batch_number'),
                'cutoff': batch.get('cutoff'),
                'month': batch.get('month'),
                'cutoff_year': batch.get('cutoff_year'),
                'status': 'Approved',
            }
            updated_count += Adjustment.objects.filter(**filter_kwargs).update(status='Credited')

        return JsonResponse({'status': 'OK', 'updated': updated_count}, status=200)

    return JsonResponse({'error': 'Invalid request method'}, status=405)

@login_required
@restrict_roles(disallowed_roles=['employee'])
def move_employee(request, emp_id):
    if request.method == 'POST':
        try:
            employee = get_object_or_404(Employee, id=emp_id)
            batch_id = request.POST.get('batch_id')
            cutoff = request.POST.get('cutoff')
            cutoff_month = request.POST.get('cutoff_month')
            cutoff_year = request.POST.get('cutoff_year')
            old_batch_number = request.POST.get('batch_number')
            assigned_office = request.POST.get('assigned_office')
            
            if not batch_id:
                return JsonResponse({'success': False, 'error': 'Batch ID is required.'})
            
            # Batch
            batch = get_object_or_404(Batch, id=batch_id)
            
            # Check if the batch belongs to the user's office prevent cross batching
            user_role = request.session.get('role', '')
            user_office = get_user_assigned_office(user_role)

            # Error Handling on invalid batch
            if not user_office or batch.batch_assigned_office != user_office:
                return JsonResponse({'success': False, 'error': 'You can only assign employees to batches in your office.'})
            
            # Batch Assignment
            assignment = BatchAssignment.objects.filter(
                employee_id=employee.id,
                cutoff=cutoff,
                cutoff_month=cutoff_month,
                cutoff_year=cutoff_year,
                batch_number = old_batch_number,
                assigned_office = assigned_office,
            ).first()

            if not assignment:
                return JsonResponse({'success': False, 'error': 'Batch assignment not found'})
            
            assignment.batch_number = batch.batch_number
            assignment.save()

            # Adjustments
            Adjustment.objects.filter(
                employee_id=employee.id,
                cutoff=cutoff,
                month=cutoff_month,
                cutoff_year=cutoff_year,
                batch_number = old_batch_number,
                assigned_office = assigned_office,
            ).update(batch_number=batch.batch_number)

            # Employee
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
@restrict_roles(disallowed_roles=['employee'])
def move_employee_available_batches(request):
    try:
        user_role = request.session.get('role', '')
        user_office = get_user_assigned_office(user_role)

        if not user_office:
            return JsonResponse({'success': False, 'error': 'Unable to determine your office.'})
        
        # Get cutoff values from request
        cutoff = request.GET.get('cutoff')
        cutoff_month = request.GET.get('cutoff_month')
        cutoff_year = request.GET.get('cutoff_year')
        batch_number = request.GET.get('batch_number')
        
        # Get all batches for the office
        batches = Batch.objects.filter(batch_assigned_office=user_office).order_by('batch_number')

        # Find pending adjustments matching same cutoff data
        pending_adjustments = Adjustment.objects.filter(
            assigned_office=user_office,
            cutoff=cutoff,
            month=cutoff_month,
            cutoff_year=cutoff_year,
            status__in=["Pending", "Approved", "Credited"]
        ).values("batch_number")

        forbidden_batch_numbers = set([adj["batch_number"] for adj in pending_adjustments])

        batch_data = []
        for batch in batches:
            if batch.batch_number not in forbidden_batch_numbers:
                batch_data.append({
                    'id': batch.id,
                    'batch_number': batch.batch_number,
                    'batch_name': batch.batch_name
                })

        return JsonResponse({'success': True, 'batches': batch_data})

    except Exception as e:
        return JsonResponse({'success': False, 'error': f'An error occurred: {str(e)}'})