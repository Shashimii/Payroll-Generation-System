from django.db import models

class ReturnRemark(models.Model):
    remark = models.TextField(blank=True, null=True) 

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

    assigned_office = models.CharField(max_length=100, blank=True, null=True)
    class Meta:
        unique_together = ['cutoff', 'cutoff_month', 'cutoff_year', 'batch_number', 'assigned_office']
        ordering = ['remark', 'cutoff_year', 'cutoff_month', 'cutoff', 'batch_number',]
    
    def __str__(self):
        return f"Batch {self.batch_number} ({self.cutoff_month} {self.cutoff}, {self.cutoff_year}) - {self.assigned_office or 'All Offices'}"