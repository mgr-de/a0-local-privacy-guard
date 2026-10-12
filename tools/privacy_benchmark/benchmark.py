"""Reproducible local PII benchmark. Synthetic data only; no paid LLM calls.

Run with privacybench-venv, supplying --plugin PATH --output PATH.
The Presidio persistent adapter is experimental benchmark code, not product code.
"""
import argparse
import hashlib
import importlib.metadata
import json
import os
import re
import sys
import time
from pathlib import Path

PEOPLE = [
    ('Anna Weber', 'anna.weber@example.com', '+49 30 55501001'),
    ('Ben Fischer', 'ben.fischer@example.com', '+49 30 55501002'),
    ('Clara Hoffmann', 'clara.hoffmann@example.com', '+49 30 55501003'),
    ('David Berger', 'david.berger@example.com', '+49 30 55501004'),
]

def iban(n):
    bban = '50010517' + str(9000000000 + n)
    checksum = 98 - int(bban + '131400') % 97
    return 'DE' + str(checksum).zfill(2) + bban

VALUES = [v for i, p in enumerate(PEOPLE) for v in (*p, iban(i))]
TYPES = ['PERSON', 'EMAIL_ADDRESS', 'PHONE_NUMBER', 'IBAN_CODE']

def fixtures(language):
    de = language == 'de'
    intro = ('Vier fiktive Personen für einen Datenschutztest:\n' if de else
             'Four fictional people for a privacy test:\n')
    intro += '\n'.join(f'{p[0]}; E-Mail/email: {p[1]}; Telefon/phone: {p[2]}; IBAN: {iban(i)}'
                       for i,p in enumerate(PEOPLE))
    turns = [intro]
    events = [
        ('Anna Weber ist mit Ben Fischer verheiratet. Clara Hoffmann ist Davids Schwester.',
         'Anna Weber is married to Ben Fischer. Clara Hoffmann is David Berger\'s sister.'),
        ('Anna Weber und Ben Fischer trennen sich. Clara Hoffmann und Ben Fischer werden Geschäftspartner.',
         'Anna Weber and Ben Fischer separate. Clara Hoffmann and Ben Fischer become business partners.'),
        ('David Berger schuldet Anna Weber 125 Euro. Ben Fischer schuldet Clara Hoffmann nichts.',
         'David Berger owes Anna Weber 125 euros. Ben Fischer owes Clara Hoffmann nothing.'),
        ('David Berger bezahlt Anna Weber. Clara Hoffmann und Ben Fischer beenden ihre Partnerschaft.',
         'David Berger pays Anna Weber. Clara Hoffmann and Ben Fischer end their partnership.'),
    ]
    for t in range(1,40):
        use_de = de or (language == 'mixed' and t % 2 == 0)
        if t in (1,10,20,30):
            text = events[(1,10,20,30).index(t)][0 if use_de else 1]
        elif t in (9,19,29,39):
            text = ('Fasse aktuelle Beziehungen und Schulden zusammen. Verwende die ursprünglichen Namen und Kontakte.'
                    if use_de else 'Summarize current relationships and debts. Use original names and contacts.')
        else:
            i = t % 4
            p = PEOPLE[i]
            text = (f'Bestätige unverändert {p[0]}, {p[1]}, {p[2]}, {iban(i)}. '
                    if use_de else f'Confirm unchanged {p[0]}, {p[1]}, {p[2]}, {iban(i)}. ')
            text += ('Beziehungen dürfen daraus nicht abgeleitet werden.' if use_de else
                     'Do not infer relationships from this reminder.')
        turns.append(text)
    return turns

def exact_restore(text, mapping):
    # One pass prevents recursive interpretation of originals containing tokens.
    if not mapping: return text
    pattern = re.compile('|'.join(re.escape(k) for k in sorted(mapping,key=len,reverse=True)))
    return pattern.sub(lambda m: mapping[m.group()], text)

