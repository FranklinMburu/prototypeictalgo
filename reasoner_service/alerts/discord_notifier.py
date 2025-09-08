import logging

class DiscordNotifier:
    def __init__(self, webhook_url, engine=None):
        self.webhook_url = webhook_url
        self.engine = engine
    async def notify(self, decision, decision_id=None):
        # Simulate sending a Discord notification
        logging.info(f"DiscordNotifier: would send to {self.webhook_url} decision_id={decision_id}")
        return {"ok": True, "sent": True}
