import os
from django.core.management.base import BaseCommand
from apps.accounts.models import User, CenterSettings


class Command(BaseCommand):
    help = "Creates the initial Owner (Ega) user, Admin user and default CenterSettings if they do not exist"

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, default=os.getenv('INITIAL_OWNER_USERNAME', 'owner'), help="Owner username (login)")
        parser.add_argument('--password', type=str, default=os.getenv('INITIAL_OWNER_PASSWORD', 'owner123'), help="Owner password")
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

        # Create or verify Owner
        owner, owner_created = User.objects.get_or_create(
            username=username,
            defaults={
                'role': User.Role.OWNER,
                'is_staff': True,
                'is_superuser': True,
                'phone': phone,
                'first_name': "Bosh",
                'last_name': "Direktor",
            }
        )

        if owner_created:
            owner.set_password(password)
            owner.save()
            self.stdout.write(self.style.SUCCESS(
                f"Muvaffaqiyatli: Ega (Owner) foydalanuvchisi '{username}' yaratildi.\n"
                f"Login: {username}\nParol: {password}\nRoli: Ega (Owner)\n"
                f"Markaz: {settings_obj.center_name}"
            ))
        elif force:
            owner.set_password(password)
            owner.role = User.Role.OWNER
            owner.is_staff = True
            owner.is_superuser = True
            owner.save()
            self.stdout.write(self.style.WARNING(
                f"Ega (Owner) foydalanuvchisi '{username}' paroli va huquqlari majburiy yangilandi (--force)."
            ))
        else:
            self.stdout.write(self.style.NOTICE(
                f"Ega (Owner) foydalanuvchisi '{username}' allaqachon mavjud. Parol o'zgarishsiz qoldirildi."
            ))

        # Ensure default Admin account exists as well
        admin_username = os.getenv('INITIAL_ADMIN_USERNAME', 'admin')
        admin_password = os.getenv('INITIAL_ADMIN_PASSWORD', 'admin123')
        admin_user, admin_created = User.objects.get_or_create(
            username=admin_username,
            defaults={
                'role': User.Role.ADMIN,
                'is_staff': True,
                'is_superuser': False,
                'phone': '+998907654321',
                'first_name': "Katta",
                'last_name': "Administrator",
            }
        )
        if admin_created:
            admin_user.set_password(admin_password)
            admin_user.save()
            self.stdout.write(self.style.SUCCESS(
                f"Muvaffaqiyatli: Administrator foydalanuvchisi '{admin_username}' yaratildi.\n"
                f"Login: {admin_username}\nParol: {admin_password}\nRoli: Administrator (Admin)"
            ))
        elif force:
            admin_user.set_password(admin_password)
            admin_user.save()
            self.stdout.write(self.style.WARNING(
                f"Administrator '{admin_username}' paroli majburiy yangilandi (--force)."
            ))

