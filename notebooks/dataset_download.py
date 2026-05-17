"""
download_dataset.py — Descarga automática de los 200 pacientes (zoom 248x248)
==============================================================================
Descarga todos los slides con zoom 248x248 um2 de la colección HunCRC
y los extrae en data/raw/zoom_2_XXX/ con la estructura esperada.
"""
 
import io
import re
import time
import zipfile
from pathlib import Path
 
import requests
from tqdm import tqdm
 
# ── Configuración ──────────────────────────────────────────────────────────────
COLLECTION_ID = 5927795
OUTPUT_DIR    = Path("data/raw")
ZOOM_FILTER   = "248x248"
API_BASE      = "https://api.figshare.com/v2"
PAGE_SIZE     = 100            # figshare acepta máximo 100 con offset
 
 
def fetch_collection_articles() -> list[dict]:
    """Obtiene todos los artículos de la colección paginando con offset."""
    articles = []
    offset   = 0
    while True:
        url  = f"{API_BASE}/collections/{COLLECTION_ID}/articles"
        resp = requests.get(url, params={"limit": PAGE_SIZE, "offset": offset}, timeout=30)
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        articles.extend(batch)
        print(f"  Obtenidos {len(articles)} articulos...")
        if len(batch) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
        time.sleep(0.3)
    return articles
 
 
def get_download_url(article_id: int) -> str | None:
    """Obtiene la URL de descarga del archivo zip de un articulo."""
    url  = f"{API_BASE}/articles/{article_id}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    files = resp.json().get("files", [])
    return files[0]["download_url"] if files else None
 
 
def extract_slide_id(title: str) -> str | None:
    """
    Extrae el numero de slide del titulo.
    Ej: "patches and local annotations, slide 162, zoom 248x248 um2" -> "162"
    """
    match = re.search(r"slide\s+(\d+)", title, re.IGNORECASE)
    return match.group(1).zfill(3) if match else None
 
 
def download_and_extract(download_url: str, slide_id: str) -> bool:
    """Descarga el zip y lo extrae en data/raw/zoom_2_XXX/."""
    out_dir = OUTPUT_DIR / f"zoom_2_{slide_id}"
 
    if out_dir.exists() and any(out_dir.iterdir()):
        print(f"  [SKIP] {out_dir.name} ya existe.")
        return True
 
    out_dir.mkdir(parents=True, exist_ok=True)
 
    try:
        resp  = requests.get(download_url, timeout=180, stream=True)
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        buf   = io.BytesIO()
 
        with tqdm(total=total, unit="B", unit_scale=True,
                  desc=f"  slide {slide_id}", leave=False) as pbar:
            for chunk in resp.iter_content(chunk_size=256 * 1024):
                buf.write(chunk)
                pbar.update(len(chunk))
 
        buf.seek(0)
        with zipfile.ZipFile(buf) as zf:
            zf.extractall(out_dir)
        return True
 
    except Exception as e:
        print(f"  [ERROR] slide {slide_id}: {e}")
        try:
            out_dir.rmdir()
        except Exception:
            pass
        return False
 
 
def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
 
    print("Obteniendo lista de articulos de la coleccion...")
    all_articles = fetch_collection_articles()
    print(f"  Total articulos en la coleccion: {len(all_articles)}")
 
    zoom2_articles = [a for a in all_articles if ZOOM_FILTER in a.get("title", "")]
    print(f"  Articulos con zoom 248x248: {len(zoom2_articles)}")
 
    if not zoom2_articles:
        print("ERROR: No se encontraron articulos con '248x248'. Revisa el filtro.")
        return
 
    zoom2_articles.sort(key=lambda a: a["title"])
 
    ok, fail = 0, 0
    for i, article in enumerate(zoom2_articles, 1):
        title    = article["title"]
        slide_id = extract_slide_id(title)
 
        if not slide_id:
            print(f"  [WARN] No se extrajo slide ID de: {title}")
            continue
 
        print(f"[{i:3d}/{len(zoom2_articles)}] slide {slide_id}")
 
        try:
            dl_url = get_download_url(article["id"])
        except Exception as e:
            print(f"  [ERROR] URL no obtenida: {e}")
            fail += 1
            continue
 
        if not dl_url:
            print(f"  [WARN] Sin archivo descargable")
            continue
 
        if download_and_extract(dl_url, slide_id):
            ok += 1
        else:
            fail += 1
 
        time.sleep(0.5)
 
    print(f"\n{'='*50}")
    print(f"Completado: {ok} OK / {fail} errores")
    print(f"Datos en: {OUTPUT_DIR.resolve()}")
 
 
if __name__ == "__main__":
    main()