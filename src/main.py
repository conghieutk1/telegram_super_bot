import logging
import time

from util import load_json, save_json, should_run
from telegram_client import TelegramClient
from gold_fx_service import GoldFxService
from weather_service import WeatherService
from news_service import NewsService


CONFIG_PATH = "config.json"
SECRETS_PATH = "secrets.json"
STATE_PATH = "state.json"


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def main() -> None:
    setup_logging()
    logger = logging.getLogger("telegram_super_bot")

    config = load_json(CONFIG_PATH)
    secrets = load_json(SECRETS_PATH)
    state = load_json(STATE_PATH, default={})

    bot_token = secrets.get("telegram_bot_token")
    chat_id = secrets.get("telegram_chat_id")

    if not bot_token or chat_id is None:
        logger.error("Missing telegram_bot_token or telegram_chat_id in secrets.json")
        return

    tg = TelegramClient(bot_token=bot_token, chat_id=chat_id)

    gold_fx_service = GoldFxService(config.get("gold_fx", {}), secrets)
    weather_service = WeatherService(config.get("weather", {}), secrets)
    news_service = NewsService(config.get("news", {}), secrets)

    schedule_cfg = config.get("schedule", {})
    gold_fx_interval = int(schedule_cfg.get("gold_fx_interval_min", 60))
    weather_interval = int(schedule_cfg.get("weather_interval_min", 60))
    news_interval = int(schedule_cfg.get("news_interval_min", 120))
    loop_sleep_seconds = int(schedule_cfg.get("loop_sleep_seconds", 30))

    logger.info("Telegram Super Bot started. Chat ID: %s", chat_id)

    # try:
    #     while True:
    # now_ts = time.time()

    # GOLD / FX
    # if should_run(state, "gold_fx_last_sent", gold_fx_interval, now_ts):
    logger.info("Running gold_fx_service...")
    try:
        msg = gold_fx_service.build_summary()
        if msg:
            tg.send_message(msg)
            # state["gold_fx_last_sent"] = now_ts
    except Exception as exc:
        logger.exception("gold_fx_service error: %s", exc)

    # WEATHER
    # if should_run(state, "weather_last_sent", weather_interval, now_ts):
    logger.info("Running weather_service...")
    try:
        msg = weather_service.build_summary()
        if msg:
            tg.send_message(msg)
            # state["weather_last_sent"] = now_ts
    except Exception as exc:
        logger.exception("weather_service error: %s", exc)

    # NEWS
    # if should_run(state, "news_last_sent", news_interval, now_ts):
    logger.info("Running news_service...")
    try:
        msg = news_service.build_summary(state)
        if msg:
            tg.send_message(msg)
            # state["news_last_sent"] = now_ts
    except Exception as exc:
        logger.exception("news_service error: %s", exc)

    # Lưu state mỗi vòng (hoặc có thể tối ưu: chỉ lưu nếu có thay đổi)
    # save_json(STATE_PATH, state)

    # time.sleep(loop_sleep_seconds)

    # except KeyboardInterrupt:
    #     logger.info("Bot stopped by user (KeyboardInterrupt).")


if __name__ == "__main__":
    main()
