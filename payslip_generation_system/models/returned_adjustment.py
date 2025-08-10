from django.utils.timezone import now
from django.db import models
from payslip_generation_system.models import Employee

class ReturnedAdjustment(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    # Name of the adjustment (e.g., Bonus, Deductions)
    name = models.CharField(max_length=255)
    
    # Type of adjustment (e.g., Income, Deduction)
    TYPE_CHOICES = [
        ('Income', 'Income'),
        ('Deduction', 'Deduction'),
    ]
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    
    # Amount of the adjustment (e.g., 1000.00, -500.00)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Details about the adjustment (e.g., reason or description)
    details = models.TextField()
    
    # Computation method for the adjustment (e.g., Percentage, Flat Amount)
    computation = models.CharField(max_length=50)
    
    # Month and Period for the adjustment
    month = models.CharField(max_length=20, choices=[ 
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
        ('December', 'December')
    ], null=True) 
    
     # Store Month (January - December)
    cutoff = models.CharField(max_length=10, choices=[('1st', '1st'), ('2nd', '2nd')])  # Cutoff (1st or 2nd)

    # Store Year
    cutoff_year = models.CharField(max_length=50)

    # Status Pending / Approved / Returned
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Returned', 'Returned'),
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    
    # Remarks or notes about the adjustment (e.g., any extra information)
    remarks = models.TextField(null=True, blank=True)
    
    # Batch Number
    batch_number = models.BigIntegerField(null=True, blank=True, default=None)

    # Assigned Office
    assigned_office = models.CharField(max_length=100, blank=True, null=True)

    # Timestamps to track when adjustments were created/updated
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Adjustment'
        verbose_name_plural = 'Adjustments'
