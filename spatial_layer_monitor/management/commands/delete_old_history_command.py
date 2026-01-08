from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from spatial_layer_monitor.models import SpatialMonitorHistory
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Deletes spatial layer history records older than a specified number of days"

    """
    Usage Examples:
    
    1. Delete records older than the default 90 days:
       python manage.py delete_old_history_command
    
    2. Delete records older than 120 days:
       python manage.py delete_old_history_command --days 120
    
    3. Dry run to see how many records would be deleted without actually deleting them:
       python manage.py delete_old_history_command --dry-run
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Delete records older than this many days (default is 90)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Check how many records would be deleted without actually deleting them'
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        
        threshold_date = timezone.now() - timedelta(days=days)
        
        start_msg = f"Looking for records older than {days} days (before {threshold_date})"
        self.stdout.write(start_msg)
        logger.info(f"Management Command: {start_msg}")
        
        old_records = SpatialMonitorHistory.objects.filter(created_at__lt=threshold_date)
        count = old_records.count()
        
        if count == 0:
            msg = "No old records found to delete."
            self.stdout.write(self.style.SUCCESS(msg))
            logger.info(f"Management Command: {msg}")
            return

        if dry_run:
            msg = f"[DRY RUN] {count} records would be deleted."
            self.stdout.write(self.style.WARNING(msg))
            logger.info(f"Management Command: {msg}")
        else:
            self.stdout.write(f"Deleting {count} records and associated images...")
            deleted_count = 0
            for record in old_records:
                if record.image:
                    try:
                        # Deleting the field also deletes the file from storage
                        record.image.delete(save=False)
                    except Exception as e:
                        logger.error(f"Management Command Error: Failed to delete image for record {record.id}: {e}")
                
                try:
                    record_id = record.id
                    record.delete()
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"Management Command Error: Failed to delete history record {record_id}: {e}")
            
            success_msg = f"Successfully deleted {deleted_count} records and their images."
            self.stdout.write(self.style.SUCCESS(success_msg))
            logger.info(f"Management Command: {success_msg}")
