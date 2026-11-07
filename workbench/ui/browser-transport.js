export class BrowserTransport {
  constructor() { this.worker = null; this.sequence = 0; this.pending = new Map(); }
  async run(input) {
    if (!this.worker) {
      this.worker = new Worker(new URL('./worker.js', import.meta.url));
      this.worker.onmessage = event => {
        const message = event.data;
        const pending = this.pending.get(message.id);
        if (!pending) return;
        clearTimeout(pending.timer); this.pending.delete(message.id);
        if (message.status === 'complete') pending.resolve(message.result);
        else {
          const error = new Error(message.message); error.history = message.history; pending.reject(error);
          if (message.fatal) this.reset(error);
        }
      };
      this.worker.onerror = event => this.reset(new Error(event.message || 'Browser calculation engine failed to load.'));
    }
    const id = ++this.sequence;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => this.reset(new Error('Calculation exceeded the five-minute limit.')), 300000);
      this.pending.set(id, {resolve, reject, timer});
      this.worker.postMessage({id, input});
    });
  }
  reset(error) {
    this.worker?.terminate(); this.worker = null;
    for (const pending of this.pending.values()) { clearTimeout(pending.timer); pending.reject(error); }
    this.pending.clear();
  }
  async cancel() { this.reset(new DOMException('Calculation cancelled.', 'AbortError')); }
  async close() { this.reset(new DOMException('Workspace closed.', 'AbortError')); }
}
