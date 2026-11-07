"""Read reviewed supplemental notices omitted from some upstream wheels."""

import hashlib
import json
from pathlib import Path


def supplemental_notices(scope):
    root = Path(__file__).resolve().parent / 'notices'
    inventory = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    notices, components = [], []
    for item in inventory['components']:
        if item['scope'] not in (scope, 'both'):
            continue
        data = (root / item['file']).read_bytes()
        if hashlib.sha256(data).hexdigest() != item['sha256']:
            raise ValueError('Supplemental notice hash mismatch: ' + item['name'])
        notices.append(f'\n--- {item["name"]} {item["version"]} ---\n'
                       f'Source: {item["source"]}\n{data.decode("utf-8")}\n')
        components.append(item)
    return notices, components
