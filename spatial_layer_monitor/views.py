import threading
import urllib3
from django.http import JsonResponse
from django.views import View
from django.shortcuts import render, redirect
from rest_framework import routers, serializers, viewsets
from rest_framework.decorators import permission_classes
import urllib3.contrib
import urllib3.util
from urllib import parse


from .tasks import run_check_all_layers
from .models import SpatialMonitor, RequestAuthentication
from .permissions import IsInOfficersGroup, IsAdministratorMixin

# Home
class AddSpatialLayerInfo(IsAdministratorMixin, View):
    # Main page for adding spatial layer information
    template_name = 'spatial_layer_monitor/add_spatial_layer_info.html'

    def get(self, request, *args, **kwargs):

        auth_modes = RequestAuthentication.objects.all().only('id', 'name','username', 'created_at')
        has_error = request.GET.get('error') == 'True',
        context = {
            'title': 'Add Spatial Layer Information',
            'auth_modes': auth_modes,
            'success': request.GET.get('success') == 'True',
            'error_message': 'An error occurred' if has_error else None,
            'has_permission': IsInOfficersGroup().has_permission(request, self),
        }

        return render(request, self.template_name, context=context)
    
    def post(self, request, *args, **kwargs):
        urls = request.POST.getlist('layer_url')
        layer_name = request.POST.getlist('layer_name')
        auth_mode = request.POST.get('auth_mode')

        if not IsInOfficersGroup(request):
            return redirect('/?error=True')

        authentication = None
        if auth_mode != '':
            authentication = RequestAuthentication.objects.filter(pk=auth_mode).first()
        for (x, url) in enumerate(urls):
            urlObj = parse.urlparse(url)
            params  = parse.parse_qs(urlObj.query)

            name = params['layer'][0] if 'layer' in params else urlObj.path

            SpatialMonitor.objects.get_or_create( defaults={'name': name}, url=url, authentication=authentication, kmi_layer_name=layer_name[x])     

        return redirect('/?success=True')
