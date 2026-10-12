"""Offline regression corpus. No LLM calls; answer quality is explicitly untested."""
import argparse
import json
import re
from pathlib import Path
from types import SimpleNamespace

def run(output,use_ner=False,backend='local'):
    from agent import Agent,AgentConfig
    from usr.plugins.local_privacy_guard.helpers import model_guard as guard
    from usr.plugins.local_privacy_guard.helpers.mapping import Mapping
    from usr.plugins.local_privacy_guard.helpers.pii_detector import PIIFilter
    import tempfile
    corpus=json.loads((Path(__file__).parents[2]/'tests/fixtures/multilingual_sessions.json').read_text())
    report={'llm_calls':0,'answer_quality':'not tested by this deterministic replay','mode':'ner' if use_ner else 'regex','backend':backend,'sessions':[]}
    with tempfile.TemporaryDirectory(prefix='privacy-language-') as folder:
      for language in ([*corpus['languages'],'mixed'] if backend=='local' else ['de','en','mixed']):
       for count in (40,100):
        source=corpus['languages']['de' if language=='mixed' else language]
        persons=source['persons']
        langs=(list(corpus['languages']) if backend=='local' else ['de','en']) if language=='mixed' else [language]
        settings={'enabled':True,'use_regex':True,'use_ner':use_ner,'languages':langs,'action':'redact','backend':backend}
        scanner=PIIFilter(settings)
        missing=set(scanner.ner_languages)-set(scanner.get_loaded_languages()) if use_ner else set()
        if missing:
            report['sessions'].append({'language':language,'messages':count,'blocked':True,'missing_models':sorted(missing)})
            continue
        agent=Agent(0,AgentConfig(profile='agent0',mcp_servers=''))
        mapping=Mapping(('',language),agent.context.id,folder)
        original_mapping_for=guard.mapping_for;guard.mapping_for=lambda unused:mapping
        try:
          pipeline=guard.PayloadFilter(agent,{'pii_filter':settings},True)
          history=[];oracle=[];roundtrips=0;formal_leaks=0;name_leaks=0;alias_roundtrips=0;fragment_leaks=0;stable_families=0;first_families=None
          graph={'relationships':[],'debts':[]}
          for turn in range(count):
            mixed_languages=list(corpus['languages']) if backend=='local' else ['de','en']
            current_language=mixed_languages[turn%len(mixed_languages)] if language=='mixed' else language
            template=corpus['languages'][current_language]['templates'][turn%2]
            statement=template.format(a=persons[0]['name'],b=persons[1]['name'],c=persons[2]['name'],d=persons[3]['name'],amount=turn+1)
            graph={'relationships':[['A','B']] if turn%2==0 else [],'debts':[['C','D',turn+1]] if turn%2==0 else []}
            text=json.dumps({'persons':persons,'statement':statement,'graph':graph,
                'collision':source['collision_name'],'variant':persons[0]['name'].upper()},ensure_ascii=False)
            entry={'role':'user' if turn%3 else 'tool','content':text}
            history.append(entry);oracle.append(entry)
            # Replay full system/user/tool text; simulate masked history persisted
            # and context compaction rather than only checking the newest message.
            payload=[{'role':'system','content':'Use synthetic facts and preserve graph identifiers.'},*history]
            expected=[payload[0],*oracle]
            masked=pipeline.value(payload)
            restored=[{**message,'content':mapping.restore(message['content'])} for message in masked]
            roundtrips+=restored==expected
            history=masked[1:] # native model history remains canonical/masked
            rendered=json.dumps(masked,ensure_ascii=False).casefold()
            formal_leaks+=any(person[key].casefold() in rendered for person in persons for key in ('email','phone','iban'))
            name_leaks+=any(person['name'].casefold() in rendered for person in persons)
            fragment_leaks+=any(re.search(r'(?<!\w)'+re.escape(part.casefold())+r'(?!\w)',rendered)
                                for person in persons for part in (person['name'].split()[0],person['name'].split()[-1]) if len(part)>2)
            current=json.loads(masked[-1]['content'])
            families=[]
            from usr.plugins.local_privacy_guard.helpers.mapping import TOKEN
            for person in current['persons']:
                name=person['name'];families.append(re.sub(r'_V\d+(?=\])','',name) if TOKEN.fullmatch(name) else None)
            if first_families is None:first_families=families
            stable_families+=all(families) and families==first_families and len(set(families))==4
            alias_roundtrips+=mapping.restore(pipeline.text(persons[0]['name'].upper()))==persons[0]['name'].upper()
            if (turn+1)%20==0:
                mapping=Mapping(('',language),agent.context.id,folder) # reopen persistent mapping
                history=history[-8:] # separate context-compaction boundary
                oracle=oracle[-8:]
          report['sessions'].append({'language':language,'messages':count,'blocked':False,
              'exact_roundtrips':roundtrips,'formal_value_leak_turns':formal_leaks,'whole_name_leak_turns':name_leaks,
              'case_variant_roundtrips':alias_roundtrips,'deterministic_graph_roundtrips':roundtrips,
              'name_fragment_leak_turns':fragment_leaks,'stable_full_name_family_turns':stable_families,
              'limitations':'Graph is an oracle, not a generated LLM answer. Partial disclosures and semantic reidentification are not exhaustively measured.'})
          print(json.dumps({'language':language,'messages':count,'exact_roundtrips':roundtrips,'formal_leak_turns':formal_leaks,'name_leak_turns':name_leaks}),flush=True)
        finally:guard.mapping_for=original_mapping_for
    Path(output).write_text(json.dumps(report,ensure_ascii=False,indent=2))
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);parser.add_argument('--ner',action='store_true');parser.add_argument('--backend',choices=['local','presidio'],default='local')
    args=parser.parse_args();report=run(args.output,args.ner,args.backend)
    print(json.dumps({'sessions':len(report['sessions']),'blocked':sum(s['blocked'] for s in report['sessions']),
        'formal_value_leak_turns':sum(s.get('formal_value_leak_turns',0) for s in report['sessions']),
        'exact_roundtrips':sum(s.get('exact_roundtrips',0) for s in report['sessions'])}))
