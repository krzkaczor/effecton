// On-disk cache for ty-client results, one JSON file per snippet.
//
// The key covers everything that can change a hover: the snippet, the ty
// version, the effecton sources and lockfile, and this helper's own sources.
// So a library change or a parser fix invalidates automatically and nobody has
// to remember to clear a directory.

import { spawnSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import * as fs from 'node:fs'
import * as path from 'node:path'

export class TyUnavailableError extends Error {
  override name = 'TyUnavailableError'
}

const memo = new Map<string, string>()

export function cacheKey(code: string, rootDir: string, docsDir: string): string {
  const parts = {
    code,
    ty: tyVersion(rootDir),
    lib: libraryHash(rootDir),
    helper: helperHash(docsDir),
  }
  return createHash('sha256').update(JSON.stringify(parts)).digest('hex').slice(0, 16)
}

export function readCache<T>(dir: string, key: string): T | null {
  const file = path.join(dir, `${key}.json`)
  if (!fs.existsSync(file)) return null
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8')) as T
  } catch {
    return null
  }
}

export function writeCache(dir: string, key: string, data: unknown): void {
  fs.mkdirSync(dir, { recursive: true })
  const file = path.join(dir, `${key}.json`)
  fs.writeFileSync(`${file}.tmp`, JSON.stringify(data))
  fs.renameSync(`${file}.tmp`, file)
}

/** `uv run ty --version`; throws `TyUnavailableError` when uv or ty cannot run. */
export function tyVersion(rootDir: string): string {
  return memoized(`ty:${rootDir}`, () => {
    const result = spawnSync('uv', ['run', 'ty', '--version'], {
      cwd: rootDir,
      encoding: 'utf8',
      timeout: 120_000,
    })
    if (result.error || result.status !== 0)
      throw new TyUnavailableError(
        `Could not run \`uv run ty --version\` in ${rootDir}: ${result.error?.message ?? result.stderr}`,
      )
    return result.stdout.trim()
  })
}

function libraryHash(rootDir: string): string {
  return memoized(`lib:${rootDir}`, () => {
    const files = [
      ...listFiles(path.join(rootDir, 'packages/effecton/src'))
        .filter((f) => f.endsWith('.py') && !path.basename(f).startsWith('test_'))
        .sort(),
      path.join(rootDir, 'packages/effecton/pyproject.toml'),
      path.join(rootDir, 'pyproject.toml'),
      path.join(rootDir, 'uv.lock'),
    ]
    return hashFiles(rootDir, files)
  })
}

function helperHash(docsDir: string): string {
  return memoized(`helper:${docsDir}`, () => {
    const dir = path.join(docsDir, 'twoslash')
    const files = listFiles(dir)
      .filter((f) => f.endsWith('.ts'))
      .sort()
    return hashFiles(docsDir, files)
  })
}

function listFiles(dir: string): string[] {
  if (!fs.existsSync(dir)) return []
  return fs
    .readdirSync(dir, { recursive: true, withFileTypes: true })
    .filter((entry) => entry.isFile())
    .map((entry) => path.join(entry.parentPath, entry.name))
}

function hashFiles(base: string, files: string[]): string {
  const hash = createHash('sha256')
  for (const file of files) {
    if (!fs.existsSync(file)) continue
    hash.update(path.relative(base, file))
    hash.update('\0')
    hash.update(fs.readFileSync(file))
    hash.update('\0')
  }
  return hash.digest('hex')
}

function memoized(key: string, compute: () => string): string {
  const cached = memo.get(key)
  if (cached !== undefined) return cached
  const value = compute()
  memo.set(key, value)
  return value
}
