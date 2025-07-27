from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Index
    path('', views.login, name='login'),
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
    path('payslip/generate', views.payslip.generate, name='payslip_generate'),
    path('payslip/employee-data', views.payslip.employee_data, name='payslip_employee_data'),
    path('payslip/adjustment/<int:emp_id>/', views.payslip.adjustment, name='payslip_adjustment'),
    path('payslip/adjustment/add/<int:emp_id>/', views.payslip.adjustment_add, name='adjustment_add'),
    path('payslip/adjustments/data/<int:emp_id>/', views.payslip.adjustment_data, name='adjustment_data'),
    path('payslip/adjustments/approve/<int:adj_id>/', views.payslip.adjustment_approve, name='adjustment_approve'),
    path('payslip/adjustments/reject/<int:adj_id>/', views.payslip.adjustment_reject, name='adjustment_reject'),
    path('payslip/adjustments/archive/<int:adj_id>/', views.payslip.adjustment_archive, name='adjustment_archive'),
    path('payslip/adjustments/unarchive/<int:adj_id>/', views.payslip.adjustment_unarchive, name='adjustment_unarchive'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)  