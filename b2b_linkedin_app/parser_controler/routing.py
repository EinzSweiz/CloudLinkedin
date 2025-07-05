from django.urls import re_path
from . import consumers
from parser_controler.test_consumer import TestWebSocketConsumer

websocket_urlpatterns = [
    re_path(r'^ws/test/$', TestWebSocketConsumer.as_asgi()),
    re_path(r'ws/parsing/(?P<request_id>\w+)/$', consumers.ParsingConsumer.as_asgi()),
]
