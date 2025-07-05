import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import ParserRequest
import logging

logger = logging.getLogger(__name__)

class ParsingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.request_id = self.scope['url_route']['kwargs']['request_id']
        self.parsing_group_name = f'parsing_{self.request_id}'

        # Join parsing group
        await self.channel_layer.group_add(
            self.parsing_group_name,
            self.channel_name
        )

        await self.accept()
        logger.info(f"WebSocket connected for parsing request {self.request_id}")

    async def disconnect(self, close_code):
        # Leave parsing group
        await self.channel_layer.group_discard(
            self.parsing_group_name,
            self.channel_name
        )
        logger.info(f"WebSocket disconnected for parsing request {self.request_id}")

    # Receive message from WebSocket (not used for this case)
    async def receive(self, text_data):
        pass

    # Send parsing updates to WebSocket
    async def parsing_update(self, event):
        """Send real-time parsing updates to WebSocket clients"""
        await self.send(text_data=json.dumps({
            'type': 'parsing_update',
            'action': event['action'],
            'message': event['message'],
            'data': event.get('data', {}),
            'timestamp': event['timestamp']
        }))

    # Send log messages to WebSocket  
    async def log_message(self, event):
        """Send real-time log messages to WebSocket clients"""
        await self.send(text_data=json.dumps({
            'type': 'log_message',
            'level': event['level'],
            'logger': event['logger'],
            'message': event['message'],
            'timestamp': event['timestamp']
        }))