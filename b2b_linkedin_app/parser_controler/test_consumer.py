# parser_controler/test_consumer.py
from channels.generic.websocket import AsyncWebsocketConsumer
import json

class TestWebSocketConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        await self.send(text_data=json.dumps({"message": "Test WebSocket connected."}))

    async def disconnect(self, close_code):
        pass

    async def receive(self, text_data):
        data = json.loads(text_data)
        await self.send(text_data=json.dumps({
            "echo": data.get("message"),
            "type": data.get("type", "message"),
            "timestamp": data.get("timestamp")
        }))
