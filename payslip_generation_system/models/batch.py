from django.db import models

class Batch(models.Model):
    batch_number = models.IntegerField(unique=True)  
    batch_name = models.CharField(max_length=100)  # Removed global unique constraint
    batch_assigned_office = models.CharField(max_length=100)   

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Allow same batch name across different offices, but prevent duplicates within the same office
        unique_together = ['batch_name', 'batch_assigned_office']

    def __str__(self):
        return f"{self.batch_name} (#{self.batch_number})"
