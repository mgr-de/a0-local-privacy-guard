"""Explicit setup download; immutable revision and checksum manifest, no text input."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

REPO = 'Wismut/nym-pii-multilingual'
REVISION = '0ed0242d67a30ca6a83e5f118506ff1e1daf83ca'


def prepare(destination, variant='int8'):
    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    files = {}
    for local in ('model.onnx', 'tokenizer.json', 'config.json'):
        remote = ('int8/' + ('model_int8.onnx' if local == 'model.onnx' else local)) if variant == 'int8' else local
        target = root / local
        digest = hashlib.sha256()
        # Atomic files prevent interrupted downloads from becoming usable bundles.
        temporary = target.with_suffix(target.suffix + '.partial')
        with urlopen(f'https://huggingface.co/{REPO}/resolve/{REVISION}/{remote}', timeout=60) as response, temporary.open('wb') as output:
            for block in iter(lambda: response.read(1024 * 1024), b''):
                output.write(block); digest.update(block)
        temporary.replace(target)
        files[local] = digest.hexdigest()
    manifest = {'repository': REPO, 'revision': REVISION, 'variant': variant, 'files': files}
    (root / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--destination', required=True)
    parser.add_argument('--variant', choices=['int8', 'fp32'], default='int8')
    args = parser.parse_args()
    print(json.dumps(prepare(args.destination, args.variant), indent=2))
