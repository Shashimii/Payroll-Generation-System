import factory
from faker import Faker
from payslip_generation_system.models import Batch

fake = Faker()

class BatchFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Batch

    batch_number = factory.Sequence(lambda n: n + 1)
    batch_name = factory.LazyAttribute(lambda x: f"Batch {fake.word().title()} {fake.random_int(min=1, max=999)}")
    batch_assigned_office = factory.Iterator(['denr_ncr_nec', 'denr_ncr_prcmo', 'meo_s', 'meo_e', 'meo_w', 'meo_n'])
