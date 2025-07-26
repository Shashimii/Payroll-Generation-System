from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.http import JsonResponse
from payslip_generation_system.models import UserRole

from django.contrib.auth.decorators import login_required

# Auth
def login(request):
    if request.user.is_authenticated:
        return redirect('dashboard') 
    
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(request, username=username, password=password)
        if user is not None:
            auth_login(request, user)
            
            try:
                role_obj = UserRole.objects.get(user=user)
                request.session['role'] = role_obj.role
            except UserRole.DoesNotExist:
                request.session['role'] = None

            return JsonResponse({
                'success': True, 
                'message': 'Login successful', 
                'redirect_url': '/dashboard/',
            })

        else:
            return render(request, 'auth/login.html', {'error': 'Invalid Credentials'})
    
    return render(request, 'auth/login.html')

def logout(request):
    auth_logout(request)
    return redirect('login')