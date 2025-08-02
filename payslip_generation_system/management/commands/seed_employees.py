from django.core.management.base import BaseCommand
from payslip_generation_system.factories import EmployeeFactory

class Command(BaseCommand):
    help = 'Seed the database with dummy employee data -Shashimii'

    def add_arguments(self, parser):
        parser.add_argument('--total', type=int, default=100)

    def handle(self, *args, **kwargs):
        total = kwargs['total']
        self.stdout.write(f'Seeding {total} employees...')

        for _ in range(total):
            EmployeeFactory.create()

        self.stdout.write(self.style.SUCCESS(f'Successfully seeded {total} employees.'))
