import logging
from typing import Any, Dict, Optional, Tuple, List
from html import escape as html_escape
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from util import http_get_json


class WeatherService:
    """
    Lấy thời tiết hiện tại + forecast từ OpenWeatherMap
    và cảnh báo mưa nếu lượng mưa trong vài giờ tới >= rain_alert_mm.
    """

    def __init__(self, config: Dict[str, Any], secrets: Dict[str, Any]) -> None:
        self.config = config
        self.api_key = secrets.get("openweather_api_key")
        self.logger = logging.getLogger(self.__class__.__name__)

        self.enabled = config.get("enabled", True)
        self.location_name = config.get("location_name", "Vị trí")
        self.lat = config.get("lat")
        self.lon = config.get("lon")
        self.api_base = config.get("api_base", "https://api.openweathermap.org/data/2.5")
        self.units = config.get("units", "metric")
        self.lang = config.get("lang", "vi")
        self.rain_alert_mm = float(config.get("rain_alert_mm", 5.0))

        # Số ngày muốn hiển thị forecast (3 hoặc 5)
        self.forecast_days = int(config.get("forecast_days", 3))

    def is_configured(self) -> bool:
        return (
            self.enabled
            and self.api_key is not None
            and self.lat is not None
            and self.lon is not None
        )

    def _common_params(self) -> Dict[str, Any]:
        return {
            "lat": self.lat,
            "lon": self.lon,
            "units": self.units,
            "lang": self.lang,
            "appid": self.api_key,
        }

    def fetch_current(self) -> Optional[Dict[str, Any]]:
        url = f"{self.api_base}/weather"
        return http_get_json(url, params=self._common_params())

    def fetch_forecast(self) -> Optional[Dict[str, Any]]:
        url = f"{self.api_base}/forecast"
        return http_get_json(url, params=self._common_params())

    def _extract_rain_alert(
        self, forecast: Dict[str, Any], hours_ahead: int = 12
    ) -> Tuple[bool, float]:
        """
        Tìm lượng mưa lớn nhất trong n giờ tới (3h/slot).
        """
        if not forecast:
            return False, 0.0

        slots = forecast.get("list", [])
        max_rain = 0.0
        # Mỗi slot là 3h, lấy số slot tương ứng với hours_ahead
        max_slots = max(1, hours_ahead // 3)
        for item in slots[:max_slots]:
            rain = item.get("rain") or {}
            mm = rain.get("3h", 0.0)
            try:
                max_rain = max(max_rain, float(mm))
            except (TypeError, ValueError):
                continue

        alert = max_rain >= self.rain_alert_mm
        return alert, max_rain
    
    def _to_local_datetime(self, ts: int, tz_offset_sec: int) -> datetime:
        """
        OpenWeather trả về:
        - dt, sunrise, sunset: timestamp UTC (giây)
        - timezone: offset so với UTC (giây, VD: +25200 cho UTC+7)
        Hàm này convert về datetime local.
        """
        # ts là UTC timestamp -> cộng offset giây -> datetime local (naive)
        return datetime.fromtimestamp(ts, tz=timezone.utc) + timedelta(seconds=tz_offset_sec)

    def _format_hhmm(self, ts: int, tz_offset_sec: int) -> str:
        try:
            dt_local = self._to_local_datetime(ts, tz_offset_sec)
            return dt_local.strftime("%H:%M")  # 24h format
        except Exception:
            return str(ts)

    def _local_date_strings(self, ts: int, tz_offset_sec: int) -> Tuple[str, str]:
        """
        Trả về:
        - iso_str: 'YYYY-MM-DD' (dùng để so sánh)
        - display_str: 'dd/mm/YYYY' (dùng để hiển thị)
        """
        dt_local = self._to_local_datetime(ts, tz_offset_sec)
        iso_str = dt_local.strftime("%Y-%m-%d")
        display_str = dt_local.strftime("%d/%m/%Y")
        return iso_str, display_str

    # -----------------------------
    #   NEW: gom forecast theo ngày
    # -----------------------------
    def _build_daily_forecast(
        self,
        forecast: Dict[str, Any],
        today_date_str: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Từ dữ liệu /forecast (3h/slot), gom lại thành từng ngày:
        - date: "YYYY-MM-DD"
        - min_temp, max_temp
        - desc: mô tả chính trong ngày (ưu tiên khung giờ 12:00)
        - rain_mm: tổng lượng mưa trong ngày

        today_date_str: nếu truyền vào (VD: '2025-11-16') thì sẽ BỎ ngày này khỏi danh sách.
        """
        result: List[Dict[str, Any]] = []
        if not forecast:
            return result

        slots = forecast.get("list", [])
        by_date: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "temps": [],
            "rains": [],
            "descs": [],
            "noon_desc": None,
        })

        for item in slots:
            dt_txt = item.get("dt_txt")  # "2025-11-16 12:00:00"
            if not dt_txt:
                continue

            date_str, time_str = dt_txt.split(" ")
            bucket = by_date[date_str]

            main = item.get("main", {})
            temp = main.get("temp")
            if temp is not None:
                bucket["temps"].append(float(temp))

            weather_arr = item.get("weather") or []
            desc = weather_arr[0].get("description") if weather_arr else None
            if desc:
                bucket["descs"].append(desc)
                if time_str.startswith("12:00"):
                    bucket["noon_desc"] = desc

            rain = item.get("rain") or {}
            mm = rain.get("3h", 0.0)
            try:
                bucket["rains"].append(float(mm))
            except (TypeError, ValueError):
                pass

        all_dates = sorted(by_date.keys())
        for date_str in all_dates:
            # BỎ ngày hôm nay khỏi forecast
            if today_date_str and date_str == today_date_str:
                continue

            b = by_date[date_str]
            if not b["temps"]:
                continue

            min_temp = min(b["temps"])
            max_temp = max(b["temps"])
            total_rain = sum(b["rains"]) if b["rains"] else 0.0
            desc = b["noon_desc"] or (b["descs"][0] if b["descs"] else "không rõ")

            result.append(
                {
                    "date": date_str,
                    "min_temp": round(min_temp),
                    "max_temp": round(max_temp),
                    "desc": desc,
                    "rain_mm": total_rain,
                }
            )

            # Dừng lại khi đủ số ngày cần
            if len(result) >= self.forecast_days:
                break

        return result

    def _extract_today_temp_range(
        self, forecast: Dict[str, Any], today_date_str: str
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Trích xuất min/max nhiệt độ của ngày hôm nay từ dữ liệu /forecast.
        today_date_str: "YYYY-MM-DD"
        """
        if not forecast or not today_date_str:
            return None, None

        slots = forecast.get("list", [])
        temps: List[float] = []

        for item in slots:
            dt_txt = item.get("dt_txt")  # "2025-11-16 09:00:00"
            if not dt_txt:
                continue

            date_str, _ = dt_txt.split(" ")
            if date_str != today_date_str:
                continue

            main = item.get("main", {})
            t = main.get("temp")
            if t is not None:
                temps.append(float(t))

        if not temps:
            return None, None

        return min(temps), max(temps)
    def build_summary(self) -> str:
        if not self.is_configured():
            self.logger.warning("WeatherService is not properly configured.")
            return ""

        current = self.fetch_current()
        if not current:
            return "☁️ <b>Thời tiết</b>: không lấy được dữ liệu."

        main = current.get("main", {})
        weather_arr = current.get("weather", [])
        desc = weather_arr[0]["description"] if weather_arr else "Không rõ"
        temp = main.get("temp")
        feels = main.get("feels_like")
        humidity = main.get("humidity")
        wind = current.get("wind", {}).get("speed")
        clouds = current.get("clouds", {}).get("all")
        visibility = current.get("visibility")
        pressure = main.get("pressure")

        sys_info = current.get("sys", {})
        sunrise = sys_info.get("sunrise")
        sunset = sys_info.get("sunset")

        # OpenWeather có field timezone (giây offset so với UTC)
        tz_offset_sec = current.get("timezone", 0)
        current_dt_ts = current.get("dt")

        location_html = html_escape(self.location_name)
        desc_html = html_escape(desc)

        lines = [f"🌦️ <b>Thời tiết - {location_html}</b>"]

        # Hôm nay là ngày bao nhiêu (local)
        today_iso = None
        if current_dt_ts is not None:
            today_iso, today_display = self._local_date_strings(
                int(current_dt_ts), tz_offset_sec
            )
            lines.append(f"- Hôm nay: <code>{today_display}</code>")

        forecast = self.fetch_forecast()

        today_min = today_max = None
        if forecast and today_iso:
            today_min, today_max = self._extract_today_temp_range(forecast, today_iso)

        if temp is not None and feels is not None:
            range_text = ""
            if today_min is not None and today_max is not None:
                range_text = (
                    f", hôm nay: <code>{round(today_min)}–{round(today_max)}°C</code>"
                )

            lines.append(
                f"- Nhiệt độ: <code>{round(temp)}°C</code> "
                f"(cảm giác: <code>{round(feels)}°C</code>{range_text})"
            )
        elif temp is not None:
            lines.append(f"- Nhiệt độ: <code>{round(temp)}°C</code>")

        lines.append(f"- Trạng thái: <code>{desc_html}</code>")

        if humidity is not None:
            lines.append(f"- Độ ẩm: <code>{humidity}%</code>")
        if wind is not None:
            lines.append(f"- Gió: <code>{wind} m/s</code>")
        if clouds is not None:
            lines.append(f"- Mây: <code>{clouds}%</code>")
        if visibility is not None:
            km = visibility / 1000.0
            lines.append(f"- Tầm nhìn: <code>{km:.1f} km</code>")
        if pressure is not None:
            lines.append(f"- Áp suất: <code>{pressure} hPa</code>")

        # Mặt trời: đổi timestamp -> giờ 24h local
        if sunrise and sunset:
            sunrise_str = self._format_hhmm(int(sunrise), tz_offset_sec)
            sunset_str = self._format_hhmm(int(sunset), tz_offset_sec)
            lines.append(
                f"- Mặt trời: sunrise <code>{sunrise_str}</code>, "
                f"sunset <code>{sunset_str}</code>"
            )

        # forecast = self.fetch_forecast()
        alert, max_rain = self._extract_rain_alert(forecast) if forecast else (False, 0.0)

        if alert:
            lines.append(
                "⚠️ <b>Cảnh báo mưa</b>: dự kiến có mưa tới "
                f"<code>{max_rain:.1f} mm</code> trong ~12 giờ tới."
            )
        else:
            lines.append("✅ Không có cảnh báo mưa lớn trong ~12 giờ tới.")

        # Dự báo 3–5 ngày tới, BỎ ngày hôm nay
        daily = self._build_daily_forecast(forecast, today_date_str=today_iso)
        if daily:
            lines.append("")
            lines.append(f"📅 <b>Dự báo {len(daily)} ngày tới</b>:")

            for d in daily:
                date_str = d["date"]      # "2025-11-17"
                y, m, day = date_str.split("-")
                ddmm = f"{day}/{m}"

                desc_html = html_escape(d["desc"])
                rain_text = ""
                if d["rain_mm"] >= 0.1:
                    rain_text = f", mưa ~<code>{d['rain_mm']:.1f} mm</code>"

                lines.append(
                    f"• <b>{ddmm}</b>: "
                    f"<code>{d['min_temp']}–{d['max_temp']}°C</code>, "
                    f"{desc_html}{rain_text}"
                )

        return "\n".join(lines)

