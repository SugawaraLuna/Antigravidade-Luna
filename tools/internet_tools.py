import os
import re
import requests
import webbrowser
from html import unescape

WMO_WEATHER_CODES = {
    0: "Céu limpo e ensolarado",
    1: "Principalmente limpo",
    2: "Parcialmente nublado",
    3: "Nublado",
    45: "Nevoeiro",
    48: "Nevoeiro com geada",
    51: "Garoa leve",
    53: "Garoa moderada",
    55: "Garoa densa",
    61: "Chuva fraca",
    63: "Chuva moderada",
    65: "Chuva forte",
    71: "Neve fraca",
    73: "Neve moderada",
    75: "Neve forte",
    80: "Pancadas de chuva fracas",
    81: "Pancadas de chuva moderadas",
    82: "Pancadas de chuva fortes",
    95: "Tempestade com trovoadas",
    96: "Tempestade com granizo leve",
    99: "Tempestade com granizo forte"
}

def get_live_weather(city_name: str = None) -> str:
    """
    Obtém a previsão do tempo e condições climáticas em tempo real para a localização do usuário ou cidade solicitada.
    Utiliza a API Open-Meteo com detecção automática por IP e suporte a geocodificação mundial.
    """
    lat, lon, location_name = -22.7886, -43.3175, "sua localização"
    try:
        if city_name and city_name.strip():
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={requests.utils.quote(city_name.strip())}&count=1&language=pt"
            geo = requests.get(geo_url, timeout=4).json()
            if geo.get("results"):
                r = geo["results"][0]
                lat, lon = r["latitude"], r["longitude"]
                location_name = f"{r.get('name')}, {r.get('admin1', '')}".strip(" ,")
        else:
            ip_data = requests.get("http://ip-api.com/json/?fields=city,regionName,lat,lon", timeout=3).json()
            if ip_data.get("city"):
                lat, lon = ip_data["lat"], ip_data["lon"]
                location_name = f"{ip_data['city']} ({ip_data.get('regionName', '')})"
    except Exception as e:
        print(f"[-] Aviso geocodificação clima: {e}")

    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,weather_code,wind_speed_10m&timezone=auto"
        )
        data = requests.get(url, timeout=5).json()
        curr = data.get("current", {})
        temp = curr.get("temperature_2m")
        feels = curr.get("apparent_temperature")
        hum = curr.get("relative_humidity_2m")
        wind = curr.get("wind_speed_10m")
        code = curr.get("weather_code", 0)
        cond = WMO_WEATHER_CODES.get(code, "Tempo estável")

        return f"Clima atual em {location_name}: {temp}°C (sensação térmica de {feels}°C), {cond}. Umidade relativa em {hum}% e ventos a {wind} km/h."
    except Exception as e:
        return f"Não foi possível obter os dados meteorológicos no momento: {e}"

def search_internet_info(query: str) -> str:
    """
    Pesquisa informações atualizadas em tempo real na internet (DuckDuckGo / Wikipedia).
    Retorna o resumo textual dos resultados para que a LUNA possa ler e responder diretamente sem abrir janelas.
    """
    clean_q = query.strip()
    if not clean_q:
        return "Nenhum termo de busca fornecido."

    # 1. DuckDuckGo Instant Answers
    try:
        url = "https://api.duckduckgo.com/"
        params = {"q": clean_q, "format": "json", "no_html": 1, "skip_disambig": 1}
        resp = requests.get(url, params=params, timeout=4)
        if resp.status_code == 200:
            data = resp.json()
            abstract = data.get("AbstractText", "").strip()
            if abstract:
                return f"Informação da Web sobre '{clean_q}': {abstract}"
            related = [t.get("Text", "") for t in data.get("RelatedTopics", []) if isinstance(t, dict) and "Text" in t]
            if related:
                return f"Resumo da Web sobre '{clean_q}': {' | '.join(related[:2])}"
    except Exception:
        pass

    # 2. DuckDuckGo HTML Snippets
    try:
        url = "https://html.duckduckgo.com/html/"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = requests.post(url, data={"q": clean_q}, headers=headers, timeout=5)
        if resp.status_code == 200:
            raw_html = resp.text
            snippets = re.findall(r'<a[^>]*class="result__snippet[^>]*>(.*?)</a>', raw_html, re.DOTALL)
            if snippets:
                clean_snippets = []
                for s in snippets[:3]:
                    txt = re.sub(r'<[^>]+>', '', s).strip()
                    txt = unescape(txt)
                    if txt:
                        clean_snippets.append(txt)
                if clean_snippets:
                    return f"Informações encontradas na internet sobre '{clean_q}': {' '.join(clean_snippets)[:400]}"
    except Exception:
        pass

    return f"Não foram encontrados resumos imediatos na internet para '{clean_q}'."

def open_in_browser(query_or_url: str) -> str:
    """
    Abre uma pesquisa no Google ou um endereço URL específico diretamente no navegador web padrão do usuário.
    Use quando o Gabriel pedir expressamente para 'abrir no Google' ou 'abrir a página'.
    """
    target = query_or_url.strip()
    if not target:
        target = "https://www.google.com"

    if target.startswith("http://") or target.startswith("https://"):
        webbrowser.open(target)
        return f"Abri a página {target} no seu navegador padrão."
    else:
        google_url = f"https://www.google.com/search?q={requests.utils.quote(target)}"
        webbrowser.open(google_url)
        return f"Abri a pesquisa no Google por '{target}' no seu navegador padrão."
