from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.http import JsonResponse

from django.contrib.auth.decorators import login_required

@login_required
def index(request):
    return render(request, 'payslip/index.html')

def create(request):
    return render(request, 'payslip/create.html')
