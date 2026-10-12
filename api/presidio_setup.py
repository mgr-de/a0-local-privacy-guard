"""Explicit authenticated optional package setup. Never changes filter settings."""
import asyncio
import subprocess
import sys
import threading
from helpers.api import ApiHandler
from usr.plugins.local_privacy_guard.helpers.presidio_backend import PIN,validate

_installation_lock=threading.Lock()

class PresidioSetup(ApiHandler):
    async def process(self,input,request):
        if input.get('action')=='check':
            try:validate(['en','de']);return {'ok':True,'available':True,'version':PIN,'restart_required':False}
            except ValueError as error:return {'ok':True,'available':False,'error':str(error)}
        if input.get('action')!='install':return {'ok':False,'error':'Unknown optional setup action.'}
        def install():
            from usr.plugins.local_privacy_guard.helpers import presidio_backend as backend
            if not _installation_lock.acquire(blocking=False):return False
            backend.restart_requested=True
            try:
                completed=subprocess.run([sys.executable,'-m','pip','install','--disable-pip-version-check',
                    '--index-url','https://pypi.org/simple','presidio-analyzer=='+PIN,'spacy==3.8.16'],
                    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=300)
            except (OSError,subprocess.TimeoutExpired):
                return False
            finally:
                # Even a failed installer may have changed packages. Require a
                # restart rather than trust a partially changed Python process.
                _installation_lock.release()
            return completed.returncode==0
        if not await asyncio.to_thread(install):
            return {'ok':False,'error':'Optional package installation failed. Filter settings are unchanged. Restart Agent Zero before retrying or using Presidio; the installer may have changed packages.'}
        return {'ok':True,'available':True,'version':PIN,'restart_required':True}
