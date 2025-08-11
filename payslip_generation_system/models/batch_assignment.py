from django.db import models
from .employee import Employee

class BatchAssignment(models.Model):
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='batchassignment'
    )

    batch_number = models.IntegerField()

    CUTOFF_MONTH_CHOICES = [
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

    cutoff_month = models.CharField(max_length=20, choices=CUTOFF_MONTH_CHOICES)

    CUTOFF_PERIOD_CHOICES = [
        ('1st', '1st'), 
        ('2nd', '2nd')
    ]

    cutoff = models.CharField(max_length=10, choices=CUTOFF_PERIOD_CHOICES)

    cutoff_year = models.CharField(max_length=50)  

    ASSIGNED_OFFICE_CHOICES = [
        ('denr_ncr_nec', 'DENR NCR NEC'),
        ('meo_s', 'MEO SOUTH'),
        ('meo_e', 'MEO EAST'),
        ('meo_w', 'MEO WEST'),
        ('meo_n', 'MEO NORTH')
    ]

    assigned_office = models.CharField(max_length=100, choices=ASSIGNED_OFFICE_CHOICES, blank=True, null=True)

    BOOLEAN_CHOICES = [
        ('YES', 'YES'), 
        ('NO', 'NO')
    ]

    late_assigned = models.CharField(max_length=10, choices=BOOLEAN_CHOICES, null=True, blank=True, default='NO')
    removed = models.CharField(max_length=10, choices=BOOLEAN_CHOICES, null=True, blank=True, default='NO')
    previous_batch = models.IntegerField(null=True, blank=True)
    cluster_number = models.IntegerField(null=True, blank=True)

    class Meta:
        unique_together = ['employee', 'cutoff', 'cutoff_month', 'cutoff_year']
        ordering = ['cutoff_year', 'cutoff_month', 'cutoff', 'assigned_office', 'batch_number', 'late_assigned', 'previous_batch']
    
    def __str__(self):
        return f"{self.employee.fullname} - Batch {self.batch_number} ({self.cutoff_month} {self.cutoff}, {self.cutoff_year}) - {self.assigned_office}"