import json
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

app = FastAPI()

class ConnectionManager:
    def __init__(self):
        # Список всех активных WebSocket-соединений
        self.active_connections: list[WebSocket] = []
        # Сопоставление соединения с именем игрока
        self.player_map = {}
        self.player_counter = 1
        # История сообщений текущей сессии
        self.chat_history = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.player_map[websocket] = f"Игрок {self.player_counter}"
        self.player_counter += 1
        return self.player_map[websocket]

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            self.player_map.pop(websocket, None)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except:
                pass

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    player_name = await manager.connect(websocket)
    
    # Отправляем приветственное сообщение только вошедшему игроку
    await websocket.send_text(json.dumps({
        "type": "system", 
        "text": f"Вы подключились! Ваше имя в комнате: {player_name}"
    }))
    
    # Оповещаем всех остальных участников
    await manager.broadcast({
        "type": "system", 
        "text": f"Новый участник вошел в комнату допроса."
    })

    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # Обработка сброса игры (перезапуск комнаты)
            if message_data.get("type") == "reset":
                manager.player_counter = 1
                manager.chat_history = []
                for i, conn in enumerate(manager.active_connections, start=1):
                    manager.player_map[conn] = f"Игрок {i}"
                    manager.player_counter += 1
                    await conn.send_text(json.dumps({
                        "type": "system", 
                        "text": f"Игра сброшена! Ваше новое имя: Игрок {i}"
                    }))
                await manager.broadcast({"type": "clear_chat"})
                continue

            # Обработка стандартного текстового сообщения от человека
            if message_data.get("type") == "message":
                user_text = message_data.get("text", "")
                if not user_text.strip():
                    continue
                    
                user_message = {
                    "type": "message", 
                    "sender": player_name, 
                    "text": user_text
                }
                
                # Логируем в консоль сервера для отладки
                print(f"[ЧАТ] {player_name}: {user_text}", flush=True)
                
                manager.chat_history.append(user_message)
                await manager.broadcast(user_message)
                   
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast({
            "type": "system", 
            "text": f"Один из участников покинул комнату."
        })

@app.get("/")
async def get():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())
