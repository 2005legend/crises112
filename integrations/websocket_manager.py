connections = []

async def connect(ws):
    await ws.accept()
    connections.append(ws)

async def broadcast(data):
    for c in connections:
        await c.send_json(data)