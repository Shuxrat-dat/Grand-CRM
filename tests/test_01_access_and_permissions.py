import pytest
from django.test import TestCase, Client
from django.urls import reverse
from django.core.exceptions import PermissionDenied
from apps.accounts.models import User, CenterSettings


class AccessAndPermissionsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create_user(
            username='owner_user',
            password='password123',
            role=User.Role.OWNER,
            first_name='Owner',
            last_name='Boss'
        )
        self.admin = User.objects.create_user(
            username='admin_user',
            password='password123',
            role=User.Role.ADMIN,
            first_name='Admin',
            last_name='Staff'
        )
        self.settings = CenterSettings.get_settings()

    def test_owner_access_allowed(self):
        """1. Owner has access to owner-only views and dashboard."""
        self.client.login(username='owner_user', password='password123')

        # Owner can access dashboard
        res = self.client.get(reverse('dashboard'))
        self.assertEqual(res.status_code, 200)

        # Owner can access salaries
        res = self.client.get(reverse('payroll:salaries_list'))
        self.assertEqual(res.status_code, 200)

        # Owner can access expenses
        res = self.client.get(reverse('finance:expenses_list'))
        self.assertEqual(res.status_code, 200)

        # Owner can access cash flow report
        res = self.client.get(reverse('reporting:cash_flow'))
        self.assertEqual(res.status_code, 200)

        # Owner can access settings and user management
        res = self.client.get(reverse('accounts:admin_users_list'))
        self.assertEqual(res.status_code, 200)
        res = self.client.get(reverse('accounts:settings'))
        self.assertEqual(res.status_code, 200)

    def test_admin_blocked_from_restricted_views(self):
        """2. Admin is strictly forbidden from accessing salaries, expenses, profit reports, settings."""
        self.client.login(username='admin_user', password='password123')

        # Admin CAN access allowed operations
        res = self.client.get(reverse('dashboard'))
        self.assertEqual(res.status_code, 200)
        res = self.client.get(reverse('students:students_list'))
        self.assertEqual(res.status_code, 200)
        res = self.client.get(reverse('academics:groups_list'))
        self.assertEqual(res.status_code, 200)
        res = self.client.get(reverse('billing:payments_list'))
        self.assertEqual(res.status_code, 200)

        # Admin CANNOT access salaries
        res = self.client.get(reverse('payroll:salaries_list'))
        self.assertEqual(res.status_code, 403)

        # Admin CANNOT access expenses
        res = self.client.get(reverse('finance:expenses_list'))
        self.assertEqual(res.status_code, 403)

        # Admin CANNOT access cash flow or accrual profit reports
        res = self.client.get(reverse('reporting:cash_flow'))
        self.assertEqual(res.status_code, 403)
        res = self.client.get(reverse('reporting:accrual_profit'))
        self.assertEqual(res.status_code, 403)

        # Admin CANNOT access user management or center settings
        res = self.client.get(reverse('accounts:admin_users_list'))
        self.assertEqual(res.status_code, 403)
        res = self.client.get(reverse('accounts:settings'))
        self.assertEqual(res.status_code, 403)
