# Clone Python de bzip2, lzma et 7-zip

Projet d'examen — Codage et Traitement du Signal (L2 Informatique, ESTI).

Utilitaire en ligne de commande (et interface graphique animée) qui compresse, décompresse
et compare les algorithmes **bzip2**, **lzma** et **7-zip (LZMA2)**, avec mesure des tailles,
du taux de compression et du temps d'exécution.

## Installation

```
pip install -r requirements.txt     # py7zr : nécessaire pour produire de vrais fichiers .7z
```

Python 3.8+ ; Tkinter est inclus avec Python (sous Linux : `sudo apt install python3-tk`).

## Utilisation (ligne de commande)

```
python compressor.py compress   bzip2 fichier.txt
python compressor.py compress   lzma  fichier.txt
python compressor.py compress   7z    fichier.txt
python compressor.py decompress bzip2 fichier.txt.bz2 -o fichier_restaure.txt
python compressor.py bench texte.txt audio.mp3 image.png video.mp4 --csv resultats.csv
```

## Interface graphique

```
python gui.py
```

## Contenu du dépôt

| Fichier | Rôle |
|---|---|
| `compressor.py` | Programme principal (CLI) |
| `gui.py` | Interface graphique animée |
| `rapport_compression.pdf` | Rapport d'analyse comparative |
| `resultats.csv` | Mesures brutes du benchmark |
| `captures/` | Captures d'écran du rapport |

## Auteur

Jonathan — ESTI, Antananarivo
