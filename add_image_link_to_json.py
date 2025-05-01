import os
import json

json_dir = "./json_results"
image_dir = "./processed_images"
image_ext = ".jpg"

for filename in os.listdir(json_dir):
    if not filename.endswith(".json"):
        continue

    json_path = os.path.join(json_dir, filename)
    base_id = os.path.splitext(filename)[0]
    image_path = os.path.join(image_dir, base_id + image_ext)

    with open(json_path, "r", encoding="utf-8") as f:
        original = json.load(f)

    rel_url = os.path.relpath(image_path, start=json_dir)


    updated = {
        "checked": "no",
        **original,
        "image_url": rel_url,
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(updated, f, indent=2, ensure_ascii=False)

    print(f"✅ Updated {filename} with checked='no' first, image_url: {rel_url}")
