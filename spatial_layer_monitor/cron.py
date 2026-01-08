from django_cron import CronJobBase, Schedule
from django.core.management import call_command
from django.conf import settings

class ProcessSpatialLayersChangesCronJob(CronJobBase):
    """Cron job to process spatial layer changes."""
    RUN_EVERY_MINS = settings.CRON_INTERVAL_CHECK_LAYERS
    schedule = Schedule(run_every_mins=RUN_EVERY_MINS)
    code = 'spatial_layer_monitor.process_spatial_layers_changes'

    def do(self):
        call_command('process_spatial_layers_changes_command')

class ProcessPurgeRetriesCronJob(CronJobBase):
    """Cron job to retry failed purge attempts."""
    RUN_EVERY_MINS = settings.CRON_INTERVAL_PURGE_RETRIES
    schedule = Schedule(run_every_mins=RUN_EVERY_MINS)
    code = 'spatial_layer_monitor.process_purge_retries'

    def do(self):
        call_command('process_purge_retries_command')
