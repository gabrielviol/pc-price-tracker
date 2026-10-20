"""
Monitor de precos (Hardware Barato -> Discord)

Le as ofertas de cada produto em products.json, guarda o historico em
prices.csv e posta um resumo no Discord via webhook.

Uso:
  python scraper.py            # busca precos, salva historico e envia ao Discord
  python scraper.py --dry-run  # so mostra no terminal, nao envia nem salva
"""

import csv
import html
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = Path(__file__).parent
PRODUCTS_FILE = BASE_DIR / "products.json"
HISTORY_FILE = BASE_DIR / "prices.csv"
BRT = timezone(timedelta(hours=-3))

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)

# Cada oferta no Hardware Barato tem um link com title assim:
#   "Ir para oferta na Kabum por R$ 2.399,99"
#   "Ver cupom e oferta na Shopee por R$ 4.415,08"
OFFER_RE = re.compile(
    r"(?:Ir para oferta|Ver cupom e oferta) na\s+(?P<store>.+?)\s+por\s+R\$\s*(?P<price>[\d.]+,\d{2})",
    re.IGNORECASE,
)


def parse_brl(value: str) -> float:
    """'2.399,99' -> 2399.99"""
    return float(value.replace(".", "").replace(",", "."))


def fmt_brl(value: float) -> str:
    """2399.99 -> 'R$ 2.399,99'"""
    s = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "pt-BR"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def get_offers(url: str) -> list[dict]:
    """Retorna as ofertas da pagina, ordenadas do menor preco para o maior."""
    page = html.unescape(fetch(url))
    offers, seen = [], set()
    for m in OFFER_RE.finditer(page):
        store = m.group("store").strip()
        price = parse_brl(m.group("price"))
        key = (store.lower(), price)
        if key not in seen:
            seen.add(key)
            offers.append({"store": store, "price": price})
    return sorted(offers, key=lambda o: o["price"])


def load_history() -> dict[str, list[dict]]:
    history: dict[str, list[dict]] = {}
    if HISTORY_FILE.exists():
        with HISTORY_FILE.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                history.setdefault(row["product"], []).append(
                    {"date": row["date"], "store": row["store"], "price": float(row["price"])}
                )
    return history


def append_history(rows: list[dict]) -> None:
    new_file = not HISTORY_FILE.exists()
    with HISTORY_FILE.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "product", "store", "price"])
        if new_file:
            writer.writeheader()
        writer.writerows(rows)


def build_line(product: dict, best: dict | None, past: list[dict]) -> tuple[str, bool]:
    """Monta a linha do Discord. Retorna (texto, bateu_meta)."""
    name, url, target = product["name"], product["url"], product.get("target")
    if best is None:
        return f"**{name}**: nao consegui ler o preco hoje ([ver pagina]({url}))", False

    line = f"**{name}**: {fmt_brl(best['price'])} na {best['store']}"

    if past:
        last = past[-1]["price"]
        diff = best["price"] - last
        if abs(diff) >= 0.01:
            arrow = "🔻" if diff < 0 else "🔺"
            line += f"  {arrow} {fmt_brl(abs(diff))} desde a ultima leitura"
        lowest = min(p["price"] for p in past)
        if best["price"] < lowest:
            line += "  🏆 menor preco ja registrado"
        else:
            line += f"  (menor registrado: {fmt_brl(lowest)})"

    hit = target is not None and best["price"] <= target
    if hit:
        line += f"\n🎯 **Abaixo da meta de {fmt_brl(target)}!**"
    line += f"\n<{url}>"
    return line, hit


def send_discord(webhook: str, lines: list[str], any_hit: bool) -> None:
    today = datetime.now(BRT).strftime("%d/%m/%Y")
    title = f"💰 Precos de hoje ({today})"
    embed = {
        "title": title,
        "description": "\n\n".join(lines)[:4000],
        "color": 0x2ECC71 if any_hit else 0x5865F2,
        "footer": {"text": "Fonte: Hardware Barato"},
    }
    payload = {"embeds": [embed]}
    if any_hit:
        payload["content"] = "@here um produto bateu a meta de preco!"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        webhook, data=data, headers={"Content-Type": "application/json", "User-Agent": USER_AGENT}
    )
    urllib.request.urlopen(req, timeout=30).read()


def main() -> int:
    # Garante UTF-8 na saida (o console/log do Windows usa cp1252 e quebra com emoji)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    dry_run = "--dry-run" in sys.argv
    products = json.loads(PRODUCTS_FILE.read_text(encoding="utf-8"))
    history = load_history()
    today = datetime.now(BRT).strftime("%Y-%m-%d")

    lines, rows, any_hit, failures = [], [], False, 0
    for i, product in enumerate(products):
        if i:
            time.sleep(3)  # educado com o site
        try:
            offers = get_offers(product["url"])
        except Exception as e:  # noqa: BLE001
            print(f"[erro] {product['name']}: {e}", file=sys.stderr)
            offers = []
        best = offers[0] if offers else None
        if best is None:
            failures += 1
        else:
            rows.append({"date": today, "product": product["name"], **best})

        line, hit = build_line(product, best, history.get(product["name"], []))
        any_hit = any_hit or hit
        lines.append(line)
        print(line.replace("\n", " | "))
        if offers:
            print("   ofertas:", ", ".join(f"{o['store']} {fmt_brl(o['price'])}" for o in offers[:5]))

    if dry_run:
        print("\n[dry-run] nada foi salvo nem enviado.")
        return 0

    if rows:
        append_history(rows)

    webhook = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook:
        print("DISCORD_WEBHOOK_URL nao definido; pulando envio.", file=sys.stderr)
        return 1
    send_discord(webhook, lines, any_hit)
    print("Enviado para o Discord.")
    return 1 if failures == len(products) else 0


if __name__ == "__main__":
    sys.exit(main())
