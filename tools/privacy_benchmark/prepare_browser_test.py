"""Create only a new, local-only native chat and profile for browser testing."""
import json,sys
from pathlib import Path
sys.path.insert(0,'/a0')
from helpers import runtime,plugins,persist_chat
from agent import Agent,AgentConfig
runtime.args['dockerized']=True
profile='privacy_bench_browser'
folder=Path('/a0/usr/agents')/profile; folder.mkdir(parents=True,exist_ok=True)
if not (folder/'agent.yaml').exists():
    (folder/'agent.yaml').write_text('title: Privacy Browser Test\ndescription: Isolated local integration test\n')
plugins.toggle_plugin('requesty',False,agent_profile=profile)
plugins.toggle_plugin('local_privacy_guard',True,agent_profile=profile)
plugins.toggle_plugin('_memory',True,agent_profile=profile)
config=plugins.get_plugin_config('local_privacy_guard',agent_profile=profile)
config['verification']['enabled']=False
plugins.save_plugin_config('local_privacy_guard','',profile,config)
memory=plugins.get_plugin_config('_memory',agent_profile=profile)
memory.update(memory_memorize_enabled=False,memory_recall_enabled=True,memory_recall_query_prep=False,memory_recall_post_filter=False)
plugins.save_plugin_config('_memory','',profile,memory)
a=Agent(0,AgentConfig(profile=profile,mcp_servers='',knowledge_subdirs=[]))
slot={'provider':'ollama','name':'gemma3:4b','api_base':'http://host.docker.internal:11434',
      'ctx_length':16384,'kwargs':{'temperature':0,'max_tokens':1024,'num_ctx':16384,'timeout':180}}
a.context.set_data('chat_model_override',{'chat':slot,'utility':slot,'vision':{}})
a.context.name='Privacy Browser Test – local Ollama'
persist_chat.save_tmp_chat(a.context)
print(json.dumps({'context':a.context.id,'profile':profile,'name':a.context.name}))
