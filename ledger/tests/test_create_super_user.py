from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase


class TestCreateSuperUserCommand(TestCase):
    """
    Example test which asserts that a superuser with username admin
    is created by the createsuperusercommand
    """
    def test(self):
        get_user_model().objects.all().delete()
        call_command('createsuperuser')

        self.assertEqual(
            list(get_user_model().objects.all()),
            [get_user_model().objects.get(username='admin',
                                          is_superuser=True)]
        )
