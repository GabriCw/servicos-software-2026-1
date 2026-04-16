import statistics
import httpx
from datetime import date, timedelta

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
HISTORICAL_URL = "https://archive-api.open-meteo.com/v1/archive"

DAILY_VARS = "temperature_2m_max,temperature_2m_min,precipitation_sum,windspeed_10m_max"
DEFAULT_HISTORICAL_YEARS = 5


def geocode(city: str) -> dict:
    candidates = [city]
    ascii_name = city.encode("ascii", errors="ignore").decode()
    if ascii_name and ascii_name != city:
        candidates.append(ascii_name)

    for name in candidates:
        resp = httpx.get(GEOCODING_URL, params={"name": name, "count": 1, "language": "pt"})
        resp.raise_for_status()
        data = resp.json()
        if data.get("results"):
            r = data["results"][0]
            return {"lat": r["latitude"], "lng": r["longitude"], "name": r["name"], "country": r.get("country", "")}

    raise ValueError(f"Cidade '{city}' não encontrada.")


def _fetch_historical_year(lat: float, lng: float, start: date, end: date, client: httpx.Client) -> list[dict]:
    resp = client.get(HISTORICAL_URL, params={
        "latitude": lat,
        "longitude": lng,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "daily": DAILY_VARS,
        "timezone": "auto",
    }, timeout=15)
    resp.raise_for_status()
    daily = resp.json()["daily"]
    return [
        {
            "temp_max": daily["temperature_2m_max"][i],
            "temp_min": daily["temperature_2m_min"][i],
            "precipitation": daily["precipitation_sum"][i],
            "wind_max": daily["windspeed_10m_max"][i],
        }
        for i in range(len(daily["time"]))
    ]


def _confidence(avg_std_dev: float) -> tuple[float, str]:
    index = round(max(0.0, min(1.0, 1.0 - (avg_std_dev / 6.0))), 2)
    level = "alta" if index >= 0.75 else ("média" if index >= 0.5 else "baixa")
    return index, level


def _safe_mean(values: list) -> float | None:
    clean = [v for v in values if v is not None]
    return round(statistics.mean(clean), 1) if clean else None


def _safe_stdev(values: list) -> float:
    clean = [v for v in values if v is not None]
    return round(statistics.stdev(clean), 2) if len(clean) > 1 else 0.0


def _sample_days(days: list[dict], max_days: int) -> list[dict]:
    if len(days) <= max_days:
        return days
    step = len(days) / max_days
    return [days[round(i * step)] for i in range(max_days)]


def get_weather(lat: float, lng: float, start_date: str, end_date: str,
                historical_years: int = DEFAULT_HISTORICAL_YEARS,
                max_days: int | None = None) -> dict:
    today = date.today()
    max_forecast = today + timedelta(days=15)
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    trip_days = (end - start).days + 1

    # --- Previsão normal ---
    if end <= max_forecast:
        resp = httpx.get(FORECAST_URL, params={
            "latitude": lat,
            "longitude": lng,
            "start_date": start_date,
            "end_date": end_date,
            "daily": DAILY_VARS,
            "timezone": "auto",
        }, timeout=15)
        resp.raise_for_status()
        daily = resp.json()["daily"]
        days = [
            {
                "date": daily["time"][i],
                "temp_max_avg": daily["temperature_2m_max"][i],
                "temp_min_avg": daily["temperature_2m_min"][i],
                "temp_max_std": 0.0,
                "temp_min_std": 0.0,
                "precipitation_avg": daily["precipitation_sum"][i],
                "wind_max_avg": daily["windspeed_10m_max"][i],
            }
            for i in range(len(daily["time"]))
        ]
        return {
            "days": _sample_days(days, max_days) if max_days else days,
            "used_historical": False,
        }

    # --- Dados históricos ---
    current_year = today.year
    yearly_data: list[list[dict]] = []

    with httpx.Client() as client:
        for offset in range(1, historical_years + 1):
            year = current_year - offset
            try:
                hist_start = start.replace(year=year)
                hist_end = end.replace(year=year)
                data = _fetch_historical_year(lat, lng, hist_start, hist_end, client)
                if len(data) == trip_days:
                    yearly_data.append(data)
            except Exception:
                pass

    if not yearly_data:
        raise ValueError("Não foi possível obter dados históricos para o período solicitado.")

    years_count = len(yearly_data)
    requested_dates = [start + timedelta(days=i) for i in range(trip_days)]
    all_stds: list[float] = []
    days = []

    for day_idx in range(trip_days):
        temps_max = [yearly_data[y][day_idx]["temp_max"] for y in range(years_count)]
        temps_min = [yearly_data[y][day_idx]["temp_min"] for y in range(years_count)]
        precips   = [yearly_data[y][day_idx]["precipitation"] for y in range(years_count)]
        winds     = [yearly_data[y][day_idx]["wind_max"] for y in range(years_count)]

        std_max = _safe_stdev(temps_max)
        std_min = _safe_stdev(temps_min)
        all_stds.append((std_max + std_min) / 2)

        days.append({
            "date": requested_dates[day_idx].isoformat(),
            "temp_max_avg": _safe_mean(temps_max),
            "temp_min_avg": _safe_mean(temps_min),
            "temp_max_std": std_max,
            "temp_min_std": std_min,
            "precipitation_avg": _safe_mean(precips),
            "wind_max_avg": _safe_mean(winds),
        })

    avg_std = round(statistics.mean(all_stds), 2)
    confidence_index, confidence_level = _confidence(avg_std)

    return {
        "days": _sample_days(days, max_days) if max_days else days,
        "used_historical": True,
        "years_analyzed": years_count,
        "confidence_index": confidence_index,
        "confidence_level": confidence_level,
        "avg_temp_std_dev": avg_std,
    }
