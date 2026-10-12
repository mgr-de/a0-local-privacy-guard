"""English LLM Guard in its own dependency environment; cached models only."""
import json,os,sys
os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
from benchmark import LLMGuard
adapter=None
for line in sys.stdin:
    try:
        data=json.loads(line)
        if data['op']=='reset' or adapter is None:adapter=LLMGuard()
        if data['op']=='mask':value=adapter.mask(data['text'],'en')
        elif data['op']=='display':value=adapter.display(data['text'])
        else:value=''
        result={'value':value,'mapping':adapter.mapping}
    except Exception as exc:result={'error':str(exc)}
    print('PRIVACY_RESULT:'+json.dumps(result,ensure_ascii=False),flush=True)
