# render the batch page
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from ..models.batch import Batch

def get_user_assigned_office(user_role):
    """
    Helper function to get the assigned office based on user role
    """
    role_to_office = {
        'preparator_denr_nec': 'denr_ncr_nec',
        'preparator_denr_prcmo': 'denr_ncr_prcmo',
        'preparator_meo_s': 'meo_s',
        'preparator_meo_e': 'meo_e',
        'preparator_meo_w': 'meo_w',
        'preparator_meo_n': 'meo_n',
    }
    return role_to_office.get(user_role)

def get_formatted_office_name(office_code):
    """
    Helper function to get formatted office name from office code
    """
    office_name_map = {
        'denr_ncr_nec': 'DENR NCR NEC',
        'denr_ncr_prcmo': 'DENR NCR PRCMO',
        'meo_s': 'MEO South',
        'meo_e': 'MEO East',
        'meo_w': 'MEO West',
        'meo_n': 'MEO North',
    }
    return office_name_map.get(office_code, office_code)

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
        
        try:
            # Get the current user's role and assigned office
            user_role = request.session.get('role', '')
            assigned_office = get_user_assigned_office(user_role)
            
            # If no assigned office found, use a default
            if not assigned_office:
                assigned_office = 'general'
            
            # Check if batch name already exists for this specific office
            if Batch.objects.filter(batch_name=batch_name, batch_assigned_office=assigned_office).exists():
                return JsonResponse({
                    'success': False,
                    'error': f'A batch with the name "{batch_name}" already exists in your office ({assigned_office}). Please choose a different name.'
                })
            
            # Get the next available batch number (globally unique across all offices)
            last_batch = Batch.objects.order_by('-batch_number').first()
            next_batch_number = 1 if not last_batch else last_batch.batch_number + 1
            
            # Create the new batch
            new_batch = Batch.objects.create(
                batch_number=next_batch_number,
                batch_name=batch_name,
                batch_assigned_office=assigned_office
            )
            
            return JsonResponse({
                'success': True,
                'batch_name': new_batch.batch_name,
                'batch_number': new_batch.batch_number,
                'assigned_office': new_batch.batch_assigned_office,
                'message': 'Batch created successfully!'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'An error occurred while creating the batch: {str(e)}'
            })
    
    # If not POST request, return method not allowed
    return JsonResponse({'error': 'Invalid request method'}, status=405)

@login_required
def get_user_office(request):
    """
    Get the current user's assigned office
    """
    if request.method == 'GET':
        user_role = request.session.get('role', '')
        assigned_office = get_user_assigned_office(user_role)
        formatted_office_name = get_formatted_office_name(assigned_office) if assigned_office else 'Unknown'
        
        return JsonResponse({
            'success': True,
            'assigned_office': assigned_office or 'general',
            'formatted_office_name': formatted_office_name
        })
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)

@login_required
def list_batches(request):
    """
    List batches created by the current user (based on their assigned office)
    """
    if request.method == 'GET':
        try:
            user_role = request.session.get('role', '')
            assigned_office = get_user_assigned_office(user_role)
            
            if not assigned_office:
                return JsonResponse({
                    'success': False,
                    'error': 'User role not found or invalid.'
                })
            
            # Get batches for the user's assigned office
            batches = Batch.objects.filter(batch_assigned_office=assigned_office).order_by('-created_at')
            
            batches_data = []
            for batch in batches:
                batches_data.append({
                    'id': batch.id,
                    'batch_number': batch.batch_number,
                    'batch_name': batch.batch_name,
                    'batch_assigned_office': batch.batch_assigned_office,
                    'created_at': batch.created_at.isoformat(),
                    'updated_at': batch.updated_at.isoformat()
                })
            
            return JsonResponse({
                'success': True,
                'batches': batches_data
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'An error occurred: {str(e)}'
            })
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)

@login_required
def update_batch(request):
    """
    Update an existing batch
    """
    if request.method == 'POST':
        batch_id = request.POST.get('batch_id')
        batch_name = request.POST.get('batch_name')
        
        # Validate required fields
        if not batch_id or not batch_name:
            return JsonResponse({
                'success': False,
                'error': 'Batch ID and name are required.'
            })
        
        try:
            # Get the current user's role and assigned office
            user_role = request.session.get('role', '')
            assigned_office = get_user_assigned_office(user_role)
            
            if not assigned_office:
                return JsonResponse({
                    'success': False,
                    'error': 'User role not found or invalid.'
                })
            
            # Get the batch and verify it belongs to the user's office
            try:
                batch = Batch.objects.get(id=batch_id, batch_assigned_office=assigned_office)
            except Batch.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Batch not found or access denied.'
                })
            
            # Check if the new name already exists in this office (excluding current batch)
            if Batch.objects.exclude(id=batch_id).filter(batch_name=batch_name, batch_assigned_office=assigned_office).exists():
                return JsonResponse({
                    'success': False,
                    'error': f'A batch with the name "{batch_name}" already exists in your office ({assigned_office}). Please choose a different name.'
                })
            
            # Update the batch
            batch.batch_name = batch_name
            batch.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Batch updated successfully!'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'An error occurred: {str(e)}'
            })
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)

@login_required
def delete_batch(request):
    """
    Delete an existing batch
    """
    if request.method == 'POST':
        batch_id = request.POST.get('batch_id')
        
        # Validate required fields
        if not batch_id:
            return JsonResponse({
                'success': False,
                'error': 'Batch ID is required.'
            })
        
        try:
            # Get the current user's role and assigned office
            user_role = request.session.get('role', '')
            assigned_office = get_user_assigned_office(user_role)
            
            if not assigned_office:
                return JsonResponse({
                    'success': False,
                    'error': 'User role not found or invalid.'
                })
            
            # Get the batch and verify it belongs to the user's office
            try:
                batch = Batch.objects.get(id=batch_id, batch_assigned_office=assigned_office)
            except Batch.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Batch not found or access denied.'
                })
            
            # Delete the batch
            batch.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'Batch deleted successfully!'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'An error occurred: {str(e)}'
            })
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)
