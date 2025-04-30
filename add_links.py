import csv, json, pathlib

# 1. build {image filename → public URL}
with open('drive_links.csv', newline='', encoding='utf-8') as f:
    next(f, None)                                    # skip header if present
    link = {row[0]: row[1] for row in csv.reader(f) if len(row) >= 2}

# 2. patch every wrapper JSON
for jf in pathlib.Path('json').glob('*.json'):
    wrapper = json.load(open(jf, encoding='utf-8'))

    fname = jf.stem + '.jpg'                         # adjust extension if PNG/TIF
    url   = link.get(fname)
    if not url:
        print(f'⚠️  no url for {fname} — skipping'); continue

    wrapper['_url'] = url                           # add/replace field
    with open(jf, 'w', encoding='utf-8') as g:
        json.dump(wrapper, g, indent=2, ensure_ascii=False)

print('✔ all wrappers updated with Google-Drive links')
