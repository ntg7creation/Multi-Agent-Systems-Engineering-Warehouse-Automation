/**
 * @typedef {Object} WorkerRequest
 * @property {string} requestId
 * @property {{type: string, payload?: Object}} command
 *
 * @typedef {Object} WorkerSuccess
 * @property {string} requestId
 * @property {true} success
 * @property {unknown} data
 *
 * @typedef {Object} WorkerFailure
 * @property {string} requestId
 * @property {false} success
 * @property {{message: string, type?: string, traceback?: string}} error
 */

export {}
