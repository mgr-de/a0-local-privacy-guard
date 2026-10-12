"""Private replay; numeric output only, no model transport."""
import sys,json,time,tempfile,statistics,argparse
from pathlib import Path
import usr.plugins.local_privacy_guard as package
parser=argparse.ArgumentParser();parser.add_argument('--plugin',required=True);parser.add_argument('--source',required=True);parser.add_argument('--output',required=True);options=parser.parse_args()
package.__path__=[options.plugin]
from usr.plugins.local_privacy_guard.helpers import model_guard as guard
from usr.plugins.local_privacy_guard.helpers.mapping import Mapping
from usr.plugins.local_privacy_guard.helpers.pii_detector import PIIFilter
from agent import Agent,AgentConfig
from helpers import runtime
runtime.args['dockerized']=True
# System prompt saved by the earlier isolated investigation, never exported.
source=Path(options.source).read_text()
settings={'enabled':True,'use_ner':True,'use_regex':True,'languages':['de','en'],'action':'redact','log_detections':False}
load=time.perf_counter();PIIFilter(settings).get_loaded_languages();load=time.perf_counter()-load
agent=Agent(0,AgentConfig(profile='agent0',mcp_servers=''))
report={'source_characters':len(source),'model_load_seconds':load,'llm_calls':0,'scenarios':{}}
with tempfile.TemporaryDirectory() as directory:
    mapping=Mapping(('','performance'),'synthetic',directory)
    guard.mapping_for=lambda unused:mapping
    def measure(text):
        start=time.perf_counter();p=guard.PayloadFilter(agent,{'pii_filter':settings},True);result=p.text(text)
        elapsed=time.perf_counter()-start
        assert mapping.restore(result)==text
        return elapsed,getattr(p.filter,'metrics',{}).copy(),p.detected_count
    # First complete pass also populates mapping and warms detector cache.
    first=measure(source);report['first_pass_seconds']=first[0]
    for scenario in ['unchanged','incremental','new']:
        samples=[];metrics=[]
        for i in range(20):
            if scenario=='unchanged':text=source
            elif scenario=='incremental':text=source+'\nIch bin Herr Max Mustermann und wohne in der Hauptstraße '+str(i+1)+'. Bitte trage das ein.'
            else:
                # Fresh, representative paragraph units; same size/structure.
                text='\n'.join(line+' testiteration '+str(i)+' '+str(n) for n,line in enumerate(source.splitlines()))
            seconds,stats,count=measure(text);samples.append(seconds);metrics.append(stats)
        ordered=sorted(samples)
        report['scenarios'][scenario]={'p50':statistics.median(samples),'p95':ordered[int(.95*len(ordered))-1],'samples':len(samples),'last_metrics':metrics[-1]}
Path(options.output).write_text(json.dumps(report,indent=2))
print(json.dumps(report))
