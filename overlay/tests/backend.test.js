const test = require('node:test');
const assert = require('node:assert/strict');
const {createBackend} = require('../input-backend');
test('missing GameInput uses built-in XInput without an installation prompt', () => {
  const read = () => [{index: 0}];
  const backend = createBackend({gameInput(){throw Error('DLL missing');}, xInput(){return read;}});
  assert.equal(backend.name, 'XInput');
  assert.deepEqual(backend.read(), [{index: 0}]);
});
test('available GameInput does not initialize the fallback', () => {
  const backend = createBackend({gameInput(){return () => [];}, xInput(){throw Error('must not run');}});
  assert.equal(backend.name, 'GameInput');
});