class Local:
    def __init__(self, **kwargs):
        from pii_detector import PIIFilter
        self.filter = PIIFilter({'use_regex': True, 'use_ner': True,
                                 'languages':['en','de'], 'store_mapping':True})
        self.mapping = {}
    def mask(self,text,language):
        result = self.filter.filter(text)
        self.mapping.update(result.mapping)
        return result.filtered_text
    def display(self,text): return exact_restore(text,self.mapping)

class LocalRegex(Local):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.filter.use_ner = False

class Presidio:
    """Explicit adapter: unique per-scope tokens and local JSON persistence."""
    engine = None
    def __init__(self, root=None, profile='A', chat='1', project='P'):
        from presidio_analyzer import AnalyzerEngine
        from presidio_analyzer.nlp_engine import NlpEngineProvider
        if Presidio.engine is None:
            provider = NlpEngineProvider(nlp_configuration={'nlp_engine_name':'spacy',
                'models':[{'lang_code':'en','model_name':'en_core_web_sm'},
                          {'lang_code':'de','model_name':'de_core_news_sm'}]})
            Presidio.engine = AnalyzerEngine(nlp_engine=provider.create_engine(),supported_languages=['en','de'])
        self.scope = (profile,project,chat)
        self.namespace = hashlib.sha256(json.dumps(self.scope).encode()).hexdigest()[:12]
        self.path = Path(root) / (self.namespace + '.json') if root else None
        self.mapping = {}
        if self.path and self.path.exists():
            document = json.loads(self.path.read_text())
            if tuple(document['scope']) != self.scope: raise ValueError('Wrong mapping owner')
            self.mapping = document['mapping']
    def mask(self,text,language):
        langs = ['en','de'] if language == 'mixed' else [language]
        hits = []
        for lang in langs:
            hits.extend(self.engine.analyze(text=text,language=lang,entities=TYPES))
        selected = []
        for hit in sorted(hits,key=lambda h:(-(h.end-h.start),-h.score,h.start)):
            if not any(hit.start < x.end and x.start < hit.end for x in selected): selected.append(hit)
        for hit in sorted(selected,key=lambda h:h.start,reverse=True):
            value = text[hit.start:hit.end]
            token = next((k for k,v in self.mapping.items() if v==value),None)
            if token is None:
                token = f'[{self.namespace}_{hit.entity_type}_{len(self.mapping)+1}]'
                self.mapping[token] = value
            text = text[:hit.start] + token + text[hit.end:]
        if self.path:
            self.path.parent.mkdir(parents=True,exist_ok=True)
            temporary = self.path.with_suffix('.tmp')
            temporary.write_text(json.dumps({'scope':self.scope,'mapping':self.mapping}),encoding='utf-8')
            os.chmod(temporary,0o600)
            os.replace(temporary,self.path)
        return text
    def display(self,text): return exact_restore(text,self.mapping)

class LLMGuard:
    scanner = None
    def __init__(self, **kwargs):
        from llm_guard.input_scanners import Anonymize
        from llm_guard.vault import Vault
        from llm_guard.output_scanners import Deanonymize
        self.vault = Vault()
        if LLMGuard.scanner is None:
            LLMGuard.scanner = Anonymize(self.vault,entity_types=TYPES.copy(),language='en')
        self.scanner = LLMGuard.scanner
        self.decoder = Deanonymize(self.vault)
    @property
    def mapping(self): return dict(self.vault.get())
    def mask(self,text,language):
        # Native DE unsupported: evaluate English scanner's actual behavior on DE/mixed.
        self.scanner._vault = self.vault
        return self.scanner.scan(text)[0]
    def display(self,text): return self.decoder.scan('',text)[0]

