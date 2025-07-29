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
from payslip_generation_system.models import Employee, Adjustment
from payslip_generation_system.decorators import restrict_roles
from django.contrib.auth.models import User

from django.contrib.auth.decorators import login_required

@login_required
@restrict_roles(disallowed_roles=['employee'])
def index(request):
    return render(request, 'payslip/index.html')

@login_required
def create(request):
    # Role
    role = request.session.get('role')

    # logged user id
    current_user_id = request.user.id

    # Offices
    denrncrnec = 'denr_ncr_nec'
    meos = 'meo_s'
    meoe = 'meo_e'
    meow = 'moe_w'
    meon = 'meo_n'

    # Data
    match role:
        case "admin":
            employees = Employee.objects.all()
        case "checker":
            employees = Employee.objects.all()
        case "preparator_denr_nec":
            employees = Employee.objects.filter(assigned_office=denrncrnec).all()
        case "preparator_meo_s":
            employees = Employee.objects.filter(assigned_office=meos).all()
        case "preparator_meo_e":
            employees = Employee.objects.filter(assigned_office=meoe).all()
        case "preparator_meo_w":
            employees = Employee.objects.filter(assigned_office=meow).all()
        case "preparator_meo_n":
            employees = Employee.objects.filter(assigned_office=meon).all()
        case "employee":
            employees = Employee.objects.filter(user_id=current_user_id)
        case _:
            employees = Employee.objects.filter(user_id=current_user_id)

    month_choices = [
        ('January', 'January'),
        ('February', 'February'),
        ('March', 'March'),
        ('April', 'April'),
        ('May', 'May'),
        ('June', 'June'),
        ('July', 'July'),
        ('August', 'August'),
        ('September', 'September'),
        ('October', 'October'),
        ('November', 'November'),
        ('December', 'December'),
    ]

    current_month = datetime.now().strftime('%B')
    # current_year = datetime.now().strftime('%Y')
    
    return render(request, 'payslip/create.html', {
        'employees': employees,
        'month_choices': month_choices,
        'current_month': current_month,
    })

@login_required
def generate(request):
    month_choices = [
        ('January', 'January'),
        ('February', 'February'),
        ('March', 'March'),
        ('April', 'April'),
        ('May', 'May'),
        ('June', 'June'),
        ('July', 'July'),
        ('August', 'August'),
        ('September', 'September'),
        ('October', 'October'),
        ('November', 'November'),
        ('December', 'December'),
    ]
    current_month = datetime.now().strftime('%B')
    current_year = datetime.now().strftime('%Y')

    if request.method == 'POST':
        # Get form data
        employee_id = request.POST.get('employee')
        selected_month = request.POST.get('month')
        selected_cutoff = request.POST.get('cutoff')

        # Fetch employee data
        employee = Employee.objects.get(id=employee_id)

        has_adjustments = Adjustment.objects.filter(
            employee=employee,
            month=selected_month,
            cutoff=selected_cutoff,
            cutoff_year=current_year,
            status="Approved"
        ).exists()

        if not has_adjustments:
            messages.error(request, 'Payslip in process.')
            return redirect('payslip_create')
        
        # Basic Salary
        basic_salary = employee.salary
        # Annual Salary
        basic_salary_annual = basic_salary * 12
        # Cutoff Salary
        basic_salary_cutoff = basic_salary / 2  

        # Deduction Conditions
        # Salary
        if (employee.tax_declaration == "Yes"):
                tax_deduction = Decimal('0.00')
        else:
            if (basic_salary_annual >= 250000):
                tax_deduction = basic_salary_cutoff * Decimal('0.027')
            else:
                tax_deduction = basic_salary_cutoff * Decimal('0.00')
        
        # Philhealth 
        if (basic_salary_cutoff > 9999):
            philhealth = basic_salary_cutoff * Decimal('0.05')
        else:
            philhealth = basic_salary_cutoff - 500
        
        #late
        late_adjustments = Adjustment.objects.filter(
            employee=employee,
            name="Late",
            month=selected_month,
            cutoff=selected_cutoff,
            status="Approved"
            # Adjusted condition to match selected month
        )
        
        late_amt_total = late_adjustments.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
        late_min_total = late_adjustments.aggregate(Sum('details'))['details__sum'] or Decimal('0.00') 
        
        # Format the salary period
        salary_period = f"{selected_month} {current_year} - {selected_cutoff} Cutoff"
        
        #adjustment_minus
        all_adjustment_minus = Adjustment.objects.filter(
            employee=employee,
            type="Deduction",
            month=selected_month,
            cutoff=selected_cutoff,
            status="Approved"
            # Adjusted condition to match selected month
        ).exclude(name="Late")
        
        # Sum the amount for all adjustments
        total_adjustment_amount_minus = all_adjustment_minus.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
        total_deductions = tax_deduction + philhealth + late_amt_total + total_adjustment_amount_minus

        #adjustment_plus
        all_adjustment_plus = Adjustment.objects.filter(
            employee=employee,
            type="Income",
            month=selected_month,
            cutoff=selected_cutoff,
            status="Approved"
            # Adjusted condition to match selected month
        )
        
        # Sum the amount for all adjustments
        total_adjustment_amount_plus = all_adjustment_plus.aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
        
        total_add = total_adjustment_amount_plus
        
        context = {
            'employee_no': employee.employee_number,
            'employee_name': employee.fullname,
            'position': employee.position,
            'salary_period': salary_period,
            'selected_cutoff': selected_cutoff,
            'basic_salary_cutoff': basic_salary_cutoff,
            'tax_deduction': tax_deduction,
            'philhealth': philhealth,
            'late_amt_total': late_amt_total,
            'late_min_total': late_min_total,
            'total_adjustment_amount_minus': total_adjustment_amount_minus,
            'all_adjustment_minus': all_adjustment_minus,
            'total_adjustment_amount_plus': total_adjustment_amount_plus,
            'all_adjustment_plus': all_adjustment_plus,
            'total_deductions' : total_deductions,
            'total_add': total_add,
            'net_pay': basic_salary_cutoff - total_deductions + total_add,
            'month_choices': month_choices,
            'current_month': current_month,
            'current_year' : current_year,
        }

    return render(request, 'payslip/payslip.html', context)

