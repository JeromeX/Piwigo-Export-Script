# Created by JeromeX 22/06/2025
#
# Duplicate handling when set to "ask":
#   Input y → only overwrite this file
#   Input n → only skip this file
#   Input A → overwrite all further duplicates automatically
#   Input N → skip all further duplicates automatically
#
# ZIP export choice:
#   Input yes  → create a ZIP file for each category
#   Input no   → do not create any ZIP files

import os
import shutil
import zipfile
import mysql.connector
from datetime import datetime

UPLOAD_DIR = "PATH TO FOLDER" ## the exact upload path must be entered here ##
OUTPUT_DIR = "exported_albums"
LOG_FILE = "missing_images.log"
FINISH_LOG = "finish.log"
HTML_REPORT = "report.html"

while True:
    zip_input = input("Do you want to save categories as ZIP files? (yes/no): ").strip().lower()
    if zip_input in ["yes", "no"]:
        ZIP_KATEGORIEN = zip_input == "yes"
        break
    else:
        print("Please enter 'yes' or 'no'.")

while True:
    dup_input = input("How should duplicates be handled? (always/never/ask): ").strip().lower()
    if dup_input in ["always", "never", "ask"]:
        DUPLICATE_BEHAVIOR = dup_input
        break
    else:
        print("Please enter 'always', 'never' or 'ask'.")

conn = mysql.connector.connect(
    host="localhost",
    user="piwigo_user", ## DATABASE USER ##
    password="piwigo_pass", ## DATABASE PASSWORD ##
    database="piwigo" ## DATABASE NAME ##
)
cursor = conn.cursor()

os.makedirs(OUTPUT_DIR, exist_ok=True)

cursor.execute("SELECT id, name, id_uppercat, uppercats FROM piwigo_categories")
categories = cursor.fetchall()
category_dict = {cat[0]: {"name": cat[1], "parent_id": cat[2], "uppercats": cat[3] or ""} for cat in categories}

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
image_dict = {img[0]: {"name": img[1], "path": img[2]} for img in images}

cursor.execute("SELECT image_id, category_id FROM piwigo_image_category")
links = cursor.fetchall()

copied_count = 0
skipped_duplicates = 0
overwrite_all = False
skip_all = False
copied_files = []
skipped_files = []
missing_files = []

with open(LOG_FILE, "w", encoding="utf-8") as log:
    for image_id, category_id in links:
        if image_id not in image_dict or category_id not in path_map:
            continue

        img = image_dict[image_id]
        rel_path = os.path.normpath(img["path"]).lstrip("./")
        if rel_path.startswith("upload/"):
            rel_path = rel_path[7:]

        src_path = os.path.join(UPLOAD_DIR, rel_path)
        dst_path = os.path.join(path_map[category_id], img["name"])

        if os.path.exists(dst_path):
            if DUPLICATE_BEHAVIOR == "always":
                overwrite = True
            elif DUPLICATE_BEHAVIOR == "never":
                overwrite = False
            else:
                if overwrite_all:
                    overwrite = True
                elif skip_all:
                    overwrite = False
                else:
                    response = input(f"File already exists: {dst_path}
Overwrite? (y/n/A/N): ").strip().lower()
                    if response == "a":
                        overwrite = True
                        overwrite_all = True
                    elif response == "n":
                        overwrite = False
                    elif response == "y":
                        overwrite = True
                    elif response == "n" or response == "N":
                        overwrite = False
                        skip_all = True
                    else:
                        overwrite = False

            if not overwrite:
                print(f"Skipping: {dst_path}")
                skipped_duplicates += 1
                skipped_files.append(dst_path)
                continue

        try:
            shutil.copy2(src_path, dst_path)
            print(f"Copied: {src_path} -> {dst_path}")
            copied_count += 1
            copied_files.append(dst_path)
        except FileNotFoundError:
            print(f"MISSING: {src_path}")
            log.write(f"MISSING: {src_path}\n")
            missing_files.append(src_path)

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
    flog.write(f"Total image links: {len(links)}\n")
    flog.write(f"Successfully copied: {copied_count}\n")
    flog.write(f"Skipped duplicates: {skipped_duplicates}\n")
