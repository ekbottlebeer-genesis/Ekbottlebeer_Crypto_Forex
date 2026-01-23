import logging
import os

class TelegramErrorHandler(logging.Handler):
    """
    A custom logging handler that sends ERROR level messages to Telegram.
    """
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.setLevel(logging.ERROR)

    def emit(self, record):
        try:
            if not self.chat_id:
                return
            
            log_entry = self.format(record)
            msg = f"‼️ **SYSTEM ERROR ALERT** ‼️\n\n```\n{log_entry}\n```\n\n_Please check your terminal for more details._"
            
            # Use synchronous send if possible or just try/except
            self.bot.send_message(msg, chat_id=self.chat_id)
        except Exception:
            # Avoid infinite loops or crashing if telegram fails
            pass
