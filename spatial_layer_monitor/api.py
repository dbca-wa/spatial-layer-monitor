import threading
import logging

from django.http import JsonResponse, HttpRequest, HttpResponse
from django.views import View
from rest_framework import routers, serializers, viewsets
from rest_framework.decorators import api_view, permission_classes
from .permissions import IsInOfficersGroup
from .tasks import run_check_all_layers

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsInOfficersGroup])
def mock_kmi_service(request):
    logger.info(request.data)
    logger.info(vars(request.POST))
    return JsonResponse({'message': 'Success'}, status=200)
    

@api_view(['POST'])
@permission_classes([IsInOfficersGroup])
def run_batch_import(request):
    x = threading.Thread(target=run_check_all_layers)
    x.run()
    return JsonResponse({'message': 'Success'}, status=200)


@api_view(['POST'])
def test_xml_request(request: HttpRequest):
    print(request.content_type)
    print(vars(request.headers))
    response  =  HttpResponse()
    response.headers = {
        'content-type': "text/xml"
    }
    response.status_code = 201
    return response



from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.negotiation import BaseContentNegotiation

class IgnoreClientContentNegotiation(BaseContentNegotiation):
    def select_parser(self, request, parsers):
        """
        Select the first parser in the `.parser_classes` list.
        """
        return parsers[0]

    def select_renderer(self, request, renderers, format_suffix):
        """
        Select the first renderer in the `.renderer_classes` list.
        """
        return (renderers[0], renderers[0].media_type)
class NoNegotiationView(APIView):
    """
    An example view that does not perform content negotiation.
    """
    content_negotiation_class = IgnoreClientContentNegotiation

    def get(self, request, format=None):
        print(request.content_type)
        print(vars(request.headers))
        response  =  HttpResponse()
        response.headers = {
        'content-type': "text/xml"
        }
        return response