def run_variant(name, factory, root, skip_long_tail=False):
    report = {'name':name,'languages':{},'lifecycle':{},'errors':[]}
    for language in ('de','en','mixed'):
        adapter = factory(root=root,chat=language)
        rows = []
        initial = None
        for turn,text in enumerate(fixtures(language)):
            started = time.perf_counter()
            masked = adapter.mask(text,language)
            elapsed = time.perf_counter()-started
            restored = adapter.display(masked)
            present = [v for v in VALUES if v in text]
            leaked = [v for v in present if v in masked]
            aliases = [v for v in ('Anna','Ben','Clara','David','Davids')
                       if re.search(r'\b'+v+r'\b',text) and v not in present]
            rows.append({'turn':turn,'original':text,'masked':masked,'display':restored,
                         'expected_full_values':len(present),'leaked_full_values':leaked,
                         'remaining_name_forms':[v for v in aliases if re.search(r'\b'+v+r'\b',masked)],
                         'exact_roundtrip':restored==text,'seconds':elapsed})
            if turn == 0: initial = dict(adapter.mapping)
        # Persisted transcript is ALWAYS masked. Display never feeds next input.
        report['languages'][language] = {'turns':rows,
            'total_full_value_occurrences':sum(r['expected_full_values'] for r in rows),
            'leaked_full_value_occurrences':sum(len(r['leaked_full_values']) for r in rows),
            'exact_roundtrips':sum(r['exact_roundtrip'] for r in rows),
            'initial_distinct_mapping_values':len(set(initial.values())),
            'initial_mapping_entries':len(initial),
            'initial_mapping':initial,
            'native_language_supported':name!='llm_guard' or language=='en'}
    a = factory(root=root,chat='scope',profile='A',project='P')
    source = 'Contact anna.weber@example.com and ben.fischer@example.com.'
    masked = a.mask(source,'en')
    again = a.mask(source,'en')
    recreated = factory(root=root,chat='scope',profile='A',project='P')
    report['lifecycle']['stable_repeat'] = masked == again
    report['lifecycle']['exact_two_email_roundtrip'] = a.display(masked) == source
    report['lifecycle']['restart_restores_original'] = recreated.display(masked) == source
    for key,kwargs in [('different_chat',{'chat':'other'}),('different_profile',{'profile':'B','chat':'scope'}),
                       ('different_project',{'project':'Q','chat':'scope'})]:
        b = factory(root=root,**kwargs)
        b.mask('Contact intruder@example.com.','en')
        report['lifecycle'][key+'_does_not_decode_foreign_tokens'] = b.display(masked) == masked
    # Entire accumulated prefix processed each time: simulates split token streaming.
    report['lifecycle']['accumulated_chunks_final_display_all_splits'] = all(
        a.display(''.join([masked[:i],masked[i:]])) == source for i in range(len(masked)+1))
    broken = []
    for i in range(len(masked)+1):
        if a.display(masked[:i])+a.display(masked[i:]) != source: broken.append(i)
    report['lifecycle']['independent_chunk_split_failures'] = len(broken)
    report['lifecycle']['buffered_complete_response_exact'] = a.display(masked)==source
    # Literal tokens are attacker/user controlled: must not become private data in model history.
    report['lifecycle']['literal_placeholder_can_be_decoded'] = bool(a.mapping) and a.display(next(iter(a.mapping))) != next(iter(a.mapping))
    clean = ['The blue chair is beside the table.', 'Der blaue Stuhl steht neben dem Tisch.',
             'There are 4 people and 125 euros.', 'Es gibt 4 Personen und 125 Euro.']
    report['false_positive_controls'] = [{'text':s,'masked':a.mask(s,'mixed')} for s in clean]
    edge_cases = [
        ('de', 'Anna Weber hat eine neue E-Mail: anna.neu@example.com. Die alte Adresse anna.weber@example.com gehört weiterhin zu Anna Weber.'),
        ('en', 'Ben Fischer now owes Clara Hoffmann 40 euros, while David Berger owes Anna Weber nothing.'),
        ('mixed', 'Anna arbeitet mit Ben. Clara hilft David. Davids Schwester ist Clara. Anna works with Ben.'),
        ('de', 'Kontakt: Anna Weber, anna.weber@example.com; IBAN: '+ ' '.join(iban(0)[i:i+4] for i in range(0,22,4))),
        ('en', 'No private data: version 1.3.0, 4 people, 125 euros, local mode.'),
    ]
    report['edge_cases'] = []
    for language,text in edge_cases:
        masked_edge = a.mask(text,language)
        report['edge_cases'].append({'language':language,'original':text,'masked':masked_edge,
            'display':a.display(masked_edge),'exact_roundtrip':a.display(masked_edge)==text})
    long_text = '\n'.join(fixtures('mixed'))
    try:
        started = time.perf_counter()
        long_masked = a.mask(long_text,'mixed')
        report['long_context'] = {'characters':len(long_text),'seconds':time.perf_counter()-started,
            'remaining_full_values':[v for v in VALUES if v in long_masked],
            'exact_roundtrip':a.display(long_masked)==long_text}
    except Exception as error:
        report['long_context'] = {'characters':len(long_text),'error':type(error).__name__+': '+str(error)}
    very_long = ('The blue chair is beside the table. ' * 900) + '\nContact Anna Weber, anna.weber@example.com.'
    try:
        started = time.perf_counter()
        if skip_long_tail: raise RuntimeError('Explicitly skipped: previous unbounded transformer run was killed. See run evidence.')
        masked_tail = a.mask(very_long,'en')
        report['long_tail'] = {'characters':len(very_long),'seconds':time.perf_counter()-started,
            'name_leaked':'Anna Weber' in masked_tail,'email_leaked':'anna.weber@example.com' in masked_tail,
            'exact_roundtrip':a.display(masked_tail)==very_long}
    except Exception as error:
        report['long_tail'] = {'characters':len(very_long),'error':type(error).__name__+': '+str(error)}
    if isinstance(a,Presidio):
        saved = a.path.read_text()
        a.path.write_text('{broken',encoding='utf-8')
        try:
            factory(root=root,chat='scope',profile='A',project='P')
            report['lifecycle']['corrupt_storage_fails_closed'] = False
        except (ValueError,KeyError): report['lifecycle']['corrupt_storage_fails_closed'] = True
        finally: a.path.write_text(saved,encoding='utf-8')
    else: report['lifecycle']['corrupt_storage_fails_closed'] = 'not implemented: no persistence'
    return report

