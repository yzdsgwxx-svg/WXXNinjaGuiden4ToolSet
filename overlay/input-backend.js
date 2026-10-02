function createBackend({gameInput, xInput, log = () => {}, forceXInput = false}) {
  if (!forceXInput) {
    try { return {read: gameInput(), name: 'GameInput'}; }
    catch (error) { log('GameInput unavailable; using Windows XInput', error.message); }
  }
  return {read: xInput(), name: 'XInput'};
}
module.exports = {createBackend};
