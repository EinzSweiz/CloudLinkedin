# b2b_linkedin_app/asgi.py - ENHANCED VERSION
import os
import django
from django.core.asgi import get_asgi_application

# Set Django settings module FIRST
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'b2b_linkedin_app.settings')

# Initialize Django ASGI application early to ensure the AppRegistry
# is populated before importing code that may import ORM models
django.setup()
django_asgi_app = get_asgi_application()

# NOW import WebSocket routing after Django is initialized
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import parser_controler.routing

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(
            parser_controler.routing.websocket_urlpatterns
        )
    ),
})

# Debug: Print routing patterns to verify they're loaded
print("🔗 WebSocket URL patterns loaded:")
for pattern in parser_controler.routing.websocket_urlpatterns:
    print(f"   - {pattern.pattern}")