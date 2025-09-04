from django.db.models import Q
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.conf import settings
from django_cryptography.fields import encrypt
from django.utils.html import format_html
from datetime import datetime
import uuid

upload_storage = FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT)

def to_history_images(instance, extension):
    extension = extension.split('.')[-1]
    extension = extension.lower() if extension else 'png'
    return f'history_images/{instance.id}_{str(uuid.uuid4())}.{extension}'

class RequestAuthentication(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    username = models.CharField(max_length=200)
    password =  encrypt(models.CharField(max_length=512, blank=True, default=""))
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name + ' - ' + self.username


class SpatialMonitor(models.Model):

    GEOSERVER_GROUP = ((0,'KMI'),
                    (1,'KB'),
                    )

    url = models.URLField(max_length=1000)
    name = models.CharField(max_length=200)
    geoserver_group = models.IntegerField(choices=GEOSERVER_GROUP,default=0)
    kmi_layer_name = models.CharField(max_length=200, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    last_updated = models.DateTimeField(blank=True, null=True)

    last_checked = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    authentication = models.ForeignKey(RequestAuthentication, on_delete=models.CASCADE, blank=True, null=True)

    def get_latest_hash(self):
        return self.hashes.all().order_by('-id').first()
    
    def get_authentication(self):
        if self.authentication:
            return (self.authentication.username, self.authentication.password)
        return None

    def __str__(self):
        return self.name

class SpatialMonitorHistory(models.Model):
    layer = models.ForeignKey(SpatialMonitor, on_delete=models.CASCADE, related_name='hashes')
    hash = models.CharField(max_length=500)
    image = models.ImageField(upload_to=to_history_images, storage=upload_storage,blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    synced_at =  models.DateTimeField(blank=True, null=True)

    @property
    def image_tag(self):
        if not self.image:
            return format_html('<span>No Image</span>')
        return format_html('<a href="%s" target="_blank"> <img src="%s" width="150" height="150" /></a>' % (self.image.url, self.image.url))

    def sync(self):
        self.synced_at = datetime.now()
        self.layer.last_updated = datetime.now()
        self.layer.save()
        self.save()

    def __str__(self):
        return f'{self.layer.name} - {self.hash} - {self.created_at}'


class SpatialQueue(models.Model):
    layer = models.ForeignKey(SpatialMonitorHistory, on_delete=models.CASCADE, related_name='queue_item')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.layer.layer.name} - {self.created_at}'



class GeoServer(models.Model):
    """Model for an Geoserver Pool."""
    GEOSERVER_GROUP = ((0,'KMI'),
                    (1,'KB'),
                    )

    name = models.CharField(max_length=200, null=True)
    geoserver_group = models.IntegerField(choices=GEOSERVER_GROUP,default=0)
    endpoint_url = models.CharField(max_length=500)    
    username = models.TextField()
    password = models.TextField()
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)