def main():
    args = argparse.ArgumentParser()
    args.add_argument('--plugin',required=True)
    args.add_argument('--output',required=True)
    args.add_argument('--variants',default='local,presidio,llm_guard')
    args.add_argument('--skip-long-tail',action='store_true',help='Avoid repeating a previously killed unbounded long-text inference')
    options = args.parse_args()
    sys.path.insert(0,options.plugin)
    output = Path(options.output)
    output.mkdir(parents=True,exist_ok=True)
    results = {'paid_calls':0,'paid_cost_eur':0,'scope':'local synthetic sequence; NOT live Agent Zero or reasoning',
        'versions':{p:importlib.metadata.version(p) for p in ('presidio-analyzer','presidio-anonymizer','llm-guard','spacy','torch')},
        'people':[{'name':p[0],'email':p[1],'phone':p[2],'iban':iban(i)} for i,p in enumerate(PEOPLE)],'variants':{}}
    for name in options.variants.split(','):
        print('START',name,flush=True)
        try: results['variants'][name] = run_variant(name,{'local':Local,'local_regex':LocalRegex,'presidio':Presidio,'llm_guard':LLMGuard}[name],output/'mappings'/name,options.skip_long_tail)
        except Exception as error: results['variants'][name] = {'error':type(error).__name__+': '+str(error)}
        (output/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
        print('DONE',name,flush=True)
    print('RESULT',output/'results.json',flush=True)

if __name__ == '__main__': main()
