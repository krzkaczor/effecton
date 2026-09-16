// A minimal JSON-RPC client for a language server speaking LSP over stdio.
//
// Just enough for one short session: framed writes, framed reads, promise per
// request id, and a hook to answer the few requests a server sends back (ty
// asks for `workspace/configuration` and registers capabilities).

import { type ChildProcess, spawn } from 'node:child_process'

type Message = {
  jsonrpc: '2.0'
  id?: number | string
  method?: string
  params?: unknown
  result?: unknown
  error?: { code: number; message: string; data?: unknown }
}

type Pending = {
  resolve: (value: unknown) => void
  reject: (error: Error) => void
  timer: NodeJS.Timeout
}

export class LspError extends Error {
  override name = 'LspError'
}

export class LspClient {
  readonly #child: ChildProcess
  readonly #pending = new Map<number, Pending>()
  readonly #onServerRequest: (method: string, params: unknown) => unknown
  #buffer = Buffer.alloc(0)
  #nextId = 1
  #exited: Error | null = null
  #stderr = ''

  constructor(
    command: string,
    args: string[],
    options: { cwd: string; onServerRequest?: (method: string, params: unknown) => unknown },
  ) {
    this.#onServerRequest = options.onServerRequest ?? (() => null)
    this.#child = spawn(command, args, { cwd: options.cwd, stdio: ['pipe', 'pipe', 'pipe'] })
    this.#child.stdout!.on('data', (chunk: Buffer) => this.#receive(chunk))
    this.#child.stderr!.on('data', (chunk: Buffer) => {
      this.#stderr += chunk.toString('utf8')
    })
    this.#child.on('error', (error) => this.#fail(new LspError(`Could not start ${command}: ${error.message}`)))
    this.#child.on('exit', (code, signal) => {
      if (this.#pending.size > 0)
        this.#fail(
          new LspError(
            `${command} exited (${code ?? signal}) with requests outstanding.\n${this.#stderr.trim()}`,
          ),
        )
    })
  }

  request<T>(method: string, params: unknown, timeoutMs = 10_000): Promise<T> {
    if (this.#exited) return Promise.reject(this.#exited)
    const id = this.#nextId++
    return new Promise<T>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.#pending.delete(id)
        reject(new LspError(`${method} timed out after ${timeoutMs}ms`))
      }, timeoutMs)
      this.#pending.set(id, { resolve: resolve as (value: unknown) => void, reject, timer })
      this.#send({ jsonrpc: '2.0', id, method, params })
    })
  }

  notify(method: string, params: unknown): void {
    this.#send({ jsonrpc: '2.0', method, params })
  }

  /** Waits for the server to exit after `exit` was sent; kills it after `graceMs`. */
  close(graceMs = 2_000): Promise<void> {
    return new Promise((resolve) => {
      if (this.#child.exitCode !== null || this.#child.signalCode !== null) return resolve()
      const timer = setTimeout(() => this.#child.kill('SIGKILL'), graceMs)
      this.#child.once('exit', () => {
        clearTimeout(timer)
        resolve()
      })
    })
  }

  get stderr(): string {
    return this.#stderr
  }

  #send(message: Message): void {
    const body = Buffer.from(JSON.stringify(message), 'utf8')
    this.#child.stdin!.write(`Content-Length: ${body.byteLength}\r\n\r\n`)
    this.#child.stdin!.write(body)
  }

  #receive(chunk: Buffer): void {
    this.#buffer = Buffer.concat([this.#buffer, chunk])
    for (;;) {
      const headerEnd = this.#buffer.indexOf('\r\n\r\n')
      if (headerEnd === -1) return
      const header = this.#buffer.subarray(0, headerEnd).toString('ascii')
      const length = /Content-Length:\s*(\d+)/i.exec(header)
      if (!length) {
        this.#fail(new LspError(`Malformed LSP header: ${header}`))
        return
      }
      const bodyStart = headerEnd + 4
      const bodyEnd = bodyStart + Number(length[1])
      if (this.#buffer.byteLength < bodyEnd) return
      const body = this.#buffer.subarray(bodyStart, bodyEnd).toString('utf8')
      this.#buffer = this.#buffer.subarray(bodyEnd)
      this.#dispatch(JSON.parse(body) as Message)
    }
  }

  #dispatch(message: Message): void {
    if (message.method !== undefined) {
      if (message.id === undefined) return // notification from the server: ignore
      let result: unknown = null
      try {
        result = this.#onServerRequest(message.method, message.params)
      } catch {
        result = null
      }
      this.#send({ jsonrpc: '2.0', id: message.id, result })
      return
    }
    if (typeof message.id !== 'number') return
    const pending = this.#pending.get(message.id)
    if (!pending) return
    this.#pending.delete(message.id)
    clearTimeout(pending.timer)
    if (message.error) pending.reject(new LspError(`${message.error.message} (${message.error.code})`))
    else pending.resolve(message.result)
  }

  #fail(error: Error): void {
    this.#exited = error
    for (const pending of this.#pending.values()) {
      clearTimeout(pending.timer)
      pending.reject(error)
    }
    this.#pending.clear()
  }
}
