# render the batch page
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from ..models.batch import Batch

@login_required
def index(request):
        return render(request, 'batch/create.html', {
    })

@login_required
def create(request):
    if request.method == 'POST':
        batch_name = request.POST.get('batch_name')
        
        # Validate required fields
        if not batch_name:
            return JsonResponse({
                'success': False,
                'error': 'Batch name is required.'
            })
        
        # Check if batch name already exists
        if Batch.objects.filter(batch_name=batch_name).exists():
            return JsonResponse({
                'success': False,
                'error': 'A batch with this name already exists.'
            })
        
        try:
            # Get the next available batch number
            last_batch = Batch.objects.order_by('-batch_number').first()
            next_batch_number = 1 if not last_batch else last_batch.batch_number + 1
            
            # Create the new batch
            new_batch = Batch.objects.create(
                batch_number=next_batch_number,
                batch_name=batch_name,
                batch_assigned_office='Default Office'  # You can add this field to your form if needed
            )
            
            return JsonResponse({
                'success': True,
                'batch_name': new_batch.batch_name,
                'batch_number': new_batch.batch_number,
                'message': 'Batch created successfully!'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'An error occurred: {str(e)}'
            })
    
    # If not POST request, return method not allowed
    return JsonResponse({'error': 'Invalid request method'}, status=405)
