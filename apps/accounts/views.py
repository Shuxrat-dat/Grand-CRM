from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import LoginForm, AdminUserForm, CenterSettingsForm
from .models import User, CenterSettings
from .decorators import owner_required
from apps.audit.services import log_audit


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            log_audit(
                actor=user,
                action='LOGIN',
                entity_type='User',
                entity_id=user.id,
                reason="Foydalanuvchi tizimga kirdi",
                ip_address=request.META.get('REMOTE_ADDR')
            )
            messages.success(request, f"Xush kelibsiz, {user.get_full_name() or user.username}!")
            return redirect('dashboard')
        else:
            messages.error(request, "Login yoki parol noto'g'ri kiritildi.")
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {'form': form})


@login_required
def logout_view(request):
    logout(request)
    messages.info(request, "Tizimdan muvaffaqiyatli chiqdingiz.")
    return redirect('accounts:login')


@owner_required
def admin_users_list_view(request):
    users = User.objects.all().order_by('-date_joined')
    return render(request, 'accounts/admin_users_list.html', {'users': users})


@owner_required
def admin_user_create_view(request):
    if request.method == 'POST':
        form = AdminUserForm(request.POST)
        if form.is_valid():
            user = form.save()
            log_audit(
                actor=request.user,
                action='CREATE',
                entity_type='User',
                entity_id=user.id,
                changes_after={'username': user.username, 'role': user.role},
                reason="Yangi xodim yaratildi"
            )
            messages.success(request, f"Foydalanuvchi '{user.username}' muvaffaqiyatli yaratildi.")
            return redirect('accounts:admin_users_list')
    else:
        form = AdminUserForm()

    return render(request, 'accounts/admin_user_form.html', {'form': form, 'title': "Yangi xodim qo'shish"})


@owner_required
def admin_user_edit_view(request, user_id):
    target_user = get_object_or_404(User, id=user_id)

    # Protect against demoting the sole owner by accident
    if request.method == 'POST':
        old_role = target_user.role
        form = AdminUserForm(request.POST, instance=target_user)
        if form.is_valid():
            user = form.save()
            log_audit(
                actor=request.user,
                action='UPDATE',
                entity_type='User',
                entity_id=user.id,
                changes_before={'role': old_role},
                changes_after={'role': user.role, 'is_active': user.is_active},
                reason="Xodim ma'lumotlari tahrirlandi"
            )
            messages.success(request, f"'{user.username}' ma'lumotlari yangilandi.")
            return redirect('accounts:admin_users_list')
    else:
        form = AdminUserForm(instance=target_user)

    return render(request, 'accounts/admin_user_form.html', {
        'form': form,
        'title': f"Xodimni tahrirlash: {target_user.username}",
        'target_user': target_user
    })


@owner_required
def admin_user_toggle_view(request, user_id):
    if request.method == 'POST':
        target_user = get_object_or_404(User, id=user_id)
        if target_user == request.user:
            messages.error(request, "O'z hisobingizni faolsizlantira olmaysiz.")
            return redirect('accounts:admin_users_list')

        target_user.is_active = not target_user.is_active
        target_user.save(update_fields=['is_active'])
        status_text = "faollashtirildi" if target_user.is_active else "faolsizlantirildi"

        log_audit(
            actor=request.user,
            action='STATUS_CHANGE',
            entity_type='User',
            entity_id=target_user.id,
            changes_after={'is_active': target_user.is_active},
            reason=f"Foydalanuvchi {status_text}"
        )
        messages.success(request, f"'{target_user.username}' {status_text}.")
    return redirect('accounts:admin_users_list')


@owner_required
def center_settings_view(request):
    settings_obj = CenterSettings.get_settings()
    if request.method == 'POST':
        form = CenterSettingsForm(request.POST, instance=settings_obj)
        if form.is_valid():
            form.save()
            log_audit(
                actor=request.user,
                action='UPDATE',
                entity_type='CenterSettings',
                entity_id=settings_obj.id,
                changes_after={
                    'proration_policy': settings_obj.proration_policy,
                    'payment_due_day': settings_obj.payment_due_day
                },
                reason="Tizim sozlamalari yangilandi"
            )
            messages.success(request, "Tizim sozlamalari muvaffaqiyatli saqlandi.")
            return redirect('accounts:settings')
    else:
        form = CenterSettingsForm(instance=settings_obj)

    return render(request, 'accounts/settings.html', {'form': form, 'settings': settings_obj})
