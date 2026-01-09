from django.core.management.base import BaseCommand
from spatial_layer_monitor.models import SpatialMonitorHistory
from django.db.models import Q

class Command(BaseCommand):
    help = 'Initializes the new status field for existing SpatialMonitorHistory records based on synced_at and last_purge_attempt_at.'

    def handle(self, *args, **options):
        self.stdout.write("Starting status initialization...")

        # 1. Success: synced_at is set
        success_count = SpatialMonitorHistory.objects.filter(
            synced_at__isnull=False
        ).update(status=SpatialMonitorHistory.Status.SUCCESS)
        self.stdout.write(f"Updated {success_count} records to SUCCESS.")

        # 2. Failed: synced_at is null, but we have attempted a purge
        failed_count = SpatialMonitorHistory.objects.filter(
            synced_at__isnull=True,
            last_purge_attempt_at__isnull=False
        ).update(status=SpatialMonitorHistory.Status.FAILED)
        self.stdout.write(f"Updated {failed_count} records to FAILED.")

        # 3. Pending: both are null
        pending_count = SpatialMonitorHistory.objects.filter(
            synced_at__isnull=True,
            last_purge_attempt_at__isnull=True
        ).update(status=SpatialMonitorHistory.Status.PENDING)
        self.stdout.write(f"Updated {pending_count} records to PENDING.")

        self.stdout.write(self.style.SUCCESS("Status initialization completed successfully."))
