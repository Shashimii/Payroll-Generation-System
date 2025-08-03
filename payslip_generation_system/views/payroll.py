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
from payslip_generation_system.models import Employee, BatchAssignment
from payslip_generation_system.decorators import restrict_roles
from django.contrib.auth.models import User

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

def batch_data(request):
    batch_number = request.GET.get('batch_number', 1)
    cutoff = request.GET.get('cutoff', '1st')
    cutoff_month = request.GET.get('cutoff_month', 'January')
    cutoff_year = request.GET.get('cutoff_year', datetime.now().year)

    assignments = BatchAssignment.objects.filter(
        batch_number=batch_number,
        cutoff=cutoff,
        cutoff_month=cutoff_month,
        cutoff_year=cutoff_year
    ).select_related('employee')

    employees = [{
        'employee_number': a.employee.employee_number,
        'fullname': a.employee.fullname,
        'position': a.employee.position,
        'division': a.employee.division,
    } for a in assignments]

    return JsonResponse({'employees': employees})

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

