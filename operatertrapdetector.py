import asyncio
import json
import websockets
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
import uvicorn
from typing import Dict

app = FastAPI()

symbol_map = {
    "BTCUSDT": "BTC-PERP",
    "ETHUSDT": "ETH-PERP"
}

latest_signals: Dict[str, Dict] = {
    "BTCUSDT": {},
    "ETHUSDT": {}
}

async def analyze_data(symbol: str):
    delta_symbol = symbol_map[symbol]
    url = f"wss://socket.delta.exchange"

    async with websockets.connect(url, ping_interval=None) as ws:
        await ws.send(json.dumps({
            "type": "subscribe",
            "payload": {
                "channels": [
                    {"name": "v2/order_book", "symbols": [delta_symbol]},
                    {"name": "v2/trades", "symbols": [delta_symbol]}
                ]
            }
        }))

        buy_volume = 0
        sell_volume = 0
        trap_alert = "Low"

        async def send_ping():
            while True:
                try:
                    await ws.send(json.dumps({"type": "ping"}))
                except:
                    break
                await asyncio.sleep(20)

        asyncio.create_task(send_ping())

        async for msg in ws:
            try:
                data = json.loads(msg)

                if data.get("type") == "trade":
                    for trade in data['trades']:
                        if trade['taker_side'] == 'buy':
                            buy_volume += float(trade['size'])
                        else:
                            sell_volume += float(trade['size'])

                        # Basic trap logic: sudden buy bursts
                        if buy_volume > sell_volume * 2:
                            trap_alert = "Moderate"
                        if buy_volume > sell_volume * 3:
                            trap_alert = "High"

                        if buy_volume > 0 and sell_volume > 0:
                            if buy_volume > sell_volume * 1.5:
                                signal = "BUY"
                            elif sell_volume > buy_volume * 1.5:
                                signal = "SELL"
                            else:
                                signal = "EXIT"

                            latest_signals[symbol] = {
                                "signal": signal,
                                "trap": trap_alert,
                                "buy_volume": round(buy_volume, 2),
                                "sell_volume": round(sell_volume, 2)
                            }

            except Exception as e:
                print("Error:", e)

@app.get("/signal/{symbol}")
async def get_signal(symbol: str, tf: str = Query("1m")):
    if symbol not in latest_signals:
        return JSONResponse(content={"error": "Invalid symbol"}, status_code=400)
    return latest_signals[symbol]

@app.on_event("startup")
async def startup_event():
    for sym in ["BTCUSDT", "ETHUSDT"]:
        asyncio.create_task(analyze_data(sym))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=10000)
