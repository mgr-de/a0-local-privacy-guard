"""Local native Ollama reasoning probe; no external destinations."""
import json,urllib.request
from pathlib import Path
root=Path('/tmp/privacy-benchmark/reasoning-native');root.mkdir(parents=True,exist_ok=True)
prompt='[PERSON_1] owes [PERSON_2] 125 euros, then pays 75 euros and later 50 euros. Think through the updates, then say which outstanding debt remains. Keep all placeholders unchanged.'
results=[]
for model in ('qwen3:8b','deepseek-r1:8b'):
    body={'model':model,'messages':[{'role':'user','content':prompt}], 'stream':True,'think':True,
          'options':{'temperature':0,'num_predict':1024,'num_ctx':4096},'keep_alive':'2m'}
    req=urllib.request.Request('http://host.docker.internal:11434/api/chat',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    row={'model':model,'input':prompt,'chunks':[],'content':'','thinking':''}
    try:
        with urllib.request.urlopen(req,timeout=180) as response:
            for line in response:
                chunk=json.loads(line);msg=chunk.get('message',{})
                row['chunks'].append({'content':msg.get('content',''),'thinking':msg.get('thinking',''),'done':chunk.get('done',False)})
                row['content']+=msg.get('content','');row['thinking']+=msg.get('thinking','')
                if chunk.get('done'):row['done_reason']=chunk.get('done_reason');row['eval_count']=chunk.get('eval_count')
    except Exception as exc:row['error']=str(exc)
    row['has_think_tags']='<think>' in row['content']
    results.append(row);(root/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
    print(model,'content',len(row['content']),'thinking',len(row['thinking']),'tags',row['has_think_tags'],row.get('error',''),flush=True)
