from functools import wraps
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.contrib import messages


def owner_required(view_func):
    """
    Decorator for views that checks that the user is logged in and has OWNER role.
    Server-side enforced check.
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_owner:
            messages.error(request, "Ushbu sahifaga kirish uchun faqat Ega (Owner) huquqi talab qilinadi.")
            raise PermissionDenied("Faqat Ega uchun ruxsat etilgan.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def admin_or_owner_required(view_func):
    """
    Decorator for views that checks that the user is logged in and has ADMIN or OWNER role.
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if not (request.user.is_admin_staff or request.user.is_owner):
            messages.error(request, "Tizimga kirish huquqiga ega emassiz.")
            raise PermissionDenied("Ruxsat yo'q.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view
