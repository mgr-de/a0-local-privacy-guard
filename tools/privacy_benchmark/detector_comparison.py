"""Offline A/B architecture comparison using one shared production mapping.

Run in the native A0 Python environment with optional Presidio installed.
All fixtures are synthetic. No inference calls or raw text are exported.
"""
import argparse
import json
import re
import tempfile
import time
from pathlib import Path

def run(output):
    from agent import Agent,AgentConfig
    from usr.plugins.local_privacy_guard.helpers import model_guard as guard
    from usr.plugins.local_privacy_guard.helpers.pii_detector import PIIFilter
    from usr.plugins.local_privacy_guard.helpers.mapping import Mapping
    from usr.plugins.local_privacy_guard.helpers.detection_cache import spans
    corpus=json.loads((Path(__file__).parents[2]/'tests/fixtures/multilingual_sessions.json').read_text())
    cases=[]
    for language in ['de','en']:
        people=corpus['languages'][language]['persons']
        for person in people:
            contacts='; '.join(person[key] for key in ['name','email','phone','iban'])
            name=person['name']
            for text in [contacts,json.dumps({'name':name,'email':person['email'],'phone':person['phone'],'iban':person['iban']}),f'# Contact {name}\nemail = "{person["email"]}"',f'Playwright / CSS / JavaScript / Agent Zero. Contact {contacts}']:
                gold=[]
                for kind,field in [('PERSON','name'),('EMAIL','email'),('TELEFON','phone'),('IBAN','iban')]:
                    for m in re.finditer(re.escape(person[field]),text):gold.append((m.start(),m.end(),kind))
                cases.append((language,text,gold))
        cases.extend((language,text,[]) for text in ['Playwright uses CSS and HTML.','Agent Zero uses JavaScript.','{"tool_name":"browser","action":"click","selector":"#submit"}','def process_json(value): return value'])
    report={'llm_calls':0,'fixtures':len(cases),'gold':'exact spans; synthetic annotated contacts and technical negatives','variants':{}}
    with tempfile.TemporaryDirectory() as directory:
        for variant in ['local','presidio-A','presidio-B']:
            by_language={};all_spans=[];roundtrips=0;semantic_roundtrips=0;leaks=0;started=time.perf_counter()
            scope='comparison-'+variant
            for language,text,gold in cases:
                cfg={'enabled':True,'languages':[language],'use_ner':True,'use_regex':True,'backend':'local' if variant=='local' else 'presidio','presidio_variant':variant[-1] if variant!='local' else 'A'}
                filt=PIIFilter({**cfg,'_cache_scope':scope})
                result=filt.filter(text)
                normalized=[(h.start,h.end,'IBAN' if h.pii_type=='IBAN_DE' else 'TELEFON' if h.pii_type=='TELEFON_INTL' else h.pii_type) for h in result.detections]
                found=set(normalized);expected=set(gold)
                tally=by_language.setdefault(language,{'tp':0,'fp':0,'fn':0})
                tally['tp']+=len(found&expected);tally['fp']+=len(found-expected);tally['fn']+=len(expected-found)
                all_spans.append(normalized)
                # Same production gateway/mapping for every backend; separate scopes.
                agent=Agent(0,AgentConfig(profile='agent0',mcp_servers=''))
                mapping=Mapping(('',variant),agent.context.id,directory)
                original=guard.mapping_for;guard.mapping_for=lambda unused:mapping
                try:
                    pipeline=guard.PayloadFilter(agent,{'pii_filter':cfg},True)
                    masked=pipeline.text(text)
                    restored=mapping.restore(masked)
                    roundtrips+=restored==text
                    try:semantic_roundtrips+=json.loads(restored)==json.loads(text)
                    except ValueError:semantic_roundtrips+=restored==text
                    leaks+=any(text[a:b] in masked for a,b,_ in gold)
                finally:guard.mapping_for=original
            for tally in by_language.values():
                tally['precision']=tally['tp']/(tally['tp']+tally['fp']) if tally['tp']+tally['fp'] else 1
                tally['recall']=tally['tp']/(tally['tp']+tally['fn']) if tally['tp']+tally['fn'] else 1
            report['variants'][variant]={'languages':by_language,'exact_roundtrips':roundtrips,'semantic_roundtrips':semantic_roundtrips,'cases_with_known_value_leak':leaks,'seconds':time.perf_counter()-started,'spans':all_spans}
            spans.clear_scope(scope)
    report['architecture_exact_span_agreement']=report['variants']['local']['spans']==report['variants']['presidio-A']['spans']
    for value in report['variants'].values():del value['spans']
    Path(output).write_text(json.dumps(report,indent=2));return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True)
    print(json.dumps(run(parser.parse_args().output)))
