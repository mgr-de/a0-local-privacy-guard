"""Explicit isolated test-profile setup; never writes the user's source profile."""
import json,sys,os
from pathlib import Path
from copy import deepcopy
sys.path.insert(0,'/a0')
from helpers import plugins,persist_chat,runtime
from agent import Agent,AgentConfig
from usr.plugins.requesty.helpers import scope,catalog
from usr.plugins.requesty.helpers.runtime_guard import settings
runtime.args['dockerized']=True
source=('', 'agent0');profile='privacy_standard_requesty';owner=('',profile)
folder=Path('/a0/usr/agents')/profile;folder.mkdir(parents=True,exist_ok=True)
(folder/'agent.yaml').write_text('title: Privacy Requesty Test\ndescription: Synthetic budget-controlled photo/form integration\n')
policy=settings(source);key=scope.key(source);available=catalog.fetch(policy.endpoint,key)
setup=deepcopy(scope.read(source,'setup.json'))
for slot in ('chat','utility'):
    metadata=available[setup['models'][slot]['name']];policy.check(metadata)
    setup['models'][slot]['vision']=metadata.get('supports_vision') is True
    setup['models'][slot]['kwargs']={'a0_retry_attempts':0,'num_retries':0,'max_tokens':1024}
for name,data in (('config.json',scope.read(source,'config.json')),('credentials.json',{'key':key}),('setup.json',setup)):
    target=scope.path(owner,name);target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    target.write_text(json.dumps(data));os.chmod(target,0o600)
for name,enabled in (('requesty',True),('local_privacy_guard',True),('_memory',False)):
    plugins.toggle_plugin(name,enabled,agent_profile=profile)
config=plugins.get_plugin_config('local_privacy_guard',agent_profile=profile)
config['verification']['enabled']=False
config['pii_filter'].update(use_ner=True,use_regex=True,languages=['en','de'],action='redact')
plugins.save_plugin_config('local_privacy_guard','',profile,config)
agent=Agent(0,AgentConfig(profile=profile,mcp_servers='',knowledge_subdirs=[]))
agent.context.name='Privacy Requesty Photo Form Test'
persist_chat.save_tmp_chat(agent.context)
print(json.dumps({'context':agent.context.id,'profile':profile,'model':setup['models']['chat']['name']}))
