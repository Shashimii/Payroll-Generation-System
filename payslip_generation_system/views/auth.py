from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.http import JsonResponse
from django.contrib import messages
from payslip_generation_system.models import UserRole

from django.contrib.auth.decorators import login_required
from payslip_generation_system.decorators import restrict_roles
from django.contrib.auth.models import User
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

@login_required
def logout(request):
    auth_logout(request)
    return redirect('login')

@login_required
@restrict_roles(disallowed_roles=['preparator_denr_nec','preparator_meo_s','preparator_meo_e','preparator_meo_w','preparator_meo_n','accounting','checker','employee'])
def create(request):
    return render(request, 'auth/create.html')

@login_required
@restrict_roles(disallowed_roles=['preparator_denr_nec','preparator_meo_s','preparator_meo_e','preparator_meo_w','preparator_meo_n','accounting','checker','employee'])
def store(request):
    if request.method == 'POST':
        # Formatted
        username = request.POST.get('fullname')
        password = request.POST.get('password')
        role = request.POST.get('role')

        # Existing Check
        if User.objects.filter(username=username).exists():
            messages.error(request, 'A user already exists.')
            return redirect('create')
        
        # Employee Account
        username = username
        password =  password if password else 'defaultpass'
        user = User(username=username)
        user.set_password(password) # hashes the password
        user.save()

        # Employee Role
        UserRole.objects.create(
            user=user,
            role=role
        )

        # Change it on the database using this roles
        # admin (System IT only)
        # checker
        # preparator_denr_nec
        # preparator_meo_s = 43
        # preparator_meo_e = 42
        # preparator_meo_w = 44
        # preparator_meo_n = 45
        # employee (default)

        # Redirect
        messages.success(request, 'Account Added successfully!')
        return redirect('create')
    
    return JsonResponse({'error': 'Invalid request method'}, status=400)
    