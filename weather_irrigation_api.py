import os
import sys
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv("config.env")

API_KEY = os.getenv("OPENWEATHER_API_KEY")
CIDADE  = os.getenv("CIDADE", "Recife")
PAIS    = os.getenv("PAIS", "BR")

if not API_KEY:
    print("[ERRO] OPENWEATHER_API_KEY não definida. Configure o arquivo config.env.")
    sys.exit(1)

BASE_URL = "https://api.openweathermap.org/data/2.5/forecast"

LIMIAR_CHUVA_MM = 10.0

def buscar_previsao(cidade: str, pais: str, api_key: str) -> dict:

    params = {
        "q":     f"{cidade},{pais}",
        "appid": api_key,
        "units": "metric",
        "lang":  "pt_br",
        "cnt":   8,
    }

    try:
        resposta = requests.get(BASE_URL, params=params, timeout=10)
        resposta.raise_for_status()
        return resposta.json()

    except requests.exceptions.ConnectionError:
        print("[ERRO] Sem conexão com a internet. Verifique sua rede.")
        sys.exit(1)

    except requests.exceptions.Timeout:
        print("[ERRO] A requisição excedeu o tempo limite (10s).")
        sys.exit(1)

    except requests.exceptions.HTTPError as e:
        codigo = resposta.status_code
        if codigo == 401:
            print("[ERRO] Chave de API inválida ou não autorizada.")
        elif codigo == 404:
            print(f"[ERRO] Cidade '{cidade},{pais}' não encontrada.")
        else:
            print(f"[ERRO] Falha na API: {e}")
        sys.exit(1)


def extrair_dados_chuva(dados_api: dict) -> list[dict]:
    intervalos = []

    for item in dados_api.get("list", []):

        chuva = item.get("rain", {}).get("3h", 0.0)

        intervalo = {
            "horario":      datetime.fromtimestamp(item["dt"]),
            "descricao":    item["weather"][0]["description"],
            "chuva_3h_mm":  chuva,
            "humidade_pct": item["main"]["humidity"],
            "temp_c":       item["main"]["temp"],
        }
        intervalos.append(intervalo)

    return intervalos


def calcular_chuva_acumulada(intervalos: list[dict]) -> float:
    return sum(i["chuva_3h_mm"] for i in intervalos)


def decidir_irrigacao(chuva_acumulada_mm: float) -> dict:
    if chuva_acumulada_mm >= LIMIAR_CHUVA_MM:
        return {
            "irrigar": False,
            "motivo":  (f"Chuva prevista de {chuva_acumulada_mm:.1f} mm supera o limiar "
                        f"de {LIMIAR_CHUVA_MM} mm. Solo permanecerá úmido sem irrigação."),
            "economia": chuva_acumulada_mm * 1.0,  # 1 mm ≈ 1 L/m²
        }
    else:
        return {
            "irrigar": True,
            "motivo":  (f"Chuva prevista de {chuva_acumulada_mm:.1f} mm está abaixo do "
                        f"limiar de {LIMIAR_CHUVA_MM} mm. Irrigação necessária."),
            "economia": 0.0,
        }


def exibir_relatorio(cidade: str, intervalos: list[dict], decisao: dict) -> None:

    print("\n" + "=" * 55)
    print(f"  PREVISÃO DE IRRIGAÇÃO — {cidade.upper()}")
    print(f"  Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 55)

    print("\n📅 PREVISÃO DAS PRÓXIMAS 24 HORAS:\n")
    print(f"  {'Horário':<18} {'Clima':<22} {'Chuva':>7} {'Umid.':>6}")
    print("  " + "-" * 57)

    for i in intervalos:
        hora = i["horario"].strftime("%d/%m %H:%M")
        print(
            f"  {hora:<18} {i['descricao']:<22} "
            f"{i['chuva_3h_mm']:>5.1f}mm {i['humidade_pct']:>5}%"
        )

    total = sum(i["chuva_3h_mm"] for i in intervalos)
    print(f"\n  ⛆  Total acumulado previsto: {total:.1f} mm")

    print("\n" + "-" * 55)
    status = "CANCELADA" if not decisao["irrigar"] else "RECOMENDADA"
    print(f"  DECISÃO DE IRRIGAÇÃO: {status}")
    print(f"  Motivo: {decisao['motivo']}")
    if decisao["economia"] > 0:
        print(f"  💧 Economia estimada: {decisao['economia']:.1f} L/m²")
    print("=" * 55 + "\n")


# ──────────────────────────────────────────────
# Ponto de entrada
# ──────────────────────────────────────────────

def main():
    print(f"[INFO] Consultando previsão para {CIDADE}, {PAIS}...")

    # 1. Busca dados na API
    dados_brutos = buscar_previsao(CIDADE, PAIS, API_KEY)

    # 2. Extrai apenas os campos de chuva relevantes
    intervalos = extrair_dados_chuva(dados_brutos)

    # 3. Calcula o total de chuva acumulada nas próximas 24h
    chuva_total = calcular_chuva_acumulada(intervalos)

    # 4. Aplica a lógica de decisão de irrigação
    decisao = decidir_irrigacao(chuva_total)

    # 5. Exibe o relatório no terminal
    exibir_relatorio(CIDADE, intervalos, decisao)

    # Retorna código de saída para integração com sistemas externos:
    # 0 = irrigar, 1 = não irrigar
    sys.exit(0 if decisao["irrigar"] else 1)


if __name__ == "__main__":
    main()