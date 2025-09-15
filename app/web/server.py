# app/web/server.py
from fastapi import FastAPI
from telegram import Bot

def create_app(bot: Bot) -> FastAPI:
    app = FastAPI(title="EU Liquidation Radar")

    @app.get("/healthz")
    async def healthz():
        return {"ok": True}

    # Placeholder for webhook:
    # @app.post("/telegram/webhook")
    # async def webhook(update: dict):
    #     await bot.process_update(Update.de_json(update, bot))
    #     return {"ok": True}

    return app
