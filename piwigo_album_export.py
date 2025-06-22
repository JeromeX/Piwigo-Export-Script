# Erstellt von JeromeX
#
# Hinweis zur Duplikatbehandlung bei "fragen":
#   Eingabe j → nur diese Datei überschreiben
#   Eingabe n → nur diese Datei überspringen
#   Eingabe A → alle weiteren Duplikate automatisch überschreiben
#   Eingabe N → alle weiteren Duplikate automatisch überspringen

import os
import shutil
import zipfile
import mysql.connector
from datetime import datetime

UPLOAD_DIR = "/media/USB/upload/"
OUTPUT_DIR = "exported_albums"
LOG_FILE = "fehlgeschlagene_bilder.log"
FINISH_LOG = "finish.log"
HTML_REPORT = "report.html"

ZIP_KATEGORIEN = input("Sollen die Kategorien als ZIP-Dateien gespeichert werden? (ja/nein): ").strip().lower() == "ja"
DUPLICATE_BEHAVIOR = input("Wie sollen Duplikate behandelt werden? (immer/nie/fragen): ").strip().lower()

DB_CONFIG = {
    "host": "localhost",
    "user": "piwigo_user",
    "password": "piwigo_pass",
    "database": "piwigo"
}

os.makedirs(OUTPUT_DIR, exist_ok=True)

conn = mysql.connector.connect(**DB_CONFIG)
cursor = conn.cursor()

cursor.execute("SELECT id, name, id_uppercat, uppercats FROM piwigo_categories")
categories = cursor.fetchall()
category_dict = {}
for cat in categories:
    cat_id, name, parent_id, uppercats = cat
    category_dict[cat_id] = {"name": name, "parent_id": parent_id, "uppercats": uppercats or ""}

path_map = {}
for cat_id, data in category_dict.items():
    if not data["uppercats"]:
        continue
    id_path = [int(i) for i in data["uppercats"].split(",") if i.isdigit() and int(i) in category_dict]
    folder_parts = [category_dict[i]["name"] for i in id_path]
    folder_path = os.path.join(OUTPUT_DIR, *folder_parts)
    os.makedirs(folder_path, exist_ok=True)
    path_map[cat_id] = folder_path

cursor.execute("SELECT id, file, path FROM piwigo_images")
images = cursor.fetchall()
image_dict = {img_id: {"name": file_name, "path": path} for img_id, file_name, path in images}

cursor.execute("SELECT image_id, category_id FROM piwigo_image_category")
links = cursor.fetchall()

copied_count = 0
total_links = len(links)
skipped_duplicates = 0
overwrite_all = False
skip_all = False
copied_files = []
skipped_files = []
missing_files = []

with open(LOG_FILE, "w", encoding="utf-8") as log:
    for image_id, category_id in links:
        try:
            if image_id not in image_dict or category_id not in path_map:
                continue
            img = image_dict[image_id]
            relative_path = os.path.normpath(img["path"]).lstrip("./")
            if relative_path.startswith("upload/"):
                relative_path = relative_path[7:]
            src_path = os.path.join(UPLOAD_DIR, relative_path)
            dst_path = os.path.join(path_map[category_id], img["name"])

            if os.path.exists(dst_path):
                if DUPLICATE_BEHAVIOR == "immer":
                    overwrite = True
                elif DUPLICATE_BEHAVIOR == "nie":
                    overwrite = False
                else:
                    if overwrite_all:
                        overwrite = True
                    elif skip_all:
                        overwrite = False
                    else:
                        response = input(f"Datei existiert bereits: {dst_path}. \nÜberschreiben? (j/n/A/N): ").strip().lower()
                        if response == "a":
                            overwrite = True
                            overwrite_all = True
                        elif response == "n":
                            overwrite = False
                        elif response == "j":
                            overwrite = True
                        elif response == "N":
                            overwrite = False
                            skip_all = True
                        else:
                            overwrite = False

                if not overwrite:
                    print(f"Überspringe: {dst_path}")
                    skipped_duplicates += 1
                    skipped_files.append(dst_path)
                    continue

            try:
                shutil.copy2(src_path, dst_path)
                print(f"Kopiert: {src_path} -> {dst_path}")
                copied_count += 1
                copied_files.append(dst_path)
            except FileNotFoundError:
                print(f"FEHLT: {src_path}")
                log.write(f"FEHLT: {src_path}\n")
                missing_files.append(src_path)
        except Exception as e:
            msg = f"Fehler bei Verknüpfung: Bild {image_id}, Kategorie {category_id} -> {e}\n"
            print(msg.strip())
            log.write(msg)

cursor.close()
conn.close()

if ZIP_KATEGORIEN:
    for cat_id, folder in path_map.items():
        zip_path = f"{folder}.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(folder):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, os.path.dirname(folder))
                    zipf.write(file_path, arcname)

with open(FINISH_LOG, "w", encoding="utf-8") as flog:
    flog.write(f"Erkannte Verknüpfungen: {total_links}\n")
    flog.write(f"Erfolgreich kopiert: {copied_count}\n")
    flog.write(f"Übersprungene Duplikate: {skipped_duplicates}\n")
