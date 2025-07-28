from django.db import models
import os
from django.contrib.auth.models import User

# Employee
class Employee(models.Model):
    # Personal Info
    fullname = models.CharField(max_length=255)
    birthdate = models.DateField()
    address = models.TextField(blank=True, null=True)
    contact = models.CharField(max_length=20, blank=True, null=True)

    EDUCATION_CHOICES = [
        ('High School', 'High School'),
        ('Vocational', 'Vocational'),
        ('Post Graduate', 'Post Graduate'),
        ('College', 'College'),
    ]
    education = models.CharField(max_length=20, choices=EDUCATION_CHOICES)

    GENDER_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),
    ]
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)

    # Employment Details
    employee_number = models.CharField(max_length=50)
    position = models.CharField(max_length=100)
    date_hired = models.DateField(blank=True, null=True)

    division = models.CharField(max_length=20, blank=True, null=True)
    section = models.CharField(max_length=20, blank=True, null=True)

    # Salary Details
    FUND_CHOICES = [
        ('regular', 'Regular'),
        ('prcmo', 'PRCMO'),
        ('manila_bay', 'Manila Bay'),
    ]
    fund_source = models.CharField(max_length=20, choices=FUND_CHOICES)

    salary = models.DecimalField(max_digits=10, decimal_places=2, null=True)

    BOOLEAN_CHOICES = [
        ('yes', 'Yes'), 
        ('no', 'No')
    ]
    tax_declaration = models.CharField(max_length=3, choices=BOOLEAN_CHOICES)
    eligibility = models.CharField(max_length=3, choices=BOOLEAN_CHOICES)
    # employee account data
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    ASSIGNED_OFFICE_CHOICES = [
        ('denr_ncr_nec', 'DENR NCR NEC'),
        ('meo_s', 'MEO WEST'),
        ('meo_e', 'MEO EAST'),
        ('meo_w', 'MEO WEST'),
        ('meo_n', 'MEO NORTH')
    ]

    assigned_office = models.CharField(max_length=100, choices=ASSIGNED_OFFICE_CHOICES, blank=True, null=True)

    def __str__(self):
        return f"{self.employee_number} - {self.fullname} - {self.position}"
    
# Attachments
def generate_filename(instance, filename):
    employee_name = instance.employee.fullname.replace(' ', '_')
    base_name, extension = os.path.splitext(filename)
    new_filename = f"{employee_name}_{base_name}{extension}"
    return os.path.join('employee_attachments', new_filename)

class EmployeeAttachment(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='attachments')

    # Use the custom function to generate a random filename for each uploaded file
    file = models.FileField(upload_to=generate_filename)  # Attach to the 'employee_attachments/' folder

    def delete(self, *args, **kwargs):
        # Delete the file from the file system
        if self.file and os.path.isfile(self.file.path):
            os.remove(self.file.path)
        super().delete(*args, **kwargs)
        
    def __str__(self):
        return self.file.name