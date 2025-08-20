from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.db import connection
from django.http import JsonResponse
from datetime import datetime
from payslip_generation_system.models import BatchAssignment, Adjustment  
from decimal import Decimal

from django.contrib.auth.decorators import login_required

@login_required
def data(request):
    if request.method == 'POST':
        cutoff = request.POST.get('cutoff')
        cutoff_month = request.POST.get('cutoff_month')
        cutoff_year = request.POST.get('cutoff_year')
        assigned_office = request.POST.get('assigned_office')
        batch_number = request.POST.get('batch_number')
        philhealth_current = Decimal('0.00')
        tax_amount = Decimal('0.00')

        # Find the Employees on the Current Payroll
        batch_assignments = BatchAssignment.objects.filter(
            cutoff=cutoff,
            cutoff_month=cutoff_month,
            cutoff_year=cutoff_year,
            assigned_office=assigned_office,
            batch_number=batch_number
        )
        
        # Fetch Employee Info
        employees_data = []
        for assignment in batch_assignments:
            emp = assignment.employee
            basic_salary = emp.salary
            basic_salary_cutoff = basic_salary / 2

            # Reset per-employee computed values
            tax_amount = Decimal('0.00')
            philhealth_current = Decimal('0.00')

            # Fetch Employee Adjustment
            adjustments = Adjustment.objects.filter(
                employee=emp,
                cutoff=cutoff,
                month=cutoff_month,
                cutoff_year=cutoff_year,
                assigned_office=assigned_office,
                batch_number=batch_number,
            )

            adjustments_data = [
                {
                    'name': adj.name,
                    'type': adj.type,
                    'amount': float(adj.amount),
                    'details': adj.details,
                }
                for adj in adjustments
            ]

            # Tax
            if emp.tax_declaration == "no":
                tax_amount = (basic_salary_cutoff * Decimal('0.03')).quantize(Decimal('0.01'))

            # Philhealth Current
            if emp.has_philhealth == "yes":
                if basic_salary_cutoff > Decimal('9999'):
                    philhealth_current = (basic_salary_cutoff * Decimal('0.05')).quantize(Decimal('0.01'))
                else:
                    philhealth_current = Decimal('500.00')

            # Philhealth Previous
            philhealth_previous = sum(
                (adj.amount for adj in adjustments if "philhealth" in (adj.name or "").lower()),
                Decimal('0.00')
            ).quantize(Decimal('0.01'))


            employees_data.append({
                'employee_id': emp.id,
                'fullname': emp.fullname,
                'position': getattr(emp, 'position', ''),
                'salary': float(getattr(emp, 'salary', 0)),
                'tax_declaration': getattr(emp, 'tax_declaration', ''),
                'has_philhealth': getattr(emp, 'has_philhealth', ''),
                'tax_amount': float(tax_amount.quantize(Decimal('0.01'))),
                'philhealth_current': float(philhealth_current.quantize(Decimal('0.01'))),
                'philhealth_previous': float(philhealth_previous.quantize(Decimal('0.01'))),
                'adjustments': adjustments_data
            })

        return JsonResponse({'employees': employees_data})

    return JsonResponse({'error': 'Invalid request method'}, status=400)