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
        Gửi message:
        - Mặc định dùng Markdown (hoặc parse_mode bạn truyền vào).
        - Nếu Telegram kêu lỗi "Can't parse entities":
          + Lần 2: bỏ hết dấu backtick ` rồi gửi lại vẫn với Markdown.
          + Lần 3 (cuối): gửi plain text (không parse_mode).
        """
        if not text:
            return

        effective_parse_mode = (
            parse_mode if parse_mode is not None else self.default_parse_mode
        )

        # Try 1: gửi nguyên bản với parse_mode
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
            return
        except TelegramError as exc:
            msg = str(exc)
            self.logger.warning(
                "Failed to send message with parse_mode=%s: %s",
                effective_parse_mode,
                msg,
            )

            # Nếu không phải lỗi parse entities thì khỏi cố nữa
            if "can't parse entities" not in msg.lower():
                self.logger.error("Failed to send message: %s", exc)
                return

        # Try 2: dọn Markdown (bỏ backtick) rồi vẫn gửi lại với Markdown
        cleaned_text = text.replace("`", "")
        try:
            self.bot.send_message(
                chat_id=self.chat_id,
                text=cleaned_text,
                parse_mode=effective_parse_mode,
                disable_notification=disable_notification,
            )
            self.logger.info(
                "Sent message to chat_id=%s after cleaning markdown (parse_mode=%s)",
                self.chat_id,
                effective_parse_mode,
            )
            return
        except TelegramError as exc2:
            self.logger.warning(
                "Still failed to send message after cleaning markdown: %s", exc2
            )

        # Try 3: gửi plain text không parse_mode (last resort)
        try:
            self.bot.send_message(
                chat_id=self.chat_id,
                text=cleaned_text,
                parse_mode=None,
                disable_notification=disable_notification,
            )
            self.logger.info(
                "Sent message to chat_id=%s without parse_mode as fallback",
                self.chat_id,
            )
        except TelegramError as exc3:
            self.logger.error(
                "Failed to send message even without parse_mode: %s", exc3
            )
