"""Production mapping implementation across two processes, synthetic only."""
import argparse,json,sys,stat
from pathlib import Path
sys.path.insert(0,'/a0')
from usr.plugins.local_privacy_guard.helpers.mapping import Mapping
parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['prepare','resume']);args=parser.parse_args()
root=Path('/tmp/privacy-benchmark/standard-mapping-restart');root.mkdir(parents=True,exist_ok=True)
mapping=Mapping(('','privacy_standard_restart'),'synthetic-chat',root/'mappings')
source='Anna Weber / Ben Fischer / anna@example.com / DE10500105179000000000'
values=[('PERSON','Anna Weber'),('PERSON','Ben Fischer'),('EMAIL','anna@example.com'),('IBAN','DE10500105179000000000')]
if args.phase=='prepare':
    masked=source
    for kind,value in values:masked=masked.replace(value,mapping.token(kind,value))
    (root/'state.json').write_text(json.dumps({'source':source,'masked':masked}))
else:
    state=json.loads((root/'state.json').read_text())
    masked=source
    for kind,value in values:masked=masked.replace(value,mapping.token(kind,value))
    foreign=Mapping(('','another-profile'),'synthetic-chat',root/'mappings')
    result={'exact_after_new_process':mapping.restore(state['masked'])==source,
            'same_tokens_after_new_process':masked==state['masked'],
            'foreign_profile_cannot_decode':foreign.restore(masked)==masked,
            'mapping_permission_mode':oct(stat.S_IMODE(mapping.path.stat().st_mode))}
    assert all(result[key] for key in result if key!='mapping_permission_mode')
    (root/'results.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
