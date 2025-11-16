import logging
from typing import Optional

from telegram import Bot


class TelegramClient:
    """
    Wrapper đơn giản cho Telegram Bot API (chỉ gửi message vào 1 chat_id).
    """

    def __init__(
        self,
        bot_token: str,
        chat_id: int,
        # Dùng HTML cho an toàn, dễ escape hơn Markdown
        default_parse_mode: Optional[str] = "HTML",
    ) -> None:
        self.bot = Bot(token=bot_token)
        self.chat_id = chat_id
        self.default_parse_mode = default_parse_mode
        self.logger = logging.getLogger(self.__class__.__name__)

    def send_message(self, text: str, disable_notification: bool = False) -> None:
        if not text:
            return
        try:
            self.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode=self.default_parse_mode,
                disable_notification=disable_notification,
            )
            self.logger.info("Sent message to chat_id=%s", self.chat_id)
        except Exception as exc:
            # Log rõ lỗi để sau debug nếu cần
            self.logger.error("Failed to send message: %s", exc)
