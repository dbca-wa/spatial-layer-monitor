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


logger = logging.getLogger(__name__)


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
        logger.error('Error fetching new hash from url %s Error: %s', url, error)
        return 
    
    if new_hash and new_hash != current_hash:
        new_layer_data = SpatialMonitorHistory.objects.create(layer=layer, hash=new_hash)
        layer.last_checked = new_layer_data.created_at
        layer.save()
        if image:
            new_layer_data.image.save(f'{layer.name}_{new_layer_data.created_at}.png', ContentFile(image.getvalue()))

        if current_hash:
            success, message = publish_layer_update(new_layer_data)
            if not success:
                logger.error('Error updating layer %s', message)

    elif new_hash:
        logger.info('New hash is the same as the last hash')
        if latest_hash_history and not latest_hash_history.synced_at:
            success, message = publish_layer_update(latest_hash_history)
            if not success:
                logger.error('Error updating layer %s', message)
    else:
        layer.description = error
        layer.save()
        logger.error('Error fetching new hash from url %s', url)




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
    endpoint = settings.SPATIAL_UPDATE_ENDPOINT
    username = settings.SPATIAL_UPDATE_USERNAME
    password = settings.SPATIAL_UPDATE_PASSWORD
    logger.info(f"Publish Layer Update: {history_layer.layer}")
    gs_response = ""
    gs_response_boolean = True
    try:
        if not endpoint:
            logger.error("Update Endpoint not set")
            return False, "Update Endpoint not set"

        if not history_layer.layer.kmi_layer_name:
            logger.error(f"Layer {history_layer.layer.id} doesn't have a layer name set")
            return False, f"Layer {history_layer.layer.id} doesn't have a layer name set"

        geoserver_group = history_layer.layer.geoserver_group
        if geoserver_group >= 0:
            gs = GeoServer.objects.filter(geoserver_group=geoserver_group,enabled=True)
            for g in gs:
                auhentication = HTTPBasicAuth(g.username, g.password)
                url = endpoint + '/geoserver/gwc/rest/masstruncate'
                data = f"<truncateLayer><layerName>{history_layer.layer.kmi_layer_name}</layerName></truncateLayer>"

                response = requests.post(url=g.endpoint_url, auth=auhentication, data=data, headers={'content-type': 'text/xml'})
                if response.status_code == 200:
                    history_layer.sync()
                    gs_response = "Success: " + g.endpoint_url+" -> " + str(response.status_code)
                    # return True, f"Success: {response.status_code}"
                else:
                    logger.error(response.content)
                    gs_response = "Error: " + g.endpoint_url+" -> " + str(response.status_code)
                    gs_response_boolean = False
                    # return False, f"Error: {response.status_code}"
            return gs_response_boolean, gs_response
        else:
            logger.error(f"Layer {history_layer.layer.id} has an invalid geoserver group")
            return False, f"Layer {history_layer.layer.id} has an invalid geoserver group"        
    except Exception as e:
        logger.error(e)
        return False, f"Error: {e}"
