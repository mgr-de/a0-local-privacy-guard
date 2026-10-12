"""Real native compaction transport and Requesty ownership probe, local only."""
import asyncio,json
from copy import deepcopy
from unittest.mock import patch
from pathlib import Path
from memory_profile_test import agent,SOURCE,fingerprints
from helpers import litellm_transport
from plugins._chat_compaction.helpers import compactor
from usr.plugins.requesty.helpers import scope
from usr.plugins.requesty.helpers.policy import PolicyError

async def run():
    a=agent('privacy_bench_memory_a');before=fingerprints();payloads=[]
    original=litellm_transport.acompletion
    async def capture(**kw):
        if kw.get('api_base','').rstrip('/')!='http://host.docker.internal:11434' or not str(kw.get('model','')).startswith(('ollama/','ollama_chat/')):
            raise RuntimeError('External compaction call refused')
        payloads.append(deepcopy(kw.get('messages',[])))
        return await original(**kw)
    log=a.context.log.log(type='info',heading='Local compaction probe')
    with patch.object(litellm_transport,'acompletion',new=capture):
        response=await compactor._compact_single_pass(a,SOURCE,log,a.get_chat_model())
    blocked=False
    try:scope.key(('',a.config.profile))
    except PolicyError:blocked=True
    result={'compaction_payloads':payloads,'summary':response,
        'unmasked_full_values':[v for v in ('Anna Weber','Ben Fischer','anna.weber@example.com','+49 30 55501001','DE10500105179000000000') if v in json.dumps(payloads)],
        'foreign_profile_cannot_read_agent0_key':blocked,
        'foreign_profile_has_no_requesty_setup':scope.read(('',a.config.profile),'setup.json') is None,
        'user_settings_unchanged':before==fingerprints()}
    root=Path('/tmp/privacy-benchmark/compaction-probe');root.mkdir(parents=True,exist_ok=True)
    (root/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k not in ('compaction_payloads','summary')}),flush=True)
asyncio.run(run())
