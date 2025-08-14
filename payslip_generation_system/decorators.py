# Like Middleware in Laravel
from django.shortcuts import redirect
from functools import wraps

def restrict_roles(disallowed_roles=None):
    if disallowed_roles is None:
        disallowed_roles = []

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user_role = str(request.session.get('role') or '').strip().lower()

            if user_role in (role.lower() for role in disallowed_roles):
                return redirect('login')

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator