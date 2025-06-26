# Created by JeromeX ' 2025
#
# Note on duplicate handling for ‘ask’:
# Enter j → overwrite this file only
# Enter n → skip this file only
# Input A → automatically overwrite all other duplicates
# Enter N → Automatically skip all further duplicates
#
# Note on ZIP selection:
# Input yes → each category is saved as a ZIP file
# Input no → no ZIP will be created

import os
import shutil
import zipfile
import mysql.connector
from datetime import datetime

UPLOAD_DIR = "path to the upload folder"
OUTPUT_DIR = "exported_albums"
LOG_FILE = "failed_images.log"
FINISH_LOG = "finish.log"
HTML_REPORT = "report.html"

while True:
    zip_input = input("Should the categories be saved as ZIP files? (yes/no): ").strip().lower()
    if zip_input in ["yes", "no"]:
        ZIP_KATEGORIEN = zip_input == "yes"
        break
    else:
        print("Please enter 'yes' or 'no'.")

while True:
    dup_input = input("How should duplicates be handled? (always/never/ask):").strip().lower()
    if dup_input in ["always", "never", "ask"]:
        DUPLICATE_BEHAVIOR = dup_input
        break
    else:
        print("Please enter 'always', 'never' or 'ask'.")

conn = mysql.connector.connect(
    host="localhost",
    user="USERNAME",
    password="PASSWORD",
    database="DBNAME"
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
                    response = input(f"file already exists: {dst_path}. \noverwrite? (j/n/A/N): ").strip().lower()
                    if response == "a":
                        overwrite = True
                        overwrite_all = True
                    elif response == "n":
                        overwrite = False
                    elif response == "j":
                        overwrite = True
                    elif response == "n" or response == "N":
                        overwrite = False
                        skip_all = True
                    else:
                        overwrite = False

            if not overwrite:
                print(f"skip: {dst_path}")
                skipped_duplicates += 1
                skipped_files.append(dst_path)
                continue

        try:
            shutil.copy2(src_path, dst_path)
            print(f"copied: {src_path} -> {dst_path}")
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
    flog.write(f"Recognised links: {len(links)}\n")
    flog.write(f"Copied successfully: {copied_count}\n")
    flog.write(f"Duplicates skipped: {skipped_duplicates}\n")

with open(HTML_REPORT, "w", encoding="utf-8") as html:
    html.write(f"""<!DOCTYPE html>
<html lang='en'>
<head>
    <meta charset='UTF-8'>
    <title>Piwigo Export Report</title>
    <style>
        body {{ font-family: 'Segoe UI', sans-serif; background: #f4f4f9; color: #333; padding: 40px; }}
        h1 {{ color: #4CAF50; }}
        h2 {{ color: #555; border-bottom: 1px solid #ccc; padding-bottom: 5px; }}
        ul {{ list-style-type: none; padding-left: 0; }}
        li {{ padding: 4px 0; }}
        a {{ text-decoration: none; color: #1976D2; }}
        a:hover {{ text-decoration: underline; }}
        .success {{ color: #2e7d32; }}
        .skipped {{ color: #ef6c00; }}
        .missing {{ color: #c62828; }}
        footer {{ margin-top: 50px; font-size: 0.9em; color: #999; }}
    </style>
</head>
<body>
    <h1>Piwigo Export Report</h1>
    <p><strong>Created by:</strong> JeromeX</p>
    <p><strong>Date:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    <p><strong>Total allocations:</strong> {len(links)}</p>
    <p class='success'><strong>copied:</strong> {copied_count}</p>
    <p class='skipped'><strong>Duplicates skipped:</strong> {skipped_duplicates}</p>
    <h2>ZIP-Downloads per Category</h2>
    <ul>
""")
    for cat_id, folder in path_map.items():
        zip_name = os.path.basename(folder) + ".zip"
        if os.path.exists(f"{folder}.zip"):
            zip_path = os.path.relpath(f"{folder}.zip", start=os.path.dirname(HTML_REPORT))
            html.write(f"<li><a href='{zip_path}' download>{zip_name}</a></li>\n")
    html.write("""
    </ul>
    <h2>Copied Files</h2>
    <ul>""")
    for path in copied_files:
        html.write(f"<li class='success'>{path}</li>\n")
    html.write("""</ul>
    <h2>Skipped files</h2>
    <ul>""")
    for path in skipped_files:
        html.write(f"<li class='skipped'>{path}</li>\n")
    html.write("""</ul>
    <h2>Missing source files</h2>
    <ul>""")
    for path in missing_files:
        html.write(f"<li class='missing'>{path}</li>\n")
    html.write("""
    </ul>
    <footer>
        <p>Report automatically generated by Piwigo export script | JeromeX</p>
    </footer>
</body>
</html>""")
