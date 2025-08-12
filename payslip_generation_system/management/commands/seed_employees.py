from django.core.management.base import BaseCommand
from payslip_generation_system.factories import EmployeeFactory, BatchFactory

class Command(BaseCommand):
    help = 'Seed the database with dummy employee data -Shashimii'

    def add_arguments(self, parser):
        parser.add_argument('--total', type=int, default=100)
        parser.add_argument('--batches', type=int, default=10)

    def handle(self, *args, **kwargs):
        total_employees = kwargs['total']
        total_batches = kwargs['batches']
        
        self.stdout.write(f'Creating {total_batches} batches...')
        
        # Create batches first
        batches = []
        for _ in range(total_batches):
            batch = BatchFactory.create()
            batches.append(batch)
            self.stdout.write(f'Created batch: {batch}')
        
        self.stdout.write(f'Seeding {total_employees} employees...')

        # Create employees with batch numbers and matching assigned offices
        for i in range(total_employees):
            # Assign employees to batches in a round-robin fashion
            batch_index = i % len(batches)
            selected_batch = batches[batch_index]
            
            # Use create_with_batch to ensure office alignment
            employee = EmployeeFactory.create_with_batch(batch=selected_batch)
            self.stdout.write(f'Created employee: {employee.fullname} (Batch #{employee.batch_number}, Office: {employee.assigned_office})')

        self.stdout.write(self.style.SUCCESS(f'Successfully seeded {total_employees} employees across {total_batches} batches.'))
