from django.core.management.base import BaseCommand
from spatial_layer_monitor.models import SpatialMonitorHistory
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Initializes the new status field for existing records based on synced_at and last_purge_attempt_at.'

    def handle(self, *args, **options):
        msg_start = "Starting status initialization..."
        self.stdout.write(msg_start)
        logger.info(msg_start)

        # 1. Success: synced_at is set
        try:
            success_count = SpatialMonitorHistory.objects.filter(
                synced_at__isnull=False
            ).update(status=SpatialMonitorHistory.Status.SUCCESS)
            msg = f"Successfully updated {success_count} records to SUCCESS."
            self.stdout.write(self.style.SUCCESS(msg))
            logger.info(msg)
        except Exception as e:
            err_msg = f"Failed to update SUCCESS records: {e}"
            self.stderr.write(err_msg)
            logger.error(err_msg)

        # 2. Failed: synced_at is null, but we have attempted a purge
        try:
            failed_count = SpatialMonitorHistory.objects.filter(
                synced_at__isnull=True,
                last_purge_attempt_at__isnull=False
            ).update(status=SpatialMonitorHistory.Status.FAILED)
            msg = f"Successfully updated {failed_count} records to FAILED."
            self.stdout.write(self.style.SUCCESS(msg))
            logger.info(msg)
        except Exception as e:
            err_msg = f"Failed to update FAILED records: {e}"
            self.stderr.write(err_msg)
            logger.error(err_msg)

        # 3. Pending: both are null
        try:
            pending_count = SpatialMonitorHistory.objects.filter(
                synced_at__isnull=True,
                last_purge_attempt_at__isnull=True
            ).update(status=SpatialMonitorHistory.Status.PENDING)
            msg = f"Successfully updated {pending_count} records to PENDING."
            self.stdout.write(self.style.SUCCESS(msg))
            logger.info(msg)
        except Exception as e:
            err_msg = f"Failed to update PENDING records: {e}"
            self.stderr.write(err_msg)
            logger.error(err_msg)

        msg_end = "Status initialization process finished."
        self.stdout.write(msg_end)
        logger.info(msg_end)
