import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests

# Thư mục project root (chứa config.json, secrets.json, state.json)
BASE_DIR = Path(__file__).resolve().parent.parent


def load_json(relative_path: str, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Đọc file JSON (nếu không tồn tại thì trả về default hoặc {}).
    """
    path = BASE_DIR / relative_path
    if not path.exists():
        logging.warning("File %s not found, using default.", path)
        return default if default is not None else {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(relative_path: str, data: Dict[str, Any]) -> None:
    """
    Ghi file JSON (pretty) ra đĩa.
    """
    path = BASE_DIR / relative_path
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def http_get_json(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    retries: int = 3,
    timeout: int = 10,
) -> Optional[Dict[str, Any]]:
    """
    GET JSON với retry đơn giản.
    """
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logging.warning("GET %s failed (attempt %s/%s): %s", url, attempt, retries, exc)
            time.sleep(1)
    logging.error("GET %s failed after %s attempts.", url, retries)
    return None


def should_run(state: Dict[str, Any], key: str, interval_min: int, now_ts: float) -> bool:
    """
    Kiểm tra đã đến lúc chạy service chưa (theo phút).
    """
    if interval_min <= 0:
        return False
    last = state.get(key)
    if last is None:
        return True
    try:
        # last là timestamp float
        last = float(last)
    except (TypeError, ValueError):
        return True
    return (now_ts - last) >= interval_min * 60
