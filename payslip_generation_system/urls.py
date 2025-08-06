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
    path('create/', views.create, name='create'),
    path('store/', views.store, name='store'),
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

    # Payroll
    path('payroll/', views.payroll.index, name='payroll'),
    path('payroll/submit', views.payroll.submit, name='payroll_submit'),
    path('payroll/batch/data', views.payroll.batch_data, name='payroll_batch_data'),
    path('payroll/batch/create', views.payroll.batch_create, name='payroll_batch_create'),
    path('payroll/batch/late', views.payroll.batch_late, name='payroll_batch_late'),
    path('payroll/batch/unlate', views.payroll.batch_unlate, name='payroll_batch_unlate'),
    path('payroll/adjustment/create/<int:emp_id>/', views.payroll.adjustment_create, name='payroll_adjustment_create'),
    path('payroll/adjustment/show/<int:emp_id>/', views.payroll.adjustment_show, name='payroll_adjustment_show'),
    path('payroll/pending', views.payroll.pending, name='payroll_pending'),
    path('payroll/data', views.payroll.data, name='payroll_data'),
    path('payroll/show', views.payroll.show, name='payroll_show'),
    path('payroll/approve', views.payroll.approve, name='payroll_approve'),
    path('payroll/reject', views.payroll.reject, name='payroll_reject'),
    path('payroll/approved-list', views.payroll.approved_list, name='payroll_approved_list'),
    path('payroll/approve_data', views.payroll.approve_data, name='payroll_approve_data'),
    path('payroll/approve_show', views.payroll.approve_show, name='payroll_approve_show'),
    path('payroll/release', views.payroll.release, name='payroll_release'),

    # Payslip
    path('payslip/', views.payslip.index, name='payslip'),
    path('payslip/create', views.payslip.create, name='payslip_create'),
    path('payslip/generate', views.payslip.generate, name='payslip_generate'),
    path('payslip/employee-data', views.payslip.employee_data, name='payslip_employee_data'),
    path('payslip/adjustment/<int:emp_id>/', views.payslip.adjustment, name='payslip_adjustment'),
    path('payslip/adjustment/add/<int:emp_id>/', views.payslip.adjustment_add, name='adjustment_add'),
    path('payslip/adjustment/edit/<int:emp_id>/<int:adj_id>/', views.payslip.adjustment_edit, name='adjustment_edit'),
    path('payslip/adjustments/data/<int:emp_id>/', views.payslip.adjustment_data, name='adjustment_data'),
    path('payslip/adjustments/return/<int:adj_id>/', views.payslip.adjustment_return, name='adjustment_return'),
    path('payslip/adjustments/approve/<int:adj_id>/', views.payslip.adjustment_approve, name='adjustment_approve'),
    path('payslip/adjustments/credit/<int:adj_id>/', views.payslip.adjustment_credit, name='adjustment_credit'),
    # path('payslip/adjustments/archive/<int:adj_id>/', views.payslip.adjustment_archive, name='adjustment_archive'),
    # path('payslip/adjustments/unarchive/<int:adj_id>/', views.payslip.adjustment_unarchive, name='adjustment_unarchive'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)  