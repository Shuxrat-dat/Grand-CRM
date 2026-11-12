import os
from django.core.management.base import BaseCommand
from apps.accounts.models import User, CenterSettings


class Command(BaseCommand):
    help = "Creates the initial Owner (Ega) user, Admin user and default CenterSettings if they do not exist"

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, default=os.getenv('INITIAL_OWNER_USERNAME', 'owner'), help="Owner username (login)")
        parser.add_argument('--password', type=str, default=os.getenv('INITIAL_OWNER_PASSWORD', ''), help="Owner password (or INITIAL_OWNER_PASSWORD env)")
        parser.add_argument('--phone', type=str, default='+998901234567', help="Owner phone")
        parser.add_argument('--name', type=str, default="Grand Ta'lim Markazi", help="Center name")
        parser.add_argument('--force', action='store_true', help="Force overwrite password even if user already exists")

    def handle(self, *args, **options):
        username = options['username']
        password = options['password']
        phone = options['phone']
        center_name = options['name']
        force = options['force']

        # Ensure CenterSettings
        settings_obj, settings_created = CenterSettings.objects.get_or_create(
            id=1,
            defaults={
                'center_name': center_name,
                'proration_policy': CenterSettings.ProrationPolicy.FULL_MONTH,
                'payment_due_day': 5,
                'currency': "UZS",
            }
        )
        if not settings_created and center_name != "Grand Ta'lim Markazi":
            settings_obj.center_name = center_name
            settings_obj.save(update_fields=['center_name'])

        self._ensure_user(
            username=username, password=password, force=force, label="Ega (Owner)",
            defaults={
                'role': User.Role.OWNER, 'is_staff': True, 'is_superuser': True,
                'phone': phone, 'first_name': "Bosh", 'last_name': "Direktor",
            },
            force_fields={'role': User.Role.OWNER, 'is_staff': True, 'is_superuser': True},
        )

        # Administrator account (no is_staff: no access to Django's /admin/)
        self._ensure_user(
            username=os.getenv('INITIAL_ADMIN_USERNAME', 'admin'),
            password=os.getenv('INITIAL_ADMIN_PASSWORD', ''),
            force=force, label="Administrator",
            defaults={
                'role': User.Role.ADMIN, 'is_staff': False, 'is_superuser': False,
                'phone': '+998907654321', 'first_name': "Katta", 'last_name': "Administrator",
            },
            force_fields={},
        )

    def _ensure_user(self, username, password, force, label, defaults, force_fields):
        """
        Creates the user only when an explicit password was supplied via
        env/argument. No built-in default passwords; passwords are never printed.
        """
        user = User.objects.filter(username=username).first()
        if user is None:
            if not password:
                self.stdout.write(self.style.WARNING(
                    f"{label} '{username}' yaratilmadi: parol berilmagan "
                    "(INITIAL_*_PASSWORD o'zgaruvchisini o'rnating). Standart parol ishlatilmaydi."
                ))
                return
            user = User(username=username, **defaults)
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"{label} '{username}' yaratildi."))
        elif force and password:
            user.set_password(password)
            for k, v in force_fields.items():
                setattr(user, k, v)
            user.save()
            self.stdout.write(self.style.WARNING(f"{label} '{username}' paroli yangilandi (--force)."))
        else:
            self.stdout.write(self.style.NOTICE(f"{label} '{username}' allaqachon mavjud. O'zgarishsiz qoldirildi."))
