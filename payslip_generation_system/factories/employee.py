import factory
from faker import Faker
from payslip_generation_system.models import Employee

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
    assigned_office = factory.Iterator(['denr_ncr_nec', 'denr_ncr_prcmo', 'meo_s', 'meo_e', 'meo_w', 'meo_n'])
    has_philhealth = factory.Iterator(['yes', 'no'])
    employee_type = factory.Iterator(['COS', 'ER'])
    user = None
