import importlib.util
from pathlib import Path
import pytest

ROOT=Path(__file__).parents[1]/'helpers'
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def test_only_finally_deleted_chat_and_its_sidecars(tmp_path):
    mapping=load('mapping');cleanup=load('mapping_cleanup')
    deleted=mapping.Mapping(('','profile'),'deleted',tmp_path)
    archived=mapping.Mapping(('','profile'),'archived',tmp_path)
    deleted.token('PERSON','Synthetic Person');archived.token('PERSON','Other Person')
    for suffix in ('-wal','-shm','-journal'):
        Path(str(deleted.path)+suffix).write_bytes(b'')
    assert cleanup.remove_chat('deleted',tmp_path)==1
    assert archived.path.exists()
    assert all(not Path(str(deleted.path)+s).exists() for s in ('','-wal','-shm','-journal'))
    assert cleanup.remove_chat('deleted',tmp_path)==0

def test_foreign_database_and_symlink_preserved(tmp_path):
    cleanup=load('mapping_cleanup')
    foreign=tmp_path/'foreign.sqlite';foreign.write_text('keep')
    assert cleanup.remove_chat('chat',tmp_path)==0
    assert foreign.read_text()=='keep'

def test_invalid_chat_does_not_touch_data(tmp_path):
    with pytest.raises(ValueError):load('mapping_cleanup').remove_chat('',tmp_path)
