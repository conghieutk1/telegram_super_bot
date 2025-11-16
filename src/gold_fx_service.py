import logging
from typing import Any, Dict, Optional
from bs4 import BeautifulSoup
from util import http_get_json
import re
import requests
from typing import Dict
import math
from datetime import datetime, timezone, timedelta
from html import escape as html_escape  # ⭐ để escape text động


class GoldFxService:
    """
    Service lấy Giá Vàng / Giá Xăng / Tỷ Giá USD.
    Ở đây mình để logic generic, bạn map vào API/thằng scrape cụ thể của bạn.
    """

    def __init__(self, config: Dict[str, Any], secrets: Dict[str, Any]) -> None:
        self.config = config
        self.access_key = secrets.get("exchangerate_access_key")
        self.logger = logging.getLogger(self.__class__.__name__)

    def _fetch_generic_price(self, url_key: str) -> Optional[float]:
        url = self.config.get(url_key)
        if not url:
            return None

        data = http_get_json(url)
        if not data:
            return None

        # TODO: chỉnh lại cho đúng với cấu trúc JSON của API thực tế
        for k in ("price", "sell", "value", "rate"):
            if k in data:
                try:
                    return float(data[k])
                except (TypeError, ValueError):
                    continue

        self.logger.warning("Cannot parse price from %s (data keys: %s)", url, list(data.keys()))
        return None

    # -------------------------------------------------------------
    # ⭐ PNJ REAL GOLD PRICE API
    # -------------------------------------------------------------
    def fetch_pnj_gold(self) -> Optional[list[tuple[str, int, int]]]:
        """
        Trả về list tuple: [(tên vàng, mua, bán), ...]
        hoặc None nếu lỗi.
        """
        url = self.config.get("pnj_gold_api_url")
        if not url:
            return None

        data = http_get_json(url)
        if not data:
            return None

        if "data" not in data:
            self.logger.error("PNJ API response missing 'data' key")
            return None

        rows = []
        for item in data["data"]:
            name = item.get("tensp")
            buy = item.get("giamua")
            sell = item.get("giaban")
            if name and buy and sell:
                rows.append((name, buy, sell))

        return rows or None

    # -------------------------------------------------------------

    def fetch_gold_price(self) -> Optional[float]:
        """
        Hàm cũ: trả về *1 con số* — không còn phù hợp cho PNJ.
        -> Ta sửa thành: trả về giá VÀNG SJC mua.
        """
        rows = self.fetch_pnj_gold()
        if not rows:
            return None

        # tìm bản ghi SJC
        for name, buy, sell in rows:
            if "SJC" in name:
                return buy  # trả về giá mua SJC làm gold index

        # fallback: lấy giá mua của dòng đầu
        return rows[0][1]

    # -------------------------------------------------------------
    # ============================================================
    # PVOIL: Lấy FULL bảng giá xăng dầu
    # ============================================================
    def fetch_pvoil_price_table(self):
        """
        Trả về list các dòng dạng:
        [
          {"stt": 1, "name": "Xăng RON 95-III", "price": 20570, "delta": 160},
          ...
        ]
        """
        url = self.config.get("gasoline_api_url")
        if not url:
            return None

        resp = requests.get(url, timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")

        # Ưu tiên table trong .oilpricescontainer, fallback sang table.table đầu tiên
        container = soup.select_one(".oilpricescontainer")
        table = None
        if container:
            table = container.find("table")
        if not table:
            table = soup.find("table", class_="table")
        if not table:
            self.logger.warning("PVOIL: không tìm thấy <table> giá xăng dầu")
            return None

        tbody = table.find("tbody") or table

        def parse_int_from_text(s: str) -> int | None:
            # "20.570 đ" -> 20570
            digits = re.sub(r"[^\d]", "", s)
            return int(digits) if digits else None

        def parse_delta(s: str) -> int | None:
            # "+160" -> 160, "-50" -> -50
            m = re.search(r"([+-]?\d+)", s)
            return int(m.group(1)) if m else None

        rows: list[dict] = []

        for tr in tbody.find_all("tr"):
            tds = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(tds) < 4:
                continue

            stt_text = tds[0]
            name = tds[1]          # cột "Mặt hàng" (colspan=2 nhưng mình chỉ cần text)
            price_text = tds[-2]   # cột giá điều chỉnh
            delta_text = tds[-1]   # cột chênh lệch

            try:
                stt = int(stt_text)
            except ValueError:
                # dòng header hoặc rác
                continue

            price = parse_int_from_text(price_text)
            delta = parse_delta(delta_text)

            rows.append(
                {
                    "stt": stt,
                    "name": name,
                    "price": price,
                    "delta": delta,
                }
            )

        return rows or None

    def fetch_gasoline_price(self) -> Optional[float]:
        return self._fetch_generic_price("gasoline_api_url")

    def fetch_usd_vnd(self) -> Optional[float]:
        return self._fetch_generic_price("usd_vnd_api_url")

    def fetch_vnd_rates(self) -> Dict[str, float]:
        url = self.config.get("exchangerate_api_url")
        if not url:
            return None

        params = {
            "source": "VND",
            "currencies": "USD,JPY,KRW,CNY",
            "access_key": self.access_key,
        }
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        rates = data["quotes"]   # USD/JPY/KRW/CNY trên 1 VND

        timestamp = data.get("timestamp")   # ⭐ lấy timestamp UTC
        self.fx_timestamp = timestamp       # ⭐ lưu vào biến instance

        result = {}
        for code, v in rates.items():
            # v = foreign_per_VND -> VND_per_foreign = 1 / v
            if v:
                result[code] = 1.0 / v

        return result

    def round_sig(self, x, sig=3):
        if x == 0:
            return 0
        return round(x, sig - int(math.floor(math.log10(abs(x)))) - 1)

    def pretty_number(self, x):
        # Format với delimiter nhưng không làm tròn lại
        if x >= 1000:
            return f"{x:,.0f}"        # Số lớn → không cần thập phân
        elif x >= 100:
            return f"{x:,.1f}"        # 100–999 → 1 số thập phân
        else:
            return f"{x:,.2f}"        # <100 → 2 số thập phân

    def convert_timestamp_to_vn(self, t: int) -> str:
        # timestamp UTC -> datetime UTC
        dt_utc = datetime.fromtimestamp(t, tz=timezone.utc)

        # convert -> Asia/Ho_Chi_Minh (UTC+7)
        dt_vn = dt_utc.astimezone(timezone(timedelta(hours=7)))

        # format đẹp
        return dt_vn.strftime("%d/%m/%Y %H:%M:%S")

    def build_summary(self) -> str:
        if not self.config.get("enabled", True):
            return ""

        # Dùng HTML: <b>, <i>, <code>...
        lines = ["💰 <b>Giá vàng / xăng / tỷ giá</b>"]

        # ---------------------------
        # GOLD
        # ---------------------------
        try:
            gold_list = self.fetch_pnj_gold()
        except Exception:
            gold_list = None

        if gold_list:
            lines.append("🏆 <b>Giá vàng PNJ (Giá mua → Giá bán):</b>")

            # Lấy SJC nổi bật trước
            for name, buy, sell in gold_list:
                if "SJC" in name:
                    safe_name = html_escape(name)
                    lines.append(
                        f"- {safe_name}: <code>{buy:,}</code> → <code>{sell:,}</code>"
                    )
                    break

            # Những vàng khác
            for name, buy, sell in gold_list:
                if "SJC" not in name:
                    safe_name = html_escape(name)
                    lines.append(
                        f"- {safe_name}: <code>{buy:,}</code> → <code>{sell:,}</code>"
                    )
        else:
            lines.append("- Vàng: <i>không lấy được dữ liệu</i>")

        # ---------------------------
        # GAS (PVOIL)
        # ---------------------------
        try:
            gases = self.fetch_pvoil_price_table()
        except Exception:
            gases = None

        if gases:
            lines.append("⛽ <b>Bảng giá xăng dầu PVOIL</b>")
            for r in gases:
                delta = f"{r['delta']:+d}" if r.get("delta") is not None else "0"
                safe_name = html_escape(r["name"])
                lines.append(
                    f"{r['stt']}. {safe_name}: <code>{r['price']:,} đ</code> (Δ <code>{delta}</code>)"
                )
        else:
            lines.append("⛽ Bảng giá xăng dầu: <i>không lấy được dữ liệu</i>")

        # ---------------------------
        # FX RATES
        # ---------------------------
        try:
            rates_vnd = self.fetch_vnd_rates()
        except Exception:
            rates_vnd = None

        if rates_vnd:
            # convert_timestamp_to_vn có lỗi thì vẫn hiển thị N/A
            try:
                ts_vn = self.convert_timestamp_to_vn(self.fx_timestamp)
            except Exception:
                ts_vn = "N/A"

            lines.append(f"💰 <b>Cập nhật tỷ giá VND: {ts_vn} (UTC+7)</b>")

            # Helper nhỏ để tránh KeyError từng currency
            def add_rate(key: str, label: str, extra_note: str | None = None):
                value = rates_vnd.get(key)
                if value is None:
                    return
                val = self.round_sig(value, 3)
                line = f"- 1 {html_escape(label)} = <code>{self.pretty_number(val)} VND</code>"
                if extra_note:
                    line += f"  <i>({html_escape(extra_note)})</i>"
                lines.append(line)

            # 1 USD, 1 JPY, 1 MAN, 1 KRW, 1 CNY
            add_rate("VNDUSD", "USD")

            jpy_value = rates_vnd.get("VNDJPY")
            if jpy_value is not None:
                jpy = self.round_sig(jpy_value, 3)
                add_rate("VNDJPY", "JPY", "Yên Nhật")
                man = self.round_sig(jpy * 10000, 3)
                lines.append(
                    f"- 1 MAN = <code>{self.pretty_number(man)} VND</code>  "
                    f"<i>(Man Nhật – 10,000 Yên)</i>"
                )

            krw_value = rates_vnd.get("VNDKRW")
            if krw_value is not None:
                krw = self.round_sig(krw_value, 3)
                lines.append(
                    f"- 1 KRW = <code>{self.pretty_number(krw)} VND</code>  "
                    f"<i>(Won Hàn Quốc)</i>"
                )

            cny_value = rates_vnd.get("VNDCNY")
            if cny_value is not None:
                cny = self.round_sig(cny_value, 3)
                lines.append(
                    f"- 1 CNY = <code>{self.pretty_number(cny)} VND</code>  "
                    f"<i>(Nhân dân tệ Trung Quốc)</i>"
                )
        else:
            lines.append("💰 <b>Cập nhật tỷ giá VND:</b> <i>không lấy được dữ liệu tỷ giá</i>")

        return "\n".join(lines)
