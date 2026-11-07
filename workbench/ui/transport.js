export class LocalTransport {
  constructor() {
    const params = new URLSearchParams(location.hash.slice(1));
    this.token = params.get('token') || sessionStorage.getItem('sipi-token') || '';
    if (params.has('token')) {
      sessionStorage.setItem('sipi-token', this.token);
      history.replaceState(null, '', location.pathname);
    }
    this.generation = 0;
    this.pendingStart = null;
    this.stopping = null;
    this.closed = false;
  }
  async request(path, body) {
    if (!this.token) throw new Error('Launch the offline application to connect to the calculation engine.');
    const response = await fetch(path, {method: body ? 'POST' : 'GET', headers: {'Authorization': `Bearer ${this.token}`, ...body ? {'Content-Type': 'application/json'} : {}}, ...body ? {body: JSON.stringify(body)} : {}});
    const value = await response.json();
    if (!response.ok) throw new Error(value.message || 'The calculation service could not complete the request.');
    return value;
  }
  async run(input) {
    if (this.stopping) await this.stopping;
    if (this.closed) throw new Error('The application is closed.');
    const generation = ++this.generation;
    const start = this.request('/api/job', input);
    this.pendingStart = start;
    try { await start; }
    catch (error) { if (generation === this.generation) throw error; }
    finally { if (this.pendingStart === start) this.pendingStart = null; }
    while (generation === this.generation) {
      await new Promise(resolve => setTimeout(resolve, 350));
      if (generation !== this.generation) break;
      const job = await this.request('/api/job');
      if (generation !== this.generation) break;
      if (job.status === 'complete') return job.result;
      if (job.status === 'error') {
        const error = new Error(job.message);
        error.history = job.history;
        throw error;
      }
      if (job.status === 'cancelled') break;
    }
    throw new DOMException('Calculation cancelled.', 'AbortError');
  }
  async stop(path) {
    ++this.generation;
    const previous = this.stopping, pending = this.pendingStart;
    const operation = (async () => {
      if (previous) await previous.catch(() => {});
      // Order stop after the server acknowledges start, even if start failed.
      if (pending) await pending.catch(() => {});
      await this.request(path, {});
    })();
    this.stopping = operation;
    try { await operation; }
    finally { if (this.stopping === operation) this.stopping = null; }
  }
  async cancel() { await this.stop('/api/cancel'); }
  async close() { this.closed = true; await this.stop('/api/shutdown'); }
}
