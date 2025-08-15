from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.db import connection
from django.http import JsonResponse
from datetime import datetime
from payslip_generation_system.models import BatchAssignment, Adjustment  

from django.contrib.auth.decorators import login_required

@login_required
def data(request):
    if request.method == 'POST':
        cutoff = request.POST.get('cutoff')
        cutoff_month = request.POST.get('cutoff_month')
        cutoff_year = request.POST.get('cutoff_year')
        assigned_office = request.POST.get('assigned_office')
        batch_number = request.POST.get('batch_number')

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
                    'amount': adj.amount,
                    'details': adj.details,
                }
                for adj in adjustments
            ]

            employees_data.append({
                'employee_id': emp.id,
                'fullname': emp.fullname,
                'position': getattr(emp, 'position', ''),
                'salary': getattr(emp, 'salary', 0),
                'tax_declaration': getattr(emp, 'tax_declaration', ''),
                'has_philhealth': getattr(emp, 'has_philhealth', ''),
                'adjustments': adjustments_data
            })

        return JsonResponse({'employees': employees_data})

    return JsonResponse({'error': 'Invalid request method'}, status=400)