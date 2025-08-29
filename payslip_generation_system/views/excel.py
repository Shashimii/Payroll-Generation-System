from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.db import connection
from django.http import JsonResponse
from django.db.models import Q, Sum
from datetime import datetime
from payslip_generation_system.models import BatchAssignment, Adjustment  
from decimal import Decimal
from datetime import datetime
import calendar

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

        # Excel File Date
        number_cutoff_month = datetime.strptime(cutoff_month, "%B").month
        number_cutoff_year = int(cutoff_year)
        last_day = calendar.monthrange(number_cutoff_year, number_cutoff_month)[1]

        # ranges
        excel_cutoff_ranges = {
            "first": f"{cutoff_month}-1-15,{cutoff_year}",
            "second": f"{cutoff_month}-16-{last_day},{cutoff_year}"
        }

        if cutoff == '1st':
            excel_cutoff_range = excel_cutoff_ranges['first']
        elif cutoff == '2nd':
            excel_cutoff_range = excel_cutoff_ranges["second"]
        else:
            excel_cutoff_range = 'Cutoff Range'

        # Find the Employees on the Current Payroll
        batch_assignments = BatchAssignment.objects.filter(
            cutoff=cutoff,
            cutoff_month=cutoff_month,
            cutoff_year=cutoff_year,
            assigned_office=assigned_office,
            batch_number=batch_number
        ).select_related("employee").order_by("employee__fullname")
        
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

            # Adjustment Deductions 
            adjustment_deductions = Adjustment.objects.filter(
                employee=assignment.employee,
                type="Deduction",
                month=cutoff_month,
                cutoff=cutoff,
                cutoff_year=cutoff_year,
            ).exclude(
                Q(name__in=["Late", "Absent", "TAX", "SSS"]) | Q(name__icontains="Philhealth")
            )

            adjustment_income = Adjustment.objects.filter(
                employee=assignment.employee,
                type="Income",
                month=cutoff_month,
                cutoff=cutoff,
                cutoff_year=cutoff_year,
            )

            # Late Adjustments
            late_adjustments = Adjustment.objects.filter(
                employee=assignment.employee,
                name="Late",
                month=cutoff_month,
                cutoff=cutoff,
                cutoff_year=cutoff_year
            )

            # Absent Adjustments
            absent_adjustments = Adjustment.objects.filter(
                employee=assignment.employee,
                name="Absent",
                month=cutoff_month,
                cutoff=cutoff,
                cutoff_year=cutoff_year
            )

            total_adjustment_deduction = (
                adjustment_deductions.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
            )
            total_adjustment_income = (
                adjustment_income.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
            )
            total_adjustment_late = (
                late_adjustments.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
            )
            total_adjustment_absent = (
                absent_adjustments.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
            )

            total_gross_amount = abs(basic_salary_cutoff - total_adjustment_late - total_adjustment_absent - total_adjustment_deduction + total_adjustment_income)

            # Tax
            if emp.tax_declaration == "no":
                tax_amount = (total_gross_amount * Decimal('0.03')).quantize(Decimal('0.01'))

            # Philhealth Current
            if emp.has_philhealth == "yes":
                philhealth_current = (total_gross_amount * Decimal('0.05')).quantize(Decimal('0.01'))

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
                'absent': total_adjustment_absent,
                'late': total_adjustment_late,
                'adjustment_deductions': total_adjustment_deduction,
                'adjustment_income': total_adjustment_income,
                'total_gross': total_gross_amount,
                'has_philhealth': getattr(emp, 'has_philhealth', ''),
                'tax_amount': float(tax_amount.quantize(Decimal('0.01'))),
                'philhealth_current': float(philhealth_current.quantize(Decimal('0.01'))),
                'philhealth_previous': float(philhealth_previous.quantize(Decimal('0.01'))),
                'adjustments': adjustments_data
            })

            # System Date of Generation
            systemNow = datetime.now()

            try:
                formatted = systemNow.strftime("%-m-%-d-%Y %I:%M %p")  # Linux/Unix
            except ValueError:
                formatted = systemNow.strftime("%#m-%#d-%Y %I:%M %p")  # Windows

        return JsonResponse({
            'excel_cutoff_range': excel_cutoff_range, 
            'employees': employees_data,
            'systemNow' : formatted,
        })

    return JsonResponse({'error': 'Invalid request method'}, status=400)