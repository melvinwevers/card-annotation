import gcsfs
import json

with open("key.json") as f:
    gcs_conf = json.load(f)

fs = gcsfs.GCSFileSystem(token=gcs_conf)

print(fs.ls("card_annotation/jsons"))
