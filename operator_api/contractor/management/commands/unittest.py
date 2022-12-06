from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command


class Command(BaseCommand):
    help = 'Run unittesting suit, not an integration testing'

    def handle(self, *args, **options):
        args = ["--parallel"]
        kwargs = {
            "pattern": "unittests*.py"
        }
        try:
            call_command("test", *args, **kwargs)
        except Exception as e:
            CommandError(e)
