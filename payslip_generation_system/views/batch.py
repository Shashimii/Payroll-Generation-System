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

    print(batch_name)

    return JsonResponse({'error': 'Invalid request method'}, status=405)
