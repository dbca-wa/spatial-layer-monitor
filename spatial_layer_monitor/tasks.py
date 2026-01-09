import uuid
from .models  import SpatialMonitorHistory, SpatialMonitor,GeoServer

import requests
import requests.cookies
from requests.auth import HTTPBasicAuth

import logging
import hashlib
import io

from django.core.files.base import ContentFile
from django.conf import settings
from django.utils import timezone


logger = logging.getLogger(__name__)

# Maximum length for storing purge status messages to avoid saving excessively long or sensitive content
MAX_PURGE_STATUS_LENGTH = 1024

def _save_purge_result(history_layer, success: bool, message: str):
    """Save purge attempt metadata and status on the history layer.

    On success reset retry count and call `sync()` to set synced_at and update parent layer.
    On failure increment retry count and save an error message.
    Messages are truncated to `MAX_PURGE_STATUS_LENGTH`.
    """
    now = timezone.now()
    history_layer.last_purge_attempt_at = now
    safe_msg = str(message)[:MAX_PURGE_STATUS_LENGTH]

    # Update new explicit status and message fields
    history_layer.status_message = safe_msg

    if success:
        history_layer.status = SpatialMonitorHistory.Status.SUCCESS
        history_layer.purge_retry_count = 0
        history_layer.purge_status = f"Success: {safe_msg}"
        # sync() updates synced_at and layer.last_updated and persists the model
        history_layer.sync()
    else:
        history_layer.status = SpatialMonitorHistory.Status.FAILED
        history_layer.purge_retry_count = (history_layer.purge_retry_count or 0) + 1
        history_layer.purge_status = f"Error: {safe_msg}"
        history_layer.save()


def run_check_all_layers():
    layers = SpatialMonitor.objects.all().prefetch_related('hashes')
    for layer in layers:
        check_layer(layer)


def check_layer(layer: SpatialMonitor):
    url = layer.url
    latest_hash_history = layer.get_latest_hash()
    current_hash = latest_hash_history.hash if latest_hash_history else None

    new_hash, image, error = fetch_current_image_hash(url, auth=layer.get_authentication())

    if error:
        layer.description = error
        layer.save()
        logger.error(f"Error fetching new hash for layer '{layer.name}' (ID: {layer.id}) from {url}. Error: {error}")
        return 
    
    if new_hash and new_hash != current_hash:
        # Create a new history record for the detected change
        logger.info(f"New hash detected for layer '{layer.name}' (ID: {layer.id}): {new_hash}. Previous hash: {current_hash}")
        new_layer_data = SpatialMonitorHistory.objects.create(layer=layer, hash=new_hash)
        layer.last_checked = new_layer_data.created_at
        layer.save()
        if image:
            new_layer_data.image.save(f'{layer.name}_{new_layer_data.created_at}.png', ContentFile(image.getvalue()))
        # Note: Purge operations are handled exclusively by process_purge_retries_command
    elif new_hash:
        # Hash is the same as the last one, no action needed
        logger.info(f"Hash for layer '{layer.name}' (ID: {layer.id}) is unchanged: {new_hash}")
    else:
        # Error occurred while fetching hash
        layer.description = error
        layer.save()
        logger.error(f"Failed to fetch hash for layer '{layer.name}' (ID: {layer.id}) from {url}")


def fetch_current_image_hash(url: str, auth: tuple = None):
    
    auhentication = HTTPBasicAuth(auth[0], auth[1]) if auth else None
    
    response = requests.get(url, auth=auhentication)

    if response.status_code == 200:
        image = io.BytesIO(response.content)
        image_hash = get_image_hash(image)
        return image_hash, image, None
    else:
        return None, None, f"Error: {response.status_code}"
    

def get_image_hash(image):
    img_hash = hashlib.md5()
    while chunk := image.read(8192):
        img_hash.update(chunk)
    return img_hash.hexdigest()


def publish_layer_update(history_layer: SpatialMonitorHistory):
    logger.info(f"Starting Publish Layer Update for layer '{history_layer.layer.name}' (ID: {history_layer.layer.id})")
    
    # Set status to PROCESSING at the start of the operation
    history_layer.status = SpatialMonitorHistory.Status.PROCESSING
    history_layer.save(update_fields=['status'])

    all_success = True
    results = []
    try:
        if not history_layer.layer.kmi_layer_name:
            msg = f"Layer {history_layer.layer.id} doesn't have a layer name set"
            logger.error(msg)
            _save_purge_result(history_layer, False, msg)
            return False, msg

        geoserver_group = history_layer.layer.geoserver_group
        if geoserver_group >= 0:
            gs = GeoServer.objects.filter(geoserver_group=geoserver_group,enabled=True)
            if not gs.exists():
                msg = f"No enabled GeoServers found for group {geoserver_group} (Layer: {history_layer.layer.name})"
                logger.warning(msg)
                _save_purge_result(history_layer, False, msg)
                return False, msg

            for g in gs:
                auhentication = HTTPBasicAuth(g.username, g.password)
                url = g.endpoint_url + '/geoserver/gwc/rest/masstruncate'
                data = f"<truncateLayer><layerName>{history_layer.layer.kmi_layer_name}</layerName></truncateLayer>"

                logger.info(f"Sending purge request to GeoServer: {url}")
                try:
                    response = requests.post(url=url, auth=auhentication, data=data, headers={'content-type': 'text/xml'})
                    if response.status_code == 200:
                        msg = f"Success: {g.endpoint_url} -> {response.status_code}"
                        logger.info(msg)
                        results.append(msg)
                    else:
                        logger.error(f"Failed purge request to {g.endpoint_url}. Status: {response.status_code}. Content: {response.content}")
                        msg = f"Error: {g.endpoint_url} -> {response.status_code}"
                        results.append(msg)
                        all_success = False
                except Exception as e:
                    logger.error(f"Exception during purge request to {g.endpoint_url}: {e}")
                    msg = f"Exception: {g.endpoint_url} -> {e}"
                    results.append(msg)
                    all_success = False
            
            final_msg = " | ".join(results)
            _save_purge_result(history_layer, all_success, final_msg)
            logger.info(f"Completed Publish Layer Update for layer '{history_layer.layer.name}'. Final Success Status: {all_success}")
            return all_success, final_msg
        else:
            msg = f"Layer {history_layer.layer.id} has an invalid geoserver group"
            logger.error(msg)
            _save_purge_result(history_layer, False, msg)
            return False, msg        
    except Exception as e:
        logger.error(e)
        msg = f"Error: {e}"
        _save_purge_result(history_layer, False, msg)
        return False, msg
