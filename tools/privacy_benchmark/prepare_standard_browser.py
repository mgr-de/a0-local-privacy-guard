"""Create a separate saved chat for native photo/form testing, local models only."""
import json,sys
from pathlib import Path
sys.path.insert(0,'/a0')
from agent import Agent,AgentConfig
from helpers import plugins,persist_chat,runtime
runtime.args['dockerized']=True
profile='privacy_standard_browser'
folder=Path('/a0/usr/agents')/profile;folder.mkdir(parents=True,exist_ok=True)
(folder/'agent.yaml').write_text('title: Privacy Standard Test\ndescription: Synthetic local photo and form test\n')
for name,enabled in (('requesty',False),('local_privacy_guard',True),('_memory',False)):
    plugins.toggle_plugin(name,enabled,agent_profile=profile)
config=plugins.get_plugin_config('local_privacy_guard',agent_profile=profile)
config['verification']['enabled']=False
config['pii_filter'].update(use_ner=True,use_regex=True,languages=['en','de'],action='redact')
plugins.save_plugin_config('local_privacy_guard','',profile,config)
slot={'provider':'ollama_chat','name':'gemma3:4b','api_base':'http://host.docker.internal:11434',
      'ctx_length':32768,'vision':True,'kwargs':{'temperature':0,'max_tokens':1536,'num_ctx':32768,'timeout':180}}
agent=Agent(0,AgentConfig(profile=profile,mcp_servers='',knowledge_subdirs=[]))
agent.context.set_data('chat_model_override',{'chat':slot,'utility':slot,'vision':{}})
agent.context.name='Privacy Standard Photo Form Test'
persist_chat.save_tmp_chat(agent.context)
print(json.dumps({'context':agent.context.id,'profile':profile,'name':agent.context.name}))
