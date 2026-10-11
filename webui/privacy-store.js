import { createStore } from "/js/AlpineStore.js";
import { callJsonApi } from "/js/api.js";

export const store = createStore("localPrivacy", {
    busy: false, result: null, checkedConfig: "", checkedAt: "", error: "", epoch: 0,
    cleanup() { this.epoch++; this.busy = false; this.result = null; this.checkedConfig = ""; this.error = ""; },
    current(config) { return !!this.result && this.checkedConfig === JSON.stringify(config); },
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
