from django.shortcuts import render, redirect, get_object_or_404
from django.db import connection
from django.db import transaction
from django.http import JsonResponse
from django.contrib import messages
from django.utils.dateparse import parse_date
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from payslip_generation_system.models import Employee, EmployeeAttachment, UserRole
from django.contrib.auth.models import User

from django.contrib.auth.decorators import login_required
@login_required
def index(request):
    return render(request, 'payslip/index.html')

def create(request):
    return render(request, 'payslip/create.html')

def adjustment(request, emp_id):
    
    return render(request, 'payslip/adjustment.html')

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

    # Section map
    section_map = {
        'preparator_meo_s': 43,
        'preparator_meo_e': 42,
        'preparator_meo_w': 44,
        'preparator_meo_n': 45
    }

    # Base queryset
    if user_role == 'admin':
        queryset = Employee.objects.values(*fields)
    elif user_role in section_map:
        queryset = Employee.objects.filter(section=section_map[user_role]).values(*fields)
    else:
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
                <i class="fas fa-list"></i>
            </button> 
            """
        ])

    return JsonResponse({
        'draw': draw,
        'recordsTotal': total_records,
        'recordsFiltered': total_records,
        'data': data
    })