from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.http import JsonResponse

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