@login_required
def adjustment(request, emp_id):
    employee = get_object_or_404(Employee, id=emp_id)
    return render(request, 'payslip/adjustment.html', {
        'employee': employee
    })

@login_required
def adjustment_add(request, emp_id):
    employee = get_object_or_404(Employee, id=emp_id)
    if request.method == 'POST':
        
        name = request.POST['name']
        raw_amount = request.POST['amount']
        raw_amount_details = request.POST['details']

        # Compute amount if the adjustment is for "Late"
        if name == 'Late':
            try:
                minutes_late = float(raw_amount_details)
                daily_rate = float(employee.salary) / 22
                per_minute_rate = daily_rate / (8 * 60)
                computed_amount = round(per_minute_rate * minutes_late, 2)
            except Exception:
                computed_amount = Decimal('0.00')
        else:
            computed_amount = raw_amount  # use as is

        # Create the adjustment record
        Adjustment.objects.create(
            employee=employee,
            name=request.POST['name'],
            type=request.POST['type'],
            amount=computed_amount,
            details=request.POST.get('details', ''),
            month=request.POST.get('month'),
            cutoff=request.POST.get('cutoff'),
            status=request.POST.get('status', 'Pending'),
            remarks=request.POST.get('remarks', ''),
        )
        messages.success(request, 'Adjustment successfully added.')
        return redirect('payslip_adjustment', emp_id=employee.id)
    
@login_required
def adjustment_edit(request, emp_id, adj_id):
    employee = get_object_or_404(Employee, id=emp_id)
    adjustment = get_object_or_404(Adjustment, id=adj_id, employee=employee)

    if request.method == 'POST':
        name = request.POST['name']
        raw_amount = request.POST['amount']
        raw_amount_details = request.POST['details']

        # Compute amount if the adjustment is for "Late"
        if name == 'Late':
            try:
                minutes_late = float(raw_amount_details)
                daily_rate = float(employee.salary) / 22
                per_minute_rate = daily_rate / (8 * 60)
                computed_amount = round(per_minute_rate * minutes_late, 2)
            except Exception:
                computed_amount = Decimal('0.00')
        else:
            computed_amount = raw_amount  # use as is

        # Update the adjustment record
        adjustment.name = name
        adjustment.type = request.POST['type']
        adjustment.amount = computed_amount
        adjustment.details = request.POST.get('details', '')
        adjustment.month = request.POST.get('month')
        adjustment.cutoff = request.POST.get('cutoff')
        adjustment.status = request.POST.get('status', 'Pending')
        adjustment.remarks = request.POST.get('remarks', '')
        adjustment.save()

        messages.success(request, 'Adjustment successfully updated.')
        return redirect('payslip_adjustment', emp_id=employee.id)

