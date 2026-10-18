const fs = require('node:fs');
const assert = require('node:assert/strict');
const YAML = require('yaml');
const path = require('node:path');
process.chdir(path.resolve(__dirname, '..'));
const read = p => fs.readFileSync(p, 'utf8');
const config = YAML.parse(read('compose.yaml'));
const verify = YAML.parse(read('compose.verify.yaml'));
assert.equal(config.services.app.build, '.');
assert.deepEqual(config.services.app.ports, ['127.0.0.1:${APP_PORT:-8002}:8000']);
assert.equal(config.services.app.environment.QDRANT_URL, 'http://qdrant:6333');
assert(config.services.app.volumes.includes('app_data:/app/data'));
assert(config.services.qdrant.volumes.includes('qdrant_data:/qdrant/storage'));
assert.equal(config.services.qdrant.ports, undefined);
assert.equal(config.services.qdrant.image, 'qdrant/qdrant:v1.19.1');
assert.equal(verify.services.app.environment.MODEL_MODE, 'demo');
for (const key of ['LLM_API_KEY', 'EMBEDDING_API_KEY', 'RERANK_API_KEY']) {
  assert.equal(verify.services.app.environment[key], '');
}
assert(read('.dockerignore').split(/\r?\n/).includes('.env'));
assert(read('Dockerfile').includes('/api/ready'));
assert(read('Dockerfile').includes('app.container_start'));
for (const file of ['requirements-docker.txt', 'app/container_start.py', 'app/static/index.html']) {
  assert(fs.existsSync(file));
}
console.log('Compose YAML and project invariants passed (not Docker runtime validation).');
