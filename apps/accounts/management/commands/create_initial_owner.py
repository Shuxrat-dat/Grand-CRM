from django.core.management.base import BaseCommand
from apps.accounts.models import User, CenterSettings


class Command(BaseCommand):
    help = "Creates the initial Owner (Ega) user and default CenterSettings"

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, default='owner', help="Owner username (login)")
        parser.add_argument('--password', type=str, default='owner123', help="Owner password")
        parser.add_argument('--phone', type=str, default='+998901234567', help="Owner phone")
        parser.add_argument('--name', type=str, default="Grand Ta'lim Markazi", help="Center name")

    def handle(self, *args, **options):
        username = options['username']
        password = options['password']
        phone = options['phone']
        center_name = options['name']

        # Ensure CenterSettings
        settings_obj, created = CenterSettings.objects.get_or_create(id=1)
        settings_obj.center_name = center_name
        settings_obj.proration_policy = CenterSettings.ProrationPolicy.FULL_MONTH
        settings_obj.payment_due_day = 5
        settings_obj.currency = "UZS"
        settings_obj.save()

        # Create or update Owner
        user, user_created = User.objects.get_or_create(username=username)
        user.role = User.Role.OWNER
        user.is_staff = True
        user.is_superuser = True
        user.phone = phone
        user.first_name = "Bosh"
        user.last_name = "Direktor"
        user.set_password(password)
        user.save()

        action = "yaratildi" if user_created else "yangilandi"
        self.stdout.write(self.style.SUCCESS(
            f"Muvaffaqiyatli: Ega (Owner) foydalanuvchisi '{username}' {action}.\n"
            f"Login: {username}\nParol: {password}\nRoli: Ega (Owner)\n"
            f"Markaz: {settings_obj.center_name}"
        ))
