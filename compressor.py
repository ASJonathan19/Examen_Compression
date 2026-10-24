#!/usr/bin/env python3
"""
compressor.py - Mini-clone de bzip2, lzma et 7-zip (projet "Codage et Traitement du Signal", L2).

Utilise les modules standards bz2 et lzma. Pour 7-zip, le vrai format .7z est produit si le
paquet optionnel `py7zr` est installé (pip install py7zr). Sinon, on se rabat sur LZMA2 (le
même algorithme que 7-zip utilise par défaut) dans un conteneur .xz.

Exemples :
    python compressor.py compress  bzip2 document.txt
    python compressor.py compress  lzma  image.png
    python compressor.py compress  7z    video.mp4
    python compressor.py decompress bzip2 document.txt.bz2
    python compressor.py bench document.txt musique.mp3 image.png video.mp4 --csv resultats.csv
"""
import argparse
import bz2
import csv
import hashlib
import lzma
import os
import sys
import tempfile
import time

try:
    import py7zr  # optionnel : vrai format .7z
    HAS_PY7ZR = True
except ImportError:
    HAS_PY7ZR = False

CHUNK = 1024 * 1024  # on lit par blocs de 1 Mo (fichiers vidéo volumineux)
EXT = {"bzip2": ".bz2", "lzma": ".lzma", "7z": ".7z" if HAS_PY7ZR else ".xz"}


# ---------------------------------------------------------------- compression
def _stream(compressor, src, dst):
    """Lit src par blocs, passe dans l'objet compresseur/décompresseur, écrit dans dst."""
    with open(src, "rb") as fin, open(dst, "wb") as fout:
        while True:
            block = fin.read(CHUNK)
            if not block:
                break
            fout.write(compressor.compress(block) if hasattr(compressor, "compress")
                       else compressor.decompress(block))
        if hasattr(compressor, "flush"):
            fout.write(compressor.flush())


def compress(algo, src, dst=None):
    dst = dst or src + EXT[algo]
    if algo == "bzip2":
        # BWT + MTF + Huffman, taille de bloc maximale (niveau 9 = 900 Ko)
        _stream(bz2.BZ2Compressor(9), src, dst)
    elif algo == "lzma":
        # LZMA1 : format historique ".lzma" (dictionnaire + codage par intervalles)
        _stream(lzma.LZMACompressor(format=lzma.FORMAT_ALONE, preset=9), src, dst)
    elif algo == "7z":
        if HAS_PY7ZR:
            with py7zr.SevenZipFile(dst, "w") as z:   # LZMA2 par défaut
                z.write(src, arcname=os.path.basename(src))
        else:
            _stream(lzma.LZMACompressor(format=lzma.FORMAT_XZ, preset=9), src, dst)  # LZMA2
    else:
        raise ValueError(f"Algorithme inconnu : {algo}")
    return dst


def decompress(algo, src, dst=None):
    if algo == "7z" and HAS_PY7ZR and src.endswith(".7z"):
        outdir = dst or os.path.dirname(os.path.abspath(src))
        with py7zr.SevenZipFile(src, "r") as z:
            z.extractall(path=outdir)
        return outdir
    dst = dst or (src[: src.rfind(".")] + ".out" if "." in src else src + ".out")
    if algo == "bzip2":
        _stream(bz2.BZ2Decompressor(), src, dst)
    elif algo == "lzma":
        _stream(lzma.LZMADecompressor(format=lzma.FORMAT_ALONE), src, dst)
    elif algo == "7z":
        _stream(lzma.LZMADecompressor(format=lzma.FORMAT_XZ), src, dst)
    else:
        raise ValueError(f"Algorithme inconnu : {algo}")
    return dst


# ---------------------------------------------------------------- utilitaires
def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def human(n):
    for unit in ("o", "Ko", "Mo", "Go"):
        if n < 1024:
            return f"{n:.2f} {unit}"
        n /= 1024
    return f"{n:.2f} To"


def timed(fn, *args):
    t0 = time.perf_counter()
    result = fn(*args)
    return result, time.perf_counter() - t0


def report_line(algo, src, out, t):
    s0, s1 = os.path.getsize(src), os.path.getsize(out)
    ratio = (1 - s1 / s0) * 100 if s0 else 0.0
    print(f"[{algo}] {src} -> {out}")
    print(f"  Taille avant : {human(s0)} ({s0} octets)")
    print(f"  Taille après : {human(s1)} ({s1} octets)")
    print(f"  Taux de compression : {ratio:.2f} %   |   Temps : {t:.3f} s")


# ---------------------------------------------------------------- commandes
def cmd_compress(a):
    out, t = timed(compress, a.algo, a.fichier, a.sortie)
    report_line(a.algo, a.fichier, out, t)


def cmd_decompress(a):
    out, t = timed(decompress, a.algo, a.fichier, a.sortie)
    print(f"[{a.algo}] {a.fichier} -> {out}   (temps : {t:.3f} s)")


def cmd_bench(a):
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        for path in a.fichiers:
            s0 = os.path.getsize(path)
            for algo in ("bzip2", "lzma", "7z"):
                out = os.path.join(tmp, os.path.basename(path) + EXT[algo])
                _, tc = timed(compress, algo, path, out)
                s1 = os.path.getsize(out)
                # vérification : décompression + comparaison des empreintes SHA-256
                if algo == "7z" and HAS_PY7ZR:
                    # py7zr extrait dans un dossier, sous le nom d'origine du fichier
                    outdir = out + ".dir"
                    decompress(algo, out, outdir)
                    back = os.path.join(outdir, os.path.basename(path))
                else:
                    back = out + ".back"
                    decompress(algo, out, back)
                ok = "OK" if sha256(back) == sha256(path) else "ERREUR"
                rows.append([os.path.basename(path), algo, s0, s1,
                             round((1 - s1 / s0) * 100, 2) if s0 else 0, round(tc, 3), ok])
    header = ["Fichier", "Algo", "Taille initiale (o)", "Taille compressée (o)",
              "Taux (%)", "Temps compression (s)", "Intégrité"]
    print("| " + " | ".join(header) + " |")
    print("|" + "---|" * len(header))
    for r in rows:
        print("| " + " | ".join(map(str, r)) + " |")
    if a.csv:
        with open(a.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)
        print(f"\nRésultats enregistrés dans {a.csv}")


def main():
    p = argparse.ArgumentParser(description="Clone pédagogique de bzip2 / lzma / 7-zip")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("compress", help="compresser un fichier")
    c.add_argument("algo", choices=["bzip2", "lzma", "7z"])
    c.add_argument("fichier")
    c.add_argument("-o", "--sortie")
    c.set_defaults(func=cmd_compress)

    d = sub.add_parser("decompress", help="décompresser un fichier")
    d.add_argument("algo", choices=["bzip2", "lzma", "7z"])
    d.add_argument("fichier")
    d.add_argument("-o", "--sortie")
    d.set_defaults(func=cmd_decompress)

    b = sub.add_parser("bench", help="comparer les 3 algorithmes sur plusieurs fichiers")
    b.add_argument("fichiers", nargs="+")
    b.add_argument("--csv", help="exporter les résultats en CSV")
    b.set_defaults(func=cmd_bench)

    args = p.parse_args()
    try:
        args.func(args)
    except FileNotFoundError as e:
        sys.exit(f"Erreur : fichier introuvable ({e.filename})")


if __name__ == "__main__":
    main()
