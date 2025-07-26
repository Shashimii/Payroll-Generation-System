from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

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
    path('employee/edit/<int:emp_id>/', views.employee.edit, name='employee_edit'),
    path('employee/update/<int:emp_id>/', views.employee.update, name='employee_update'),
    path('employee/destroy/<int:emp_id>/', views.employee.destroy, name='employee_destroy'),
    path('employee/attachment-delete/<int:attachment_id>/', views.employee.attachment_delete, name='employee_attachment_delete'),
    path('employee/data', views.employee.data, name='employee_data'),
    path('employee/show/<int:emp_id>/', views.employee.show, name='employee_show'),
    # Payslip
    path('payslip/', views.payslip.index, name='payslip'),
    path('payslip/create', views.payslip.create, name='payslip_create'),
    path('payslip/employee-data', views.payslip.employee_data, name='payslip_employee_data'),
    path('payslip/adjustment/<int:emp_id>/', views.payslip.adjustment, name='payslip_adjustment'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)  