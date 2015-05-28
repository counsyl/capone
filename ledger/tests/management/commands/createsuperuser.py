from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    def handle(self, *args, **options):
        User = get_user_model()
        try:
            user = User.objects.get(username='admin')
        except User.DoesNotExist:
            user = get_user_model().objects.create_superuser(
                'admin', 'admin@example.com', 'admin')
        user.set_password('admin')
        user.save()
