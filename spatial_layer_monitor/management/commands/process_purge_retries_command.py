
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from spatial_layer_monitor.models import SpatialMonitorHistory
from spatial_layer_monitor.tasks import publish_layer_update
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Retries failed cache purges for spatial layers up to retry limit"

    def handle(self, *args, **options):
        now = timezone.now()
        lock_timeout = timedelta(seconds=settings.SPATIAL_PURGE_LOCK_TIMEOUT_SECONDS)
        retry_limit = settings.SPATIAL_PURGE_RETRY_LIMIT
        retry_interval = timedelta(seconds=settings.SPATIAL_PURGE_RETRY_INTERVAL_SECONDS)

        logger.info("Starting process_purge_retries_command")
        candidates = SpatialMonitorHistory.objects.filter(
            purge_retry_count__lt=retry_limit,
            synced_at__isnull=True  # Only process records that haven't been synced yet
        )
        logger.info(f"Found {candidates.count()} candidates for purge retry")

        for history in candidates:
            # Check lock
            if history.purge_processing_at and (now - history.purge_processing_at) < lock_timeout:
                logger.info(f"Skipping id={history.pk}: locked by another process (lock age: {(now - history.purge_processing_at).total_seconds()}s)")
                continue

            # Check interval
            if history.last_purge_attempt_at and (now - history.last_purge_attempt_at) < retry_interval:
                logger.info(f"Skipping id={history.pk}: retry interval not reached (last attempt: {history.last_purge_attempt_at})")
                continue

            # Try to acquire lock atomically.
            # We filter by history.purge_processing_at to ensure the lock hasn't been changed 
            # by another process (Optimistic Locking). This also allows re-acquiring expired locks.
            updated = SpatialMonitorHistory.objects.filter(
                pk=history.pk,
                purge_processing_at=history.purge_processing_at
            ).update(purge_processing_at=now)
            if updated != 1:
                logger.info(f"Skipping id={history.pk}: failed to acquire lock")
                continue  # Lock not acquired

            try:
                logger.info(f"Retrying purge for history id={history.pk} (retry={history.purge_retry_count})")
                publish_layer_update(history)
            except Exception as e:
                logger.error(f"Error during purge for id={history.pk}: {e}")
            finally:
                # Release lock
                SpatialMonitorHistory.objects.filter(pk=history.pk).update(purge_processing_at=None)
                logger.info(f"Released lock for id={history.pk}")

        logger.info("Finished process_purge_retries_command")
