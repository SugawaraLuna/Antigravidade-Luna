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

def inspect_website(url: str, search_within: str = None, max_chars: int = 8000) -> str:
    """
    Navega profundamente em uma página web e inspeciona todo o seu conteúdo textual e estrutural.
    - Extrai títulos, artigos, parágrafos e tabelas.
    - Se search_within for informado, filtra e foca nos parágrafos e dados relacionados ao assunto.
    """
    target_url = url.strip()
    if not target_url.startswith("http://") and not target_url.startswith("https://"):
        target_url = "https://" + target_url

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
    }

    try:
        from bs4 import BeautifulSoup
        resp = requests.get(target_url, headers=headers, timeout=10, allow_redirects=True)
        if resp.status_code != 200:
            return f"Não foi possível acessar a página {target_url} (Código HTTP {resp.status_code})."

        soup = BeautifulSoup(resp.text, "html.parser")

        # Remover elementos inúteis
        for tag in soup(["script", "style", "nav", "footer", "aside", "header", "noscript", "svg", "form"]):
            tag.decompose()

        page_title = soup.title.string.strip() if soup.title and soup.title.string else target_url

        # Extrair texto limpo estruturado
        headings = [h.get_text(strip=True) for h in soup.find_all(["h1", "h2", "h3"]) if h.get_text(strip=True)]
        paragraphs = [p.get_text(strip=True) for p in soup.find_all("p") if len(p.get_text(strip=True)) > 25]

        # Se houver busca interna dentro da página
        if search_within and search_within.strip():
            kw = search_within.strip().lower()
            matched_paras = [p for p in paragraphs if kw in p.lower()]
            if matched_paras:
                res = f"Resultados encontrados em '{page_title}' sobre '{search_within}':\n\n"
                res += "\n\n".join(matched_paras[:6])
                return res[:max_chars]
            else:
                res = f"O termo '{search_within}' não foi encontrado diretamente nos parágrafos principais de '{page_title}'. Resumo geral do site:\n\n"
                res += "\n".join(paragraphs[:5])
                return res[:max_chars]

        # Conteúdo geral
        output = [f"Título da Página: {page_title}"]
        if headings:
            output.append("Tópicos Principais: " + " | ".join(headings[:8]))
        if paragraphs:
            output.append("\nConteúdo Principal:\n" + "\n\n".join(paragraphs[:10]))
        else:
            body_text = soup.get_text(separator="\n", strip=True)
            output.append(body_text[:max_chars])

        return "\n".join(output)[:max_chars]
    except Exception as e:
        return f"Erro ao inspecionar o site {target_url}: {e}"

def deep_web_research(query: str, max_sources: int = 3) -> str:
    """
    Realiza uma pesquisa aprofundada na web:
    Localiza os links mais relevantes, visita e extrai os textos dessas páginas para formular uma resposta rica.
    """
    clean_q = query.strip()
    if not clean_q:
        return "Nenhum termo de pesquisa profunda fornecido."

    try:
        from bs4 import BeautifulSoup
        search_url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(clean_q)}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = requests.post("https://html.duckduckgo.com/html/", data={"q": clean_q}, headers=headers, timeout=6)
        if resp.status_code != 200:
            return search_internet_info(clean_q)

        soup = BeautifulSoup(resp.text, "html.parser")
        results = soup.find_all("a", class_="result__url")
        urls = []
        for r in results:
            href = r.get("href", "")
            if href.startswith("//"):
                href = "https:" + href
            if href.startswith("http"):
                urls.append(href)
            if len(urls) >= max_sources:
                break

        if not urls:
            return search_internet_info(clean_q)

        compiled_info = [f"Pesquisa aprofundada sobre '{clean_q}':"]
        for u in urls[:max_sources]:
            summary = inspect_website(u, search_within=clean_q, max_chars=1200)
            compiled_info.append(f"\n--- Fonte: {u} ---\n{summary}")

        return "\n".join(compiled_info)[:5000]
    except Exception as e:
        return search_internet_info(clean_q)

