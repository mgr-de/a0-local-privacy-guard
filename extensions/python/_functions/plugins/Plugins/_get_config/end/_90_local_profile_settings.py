from helpers.extension import Extension
from helpers import plugins
from usr.plugins.local_privacy_guard.helpers.agent_scope import selected_path

class LocalProfileSettings(Extension):
    def execute(self, data, **kwargs):
        args = data.get("args", ())
        inputs = args[1] if len(args) > 1 else data.get("kwargs", {}).get("input", {})
        if inputs.get("plugin_name") != "local_privacy_guard" or not isinstance(data.get("result"), dict):
            return
        project = inputs.get("project_name", "")
        profile = inputs.get("agent_profile", "")
        path = selected_path(project, profile) if profile else None
        exists = path is not None and path.exists()
        data["result"] = {"ok":True,
            "data":plugins.get_plugin_config("local_privacy_guard", project_name=project, agent_profile=profile, caller="ui"),
            "loaded_path":str(path) if exists else "", "loaded_project_name":project if exists else "",
            "loaded_agent_profile":profile if exists else ""}
