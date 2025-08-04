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
from django.contrib.auth.models import User
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
    ).select_related('employee')

    employees = [model_to_dict(a.employee) for a in assignments]

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
def adjustment_create(request, emp_id):
    if request.method == 'POST':
        id = emp_id,
        absence = request.POST.get('absence')
        late = request.POST.get('late')
        income_name = request.POST.get('income_name')
        income_ammount = request.POST.get('income_ammount')
        deduction_name = request.POST.get('deduction_name')
        deduction_ammount = request.POST.get('deduction_ammount')

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

        return JsonResponse(status=200)

    return JsonResponse({'error': 'Invalid request method'}, status=405)
