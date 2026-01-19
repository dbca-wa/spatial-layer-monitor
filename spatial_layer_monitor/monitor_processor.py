

# Third-Party
import os
import logging
import subprocess
from datetime import datetime
# Local
from spatial_layer_monitor import settings
from .models import SpatialMonitor
from .tasks import run_check_all_layers, check_layer
logger = logging.getLogger(__name__)

class MonitorProcessor():

    def __init__(self):
        pass

    def monitor_layers(self):
        
        current_datetime = datetime.now().astimezone()
        seen_datetime = datetime.strftime(current_datetime, '%Y-%m-%d %H:%M:%S')
        logger.info(f"Monitoring Layers {seen_datetime}")
        try:
            layers = SpatialMonitor.objects.filter(active=True).prefetch_related('hashes')
            logger.info(f"Layers to be checked on: {layers.count()}")
            for layer in layers:
                check_layer(layer)
           
        except Exception as e:
            logger.error(e)