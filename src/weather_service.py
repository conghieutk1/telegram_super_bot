import logging
from typing import Any, Dict, Optional, Tuple

from util import http_get_json
from html import escape as html_escape  # HTML escape cho text động


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
            # OpenWeather format: "rain": {"3h": mm}
            mm = rain.get("3h", 0.0)
            try:
                max_rain = max(max_rain, float(mm))
            except (TypeError, ValueError):
                continue

        alert = max_rain >= self.rain_alert_mm
        return alert, max_rain

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

        location_html = html_escape(self.location_name)
        desc_html = html_escape(desc)

        lines = [f"☁️ <b>Thời tiết - {location_html}</b>"]

        if temp is not None and feels is not None:
            lines.append(
                f"- Nhiệt độ: <code>{round(temp)}°C</code> "
                f"(cảm giác: <code>{round(feels)}°C</code>)"
            )
        elif temp is not None:
            lines.append(f"- Nhiệt độ: <code>{round(temp)}°C</code>")

        lines.append(f"- Trạng thái: <code>{desc_html}</code>")

        if humidity is not None:
            lines.append(f"- Độ ẩm: <code>{humidity}%</code>")
        if wind is not None:
            lines.append(f"- Gió: <code>{wind} m/s</code>")

        forecast = self.fetch_forecast()
        alert, max_rain = self._extract_rain_alert(forecast)

        if alert:
            lines.append(
                "⚠️ <b>Cảnh báo mưa</b>: dự kiến có mưa tới "
                f"<code>{max_rain:.1f} mm</code> trong ~12 giờ tới."
            )
        else:
            lines.append("✅ Không có cảnh báo mưa lớn trong ~12 giờ tới.")

        return "\n".join(lines)
