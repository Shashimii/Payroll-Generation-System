from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),
    # Employee
    path('employee/', views.employee.index, name='employee'),
    path('employee/create', views.employee.create, name='employee_create'),
    path('employee/store', views.employee.store, name='employee_store'),
    # Payslip
    path('payslip/', views.payslip.index, name='payslip'),
    path('payslip/create', views.payslip.create, name='payslip_create'),
]
