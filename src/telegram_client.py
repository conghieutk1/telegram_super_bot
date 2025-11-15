import logging
from typing import Optional

from telegram import Bot
from telegram.error import TelegramError


class TelegramClient:
    """
    Wrapper đơn giản cho Telegram Bot API (chỉ gửi message vào 1 chat_id).
    """

    def __init__(
        self,
        bot_token: str,
        chat_id: int,
        default_parse_mode: Optional[str] = "Markdown",
    ) -> None:
        self.bot = Bot(token=bot_token)
        self.chat_id = chat_id
        self.default_parse_mode = default_parse_mode
        self.logger = logging.getLogger(self.__class__.__name__)

    def send_message(
        self,
        text: str,
        disable_notification: bool = False,
        parse_mode: Optional[str] = None,
    ) -> None:
        """
        Gửi 1 message:
        - Mặc định dùng parse_mode = default_parse_mode (Markdown / HTML / None)
        - Nếu Telegram báo lỗi parse (Can't parse entities) thì retry lại không dùng parse_mode.
        """
        if not text:
            return

        # Ưu tiên parse_mode truyền vào, nếu không thì dùng default
        effective_parse_mode = parse_mode if parse_mode is not None else self.default_parse_mode

        try:
            self.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode=effective_parse_mode,
                disable_notification=disable_notification,
            )
            self.logger.info(
                "Sent message to chat_id=%s (parse_mode=%s)",
                self.chat_id,
                effective_parse_mode,
            )
        except TelegramError as exc:
            msg = str(exc)
            # Nếu lỗi liên quan đến parse entities, retry không dùng parse_mode
            if "Can't parse entities" in msg or "can't parse entities" in msg:
                self.logger.warning(
                    "Failed to send message with parse_mode=%s: %s. "
                    "Retrying without parse_mode...",
                    effective_parse_mode,
                    msg,
                )
                try:
                    self.bot.send_message(
                        chat_id=self.chat_id,
                        text=text,
                        parse_mode=None,
                        disable_notification=disable_notification,
                    )
                    self.logger.info(
                        "Sent message to chat_id=%s without parse_mode after retry",
                        self.chat_id,
                    )
                    return
                except TelegramError as exc2:
                    self.logger.error(
                        "Failed to send message even without parse_mode: %s",
                        exc2,
                    )
            else:
                self.logger.error("Failed to send message: %s", exc)
