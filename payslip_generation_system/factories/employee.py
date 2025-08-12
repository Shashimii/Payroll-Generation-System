import factory
from faker import Faker
from payslip_generation_system.models import Employee, Batch

fake = Faker()

class EmployeeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Employee

    fullname = factory.LazyAttribute(lambda x: fake.name())
    birthdate = factory.LazyAttribute(lambda x: fake.date_of_birth(minimum_age=20, maximum_age=60))
    address = factory.LazyAttribute(lambda x: fake.address())
    contact = factory.LazyAttribute(lambda x: fake.phone_number())
    education = factory.Iterator(['High School', 'Vocational', 'College', 'Post Graduate'])
    gender = factory.Iterator(['Male', 'Female'])
    employee_number = factory.LazyAttribute(lambda x: fake.unique.bothify(text='######'))
    position = factory.LazyAttribute(lambda x: fake.job())
    date_hired = factory.LazyAttribute(lambda x: fake.date_this_decade())
    division = factory.Iterator(['Admin', 'Finance', 'Tech'])
    section = factory.Iterator(['A', 'B', 'C'])
    fund_source = factory.Iterator(['regular', 'prcmo', 'manila_bay'])
    salary = factory.LazyAttribute(lambda x: fake.pydecimal(left_digits=5, right_digits=2, positive=True))
    tax_declaration = factory.Iterator(['yes', 'no'])
    eligibility = factory.Iterator(['yes', 'no'])
    has_philhealth = factory.Iterator(['yes', 'no'])
    employee_type = factory.Iterator(['COS', 'ER'])
    
    # These will be set when creating with a specific batch
    assigned_office = None
    batch_number = None
    user = None

    @classmethod
    def create_with_batch(cls, **kwargs):
        """Create an employee with a specific batch, ensuring office alignment"""
        batch = kwargs.pop('batch', None)
        if batch:
            kwargs['batch_number'] = batch.batch_number
            kwargs['assigned_office'] = batch.batch_assigned_office
        return cls.create(**kwargs)
