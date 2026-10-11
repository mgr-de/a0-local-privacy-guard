"""Presidio mapping survives a real process boundary; display stays separate."""
import argparse,json,sys,stat
from pathlib import Path
sys.path.append('/opt/privacybench-venv/lib/python3.12/site-packages')
from benchmark import Presidio,fixtures,VALUES
root=Path('/tmp/privacy-benchmark/mapping-restart');root.mkdir(parents=True,exist_ok=True)
p=argparse.ArgumentParser();p.add_argument('phase',choices=['prepare','resume']);args=p.parse_args()
adapter=Presidio(root=root/'maps',profile='restart-A',chat='restart-chat')
if args.phase=='prepare':
    source=fixtures('en')[0];masked=adapter.mask(source,'en')
    (root/'state.json').write_text(json.dumps({'source':source,'masked':masked}))
else:
    state=json.loads((root/'state.json').read_text());masked=state['masked']
    foreign=Presidio(root=root/'maps',profile='restart-B',chat='restart-chat')
    # Accumulate stream chunks without ever feeding local display back.
    reconstructed='';display=''
    for char in masked:
        reconstructed+=char;display=adapter.display(reconstructed)
    result={'exact_after_new_process':adapter.display(masked)==state['source'],
            'same_tokens_after_new_process':adapter.mask(state['source'],'en')==masked,
            'foreign_profile_cannot_decode':foreign.display(masked)==masked,
            'buffered_stream_final_display_exact':display==state['source'],
            'canonical_stream_is_masked':not any(v in reconstructed for v in VALUES),
            'mapping_permission_mode':oct(stat.S_IMODE(adapter.path.stat().st_mode))}
    (root/'results.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
