import importlib.util
from pathlib import Path
import pytest

def load():
    source=Path(__file__).parents[1]/'helpers'/'inherited_bridge.py'
    spec=importlib.util.spec_from_file_location('bridge_under_test',source)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def test_install_and_owned_uninstall_preserve_other_files(tmp_path):
    bridge=load();root=tmp_path/'usr/plugins/local_privacy_guard';root.mkdir(parents=True)
    protected=root.parent.parent/'model-presets.json';protected.write_text('unchanged')
    result=bridge.manage(root)
    assert result['native_adapters_installed']==len(bridge.sources())
    for relative in bridge.sources():
        path=root.parent.parent/'extensions/python'/relative
        compile(path.read_text(),str(path),'exec')
    result=bridge.manage(root,remove=True)
    assert result['native_adapters_removed']==len(bridge.sources())
    assert protected.read_text()=='unchanged' and root.exists()

def test_foreign_adapter_collision_is_rejected_before_any_write(tmp_path):
    bridge=load();root=tmp_path/'usr/plugins/local_privacy_guard';root.mkdir(parents=True)
    first=next(iter(bridge.sources()));target=root.parent.parent/'extensions/python'/first
    target.parent.mkdir(parents=True);target.write_text('foreign extension')
    with pytest.raises(ValueError):bridge.manage(root)
    assert target.read_text()=='foreign extension'
    assert not (root/'inherited-bridge.json').exists()

def test_modified_adapter_is_preserved_on_uninstall(tmp_path):
    bridge=load();root=tmp_path/'usr/plugins/local_privacy_guard';root.mkdir(parents=True)
    bridge.manage(root);first=next(iter(bridge.sources()));target=root.parent.parent/'extensions/python'/first
    target.write_text('user modified extension')
    result=bridge.manage(root,remove=True)
    assert result['native_adapters_removed']==len(bridge.sources())-1
    assert target.read_text()=='user modified extension'

def test_zip_replacement_retains_ownership_for_adapter_update(tmp_path,monkeypatch):
    import shutil
    bridge=load();root=tmp_path/'usr/plugins/local_privacy_guard';root.mkdir(parents=True)
    bridge.manage(root)
    assert root.resolve().is_relative_to(tmp_path.resolve())
    shutil.rmtree(root);root.mkdir()
    updated={path:source+'\n# next version\n' for path,source in bridge.sources().items()}
    monkeypatch.setattr(bridge,'sources',lambda:updated)
    assert bridge.manage(root)['native_adapters_installed']==len(updated)

def test_foreign_ownership_journal_is_preserved(tmp_path):
    bridge=load();root=tmp_path/'usr/plugins/local_privacy_guard';root.mkdir(parents=True)
    manifest=root.parent.parent/'privacy-guard-adapters'/(bridge.PLUGIN+'.json')
    manifest.parent.mkdir();manifest.write_text('{"other_user_data":"preserve"}')
    with pytest.raises(ValueError):bridge.manage(root)
    assert manifest.read_text()=='{"other_user_data":"preserve"}'