@login_required
def employee_data(request):
    user_role = request.session.get('role')

    # DataTable parameters
    draw = int(request.GET.get('draw', 1))
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 10))
    search_value = request.GET.get('search[value]', '')
    order_col_index = int(request.GET.get('order[0][column]', 0))
    order_dir = request.GET.get('order[0][dir]', 'asc')

    # Fields to retrieve
    fields = ['id', 'employee_number', 'fullname', 'position', 'fund_source', 'salary', 'tax_declaration', 'eligibility']

    # Roles
    role = request.session.get('role')
    
    # Offices
    denrncrnec = 'denr_ncr_nec'
    meos = 'meo_s'
    meoe = 'meo_e'
    meow = 'moe_w'
    meon = 'meo_n'

    # Data
    match role:
        case "admin":
            queryset = Employee.objects.values(*fields)
        case "checker":
            queryset = Employee.objects.values(*fields)
        case "preparator_denr_nec":
            queryset = Employee.objects.filter(assigned_office=denrncrnec).values(*fields)
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

    # Search filter
    if search_value:
        queryset = queryset.filter(
            Q(employee_number__icontains=search_value) |
            Q(fullname__icontains=search_value) |
            Q(position__icontains=search_value) |
            Q(fund_source__icontains=search_value) |
            Q(tax_declaration__icontains=search_value) |
            Q(eligibility__icontains=search_value)
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

    data = []
    for emp in page:
        salary = f"₱{emp['salary']:,.2f}" if emp.get('salary') else ""

        data.append([
            emp.get('employee_number', ''),
            emp.get('fullname', ''),
            emp.get('position', ''),
            emp.get('fund_source', ''),
            salary,
            emp.get('tax_declaration', ''),
            emp.get('eligibility', ''),
            f"""
            <button class='adjustments-btn btn btn-warning btn-sm view-btn' title='Adjustments' data-id='{emp['id']}'>
                <i class="fa-solid fa-sliders"></i> Make Adjustments
            </button> 
            """
        ])

    return JsonResponse({
        'draw': draw,
        'recordsTotal': total_records,
        'recordsFiltered': total_records,
        'data': data
    })

def safe_int(value, default=0):
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

@login_required
def adjustment_data(request, emp_id):
    employee = get_object_or_404(Employee, id=emp_id)

    draw = safe_int(request.GET.get('draw'), 1)
    start = safe_int(request.GET.get('start'), 0)
    length = safe_int(request.GET.get('length'), 10)
    search_value = request.GET.get('search[value]', '')

    queryset = Adjustment.objects.filter(employee=employee)

    if search_value:
        queryset = queryset.filter(
            Q(name__icontains=search_value) |
            Q(type__icontains=search_value) |
            Q(amount__icontains=search_value) |
            Q(month__icontains=search_value) |
            Q(status__icontains=search_value) |
            Q(remarks__icontains=search_value) |
            Q(created_at__icontains=search_value)
        )

    total_records = Adjustment.objects.filter(employee=employee).count()
    filtered_records = queryset.count()

    columns = ['name', 'type', 'amount', 'details', 'cutoff_month', 'status', 'remarks', 'created_at']
    order_col_index = safe_int(request.GET.get('order[0][column]'), 0)
    order_dir = request.GET.get('order[0][dir]', 'asc')

    if 0 <= order_col_index < len(columns):
        order_column = 'month' if columns[order_col_index] == 'cutoff_month' else columns[order_col_index]
    else:
        order_column = 'created_at'

    if order_dir == 'desc':
        order_column = f'-{order_column}'

    queryset = queryset.order_by(order_column)[start:start + length]

    data = []

    user_role = str(request.session.get('role', '')).lower()

    # List of roles that should NOT see buttons
    restricted_roles = [
        'employee',
        'preparator_meo_s',
        'preparator_meo_e',
        'preparator_meo_w',
        'preparator_meo_n'
    ]

    for adj in queryset:
        details = f"{int(adj.details)} minutes" if adj.name == "Late" and adj.details.isdigit() else adj.details

        if adj.type.lower() == "income":
            adjustment_type = "<span style='color:green; font-weight:bold;'>Income</span>"
        else:
            adjustment_type = "<span style='color:red; font-weight:bold;'>Deduction</span>"

        amount = (
            f"<span style='color:red; font-weight:bold;'>(₱{adj.amount:,.2f})</span>"
            if adj.type == "Deduction"
            else f"<span style='color:green; font-weight:bold;'>₱{adj.amount:,.2f}</span>"
        )

        if adj.status.lower() == "approved":
            status_display = "<span style='color:green; font-weight:bold;'>Approved</span>"
        elif adj.status.lower() == "returned":
            status_display = "<span style='color:red; font-weight:bold;'>Returned</span>"
        elif adj.status.lower() == "archived":
            status_display = "<span style='color:gray; font-weight:bold;'>Archived</span>"
        elif adj.status.lower() == "pending":
            status_display = "<span style='color:orange; font-weight:bold;'>Pending</span>"
        else:
            status_display = f"<span style='font-weight:bold;'>{adj.status}</span>"

        if adj.status.lower() == "returned":
            buttons = "<span style='color:red; font-weight:bold;'>Returned</span>"
        elif adj.status.lower() == "archived":
            buttons = "<span style='color:gray; font-weight:bold;'>Archived</span>"
        elif adj.status.lower() == "approved":
                buttons = "<span style='color:green; font-weight:bold;'>Approved</span>"
        else:
            buttons = 'Checking'

        if (user_role not in restricted_roles):
            if adj.status.lower() == "pending":
                buttons = f"""
                    <button class="btn btn-sm btn-success" data-id="{adj.id}" onclick="approveAdjustment({adj.id})">Approve</button>
                    <button class="btn btn-sm btn-warning" data-id="{adj.id}" onclick="returnAdjustment({adj.id})">Return</button>
                """
        
        if user_role in restricted_roles:
            if adj.status.lower() == "returned" and adj.name.lower() == "late":
                buttons = f"""
                <button class="btn btn-sm btn-info"
                    data-id="{ adj.id }"
                    data-month="{ adj.month }"
                    data-cutoff="{ adj.cutoff }"
                    data-name="{ adj.name }"
                    data-type="{ adj.type }"
                    data-amount="{ adj.amount }"
                    data-details="{ adj.details }"
                    data-remarks="{ adj.remarks }"
                    data-employee_id="{adj.employee_id}"
                    onclick="editAdjustmentLate(this)">
                        Edit Late Adjustment
                </button>
                """
            elif adj.status.lower() == "returned":
                buttons = f"""
                <button class="btn btn-sm btn-info"
                    data-id="{ adj.id }"
                    data-month="{ adj.month }"
                    data-cutoff="{ adj.cutoff }"
                    data-name="{ adj.name }"
                    data-type="{ adj.type }"
                    data-amount="{ adj.amount }"
                    data-details="{ adj.details }"
                    data-remarks="{ adj.remarks }"
                    data-employee_id="{adj.employee_id}"
                    onclick="editAdjustment(this)">
                        Edit Adjustment
                </button>
        """


        data.append({
            "name": adj.name,
            "type": adjustment_type,
            "amount": amount,
            "details": details,
            "cutoff_month": f"{adj.month} - {adj.cutoff} - {adj.cutoff_year}",
            "status": status_display,
            "remarks": adj.remarks,
            "created_at": adj.created_at.strftime('%Y-%m-%d %I:%M %p'),
            "action": buttons,
        })


    return JsonResponse({
        "draw": draw,
        "recordsTotal": total_records,
        "recordsFiltered": filtered_records,
        "data": data
    })

@login_required
def adjustment_approve(request, adj_id):
    adjustment = get_object_or_404(Adjustment, id=adj_id)

    if request.method == "POST":
        adjustment.status = "Approved"
        adjustment.save()

        return JsonResponse({"success": True, "message": "Adjustment approved successfully!"})

@login_required
def adjustment_return(request, adj_id):
    adjustment = get_object_or_404(Adjustment, id=adj_id)

    if request.method == "POST":
        adjustment.status = "Returned"
        adjustment.save()

        return JsonResponse({"success": True, "message": "Adjustment returned successfully!"})
    return

# Removed the Archiving Function for now
# @login_required
# def adjustment_archive(request, adj_id):
#     adjustment = get_object_or_404(Adjustment, id=adj_id)

#     if request.method == "POST":
#         adjustment.status = "Archived"
#         adjustment.save()

#         return JsonResponse({"success": True, "message": "Adjustment archived successfully!"})
#     return

# @login_required
# def adjustment_unarchive(request, adj_id):
#     adjustment = get_object_or_404(Adjustment, id=adj_id)

#     if request.method == "POST":
#         adjustment.status = "Pending"
#         adjustment.save()

#         return JsonResponse({"success": True, "message": "Adjustment Unarchived successfully!"})
#     return
