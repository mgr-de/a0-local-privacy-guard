import { createStore } from "/js/AlpineStore.js";
import { callJsonApi } from "/js/api.js";
import {toastFrontendError,toastFrontendSuccess} from "/components/notifications/notification-store.js";

export const store = createStore("localPrivacy", {
    confirmMappingDeletion:false,
    async deleteMappings(){
        const context_id=globalThis.getContext?.();
        if(this.busy || !context_id || !this.confirmMappingDeletion)return;
        this.busy=true;const epoch=this.epoch;
        try{
            const result=await callJsonApi('plugins/local_privacy_guard/mappings',{context_id,confirmation:'DELETE_CHAT_MAPPINGS'});
            if(epoch!==this.epoch)return;
            if(!result.ok)throw new Error(result.error);
            this.confirmMappingDeletion=false;
            toastFrontendSuccess('Local mappings deleted for this chat. Old placeholders cannot be restored.','Local Privacy Guard');
        }catch(e){if(epoch===this.epoch)toastFrontendError(e.message,'Local Privacy Guard');}
        finally{if(epoch===this.epoch)this.busy=false;}
    },
    backendBusy:false, backendResult:null,
    async setupPresidio(action='check') {
        if(this.backendBusy)return;
        this.backendBusy=true;const epoch=this.epoch;
        try{
            const result=await callJsonApi('plugins/local_privacy_guard/presidio_setup',{action});
            if(epoch!==this.epoch)return;
            this.backendResult=result;
            if(!result.ok)throw new Error(result.error);
        }catch(e){if(epoch===this.epoch)toastFrontendError(e.message,'Local Privacy Guard');}
        finally{if(epoch===this.epoch)this.backendBusy=false;}
    },
    busy: false, result: null, checkedConfig: "", checkedAt: "", error: "", epoch: 0,
    ocrPath: "", ocrText: "", ocrBusy: false, ocrError: "",
    cleanup() { this.backendBusy=false; this.backendResult=null; this.confirmMappingDeletion=false; this.epoch++; this.busy = false; this.result = null; this.checkedConfig = ""; this.error = ""; this.ocrBusy=false; this.ocrPath=""; this.ocrText=""; this.ocrError=""; },
    current(config) { return !!this.result && this.checkedConfig === JSON.stringify(config); },
    async runOcr() {
        if (this.ocrBusy || !this.ocrPath.trim()) return;
        const epoch = this.epoch, path = this.ocrPath;
        this.ocrBusy = true; this.ocrText = ""; this.ocrError = "";
        try {
            const result = await callJsonApi("plugins/local_privacy_guard/ocr", { path });
            if (epoch !== this.epoch || path !== this.ocrPath) return;
            if (!result.ok) throw new Error(result.error);
            this.ocrText = result.text || "No text detected. This does not establish that the image contains no personal details.";
        } catch (error) { if (epoch === this.epoch) this.ocrError = error.message; }
        finally { if (epoch === this.epoch) this.ocrBusy = false; }
    },
    async runExample(config) {
        if (this.busy) return;
        const snapshot = JSON.stringify(config); const epoch = this.epoch;
        this.busy = true; this.result = null; this.error = "";
        try {
            const result = await callJsonApi("plugins/local_privacy_guard/example", { config: JSON.parse(snapshot) });
            if (epoch !== this.epoch || snapshot !== JSON.stringify(config)) return;
            if (!result.ok) throw new Error(result.error || "Could not run the local example.");
            this.result = result; this.checkedConfig = snapshot; this.checkedAt = new Date().toLocaleString();
        } catch (e) { if (epoch === this.epoch) this.error = e.message; }
        finally { if (epoch === this.epoch) this.busy = false; }
    }
});
