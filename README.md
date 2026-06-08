# conf-loaders

Configuration loading utilities for Python projects. Load settings from YAML with environment variable substitution, relative path resolution, encrypted passwords, and advanced merge operations.

```sh
pip install conf-loaders
```

## What it does

`conf-loaders` solves the problem of keeping default settings in Python code while allowing local overrides via YAML files. It provides:

- **YAML settings loading** with automatic environment variable substitution (`${VAR}` or `${VAR:-default}`)
- **Relative path resolution** — relative paths in YAML are resolved to absolute paths automatically
- **Update operations** — extend lists, append items, update dicts without replacing the whole structure
- **Encrypted passwords** — load AES/RSA encrypted secrets from separate YAML files
- **Environment variable parsing** — parse prefixed environment variables into nested dict structures

## Quick start

### Basic usage in Django/Flask settings.py

```python
# settings.py — default values
DEBUG = False
ALLOWED_HOSTS = ["localhost"]
DATABASES = {
    "default": {"ENGINE": "django.db.backends.sqlite3"}
}
```

```yaml
# config.yaml — local overrides
DEBUG: true
ALLOWED_HOSTS@extend:
  - "my-domain.com"
DATABASES@update:
  default:
    NAME: "/path/to/db.sqlite3"
```

```python
# At the end of settings.py
from conf_loaders.utils.settings_load import load_settings_from_yaml
load_settings_from_yaml("config.yaml", object_to_update=locals())
```

After loading, `locals()` contains merged values from both sources.

## Features

### Environment variable substitution

YAML files are pre-processed with `varsubst` before parsing:

```yaml
DB_HOST: "${DB_HOST:-localhost}"
DB_PORT: "${DB_PORT:-5432}"
```

### Relative path resolution

String values that look like relative paths are resolved to absolute paths using `base_dir`:

```yaml
# Relative to the directory passed as base_dir
LOG_PATH: "../../data/logs/app.log"
MODEL_DIR: "./models"
```

To disable resolution for a specific value, prefix it with `!`:

```yaml
# Will remain "./relative/path" without resolution
PATTERN: "!./relative/path"
```

Path resolution is recursive — works inside nested dicts and lists.

U can disable all these operations by setting `base_dir=...`.

### Update operations

By default, a YAML key replaces the entire Python value. Use `@operation` suffixes to merge instead:

#### `@extend` — extend a list

```yaml
ALLOWED_HOSTS@extend:
  - "api.example.com"
  - "app.example.com"
```

#### `@append` — append a single item

```yaml
ALLOWED_HOSTS@append: "admin.example.com"
```

#### `@update` — update a dict (merge keys)

```yaml
DATABASES@update:
  default:
    HOST: "postgres.internal"
```

#### `@bind` — replace contents, keep object reference

Useful when other modules hold references to the list/dict:

```yaml
# Clears SCRIPT_ROOTS and fills with new values,
# but the list object in memory stays the same
SCRIPT_ROOTS@bind:
  - scripts/common/
  - scripts/custom/
```

#### `@setdefault` — set only if not defined

```yaml
DEBUG@setdefault: false
```

If `DEBUG` is already defined in `settings.py`, the YAML value is ignored.

#### Full operation reference

| Operation | Effect | Requires existing var |
|-----------|--------|----------------------|
| (no suffix) | Replace entirely | No |
| `@setdefault` | Set only if undefined | No |
| `@bind` | Clear + refill, keep object reference | No |
| `@append` | Append one item to list | Yes |
| `@try-append` | Append one item, create list if missing | No |
| `@extend` | Extend list with multiple items | Yes |
| `@try-extend` | Extend list, create if missing | No |
| `@update` | Merge dict keys | Yes |
| `@try-update` | Merge dict keys, create dict if missing | No |

### Nested key access

Operations support dot-notation for nested structures:

```yaml
# Sets DATABASES["default"]["PORT"] = 5433
DATABASES.default.PORT: 5433

# Appends to nested list
DATABASES.default.OPTIONS@append: "sslmode=require"
```

### Encrypted passwords

Store sensitive values in a separate encrypted file:

```python
from conf_loaders.utils.settings_load import load_passwords_from_yaml

load_passwords_from_yaml(
    passwords_file="secrets.yaml",
    secret_key_file=".secret.key",
    object_to_update=locals(),
)
```

```yaml
# secrets.yaml
DB_PASSWORD: "AES$salt$ciphertext"
API_KEY: "AES$salt$ciphertext"
```

Supported algorithms: `AES`, `RSA`.

### Environment variable parsing

Load prefixed environment variables into settings:

```python
from conf_loaders.utils.settings_load import load_vars_from_env

load_vars_from_env(
    object_to_update=locals(),
    prefix="MYAPP_",      # Only vars starting with MYAPP_
    secret_key_file=".secret.key",  # Auto-decrypt encrypted values
)
```

With `MYAPP_DB_HOST=localhost` and `MYAPP_DB_PORT_NUMBER=5432` and `MYAPP_USE_PROXY_FLAG=1` in environment:

```python
# Results in:
DB_HOST = "localhost"
DB_PORT = 5432
USE_PROXY = True
```

Double underscores create nested dicts: `MYAPP_CACHE__REDIS__HOST=localhost` → `CACHE["REDIS"]["HOST"] = "localhost"`.

## API reference

### `load_settings_from_yaml`

```python
load_settings_from_yaml(
    path: str | Path,
    object_to_update: MutableMapping[str, Any],
    base_dir: str | Path | None = None,
    show_update_errors: bool = True,
)
```

- **path** — path to YAML file
- **object_to_update** — dict-like object to update, usually `locals()`
- **base_dir** — directory for resolving relative paths; `None` disables resolution
- **show_update_errors** — whether to print values in error messages

### `load_passwords_from_yaml`

```python
load_passwords_from_yaml(
    passwords_file: str | Path,
    secret_key_file: str | Path,
    object_to_update: MutableMapping[str, Any],
    password_sep: str = "$",
) -> Dict[str, Dict[str, str]]
```

Returns a dict of successfully decrypted variables with their algorithms and keys.

### `load_vars_from_env`

```python
load_vars_from_env(
    object_to_update: MutableMapping[str, Any],
    secret_key_file: str | Path | None = None,
    password_sep: str = "$",
    prefix: str = "TRANSLATE_",
)
```

### `save_settings_debug`

```python
save_settings_debug(settings: Mapping[str, Any])
```

If `settings` contains `SAVE_SETTINGS_DEBUG` key with a file path, dumps all settings to that file as JSON (for debugging).

### File utilities

`conf_loaders.utils.docrender_utils.files` provides helpers for common file operations:

- `read_yaml(path)` / `write_yaml(path, data)` — YAML I/O
- `read_json(path)` / `write_json(path, data)` — JSON I/O
- `read_text(path)` / `write_text(path, text)` — Text I/O
- `mkdir(path)` / `mkdir_of_file(path)` / `mkparents(path)` — Directory creation
- `copy_file(src, dst)` / `move_file(src, dst)` — File operations
- `touch(path)` / `rmdir(path)` — Basic file ops

## Changelog

### 0.6.1

- `_resolve_variables` recursion hotfix

### 0.6.0

- `save_settings_debug`:
  - if `base_dir=None` then it will be extracted from `settings.BASE_DIR`

### 0.5.0

- `load_settings_from_yaml`:
  - relative path resolution can be disabled at all (even `!` removing) using `base_dir=...`
  - relative values start from `!` provide warning if `base_dir=None`
  - `resolve_content_from_env=False` disables file content resolving from environment
- `save_settings_debug`:
  - `base_dir` option (like in `load_settings_from_yaml`) provides supplement path resolution for debugging purposes

### 0.4.0

- Relative path resolution is now recursive — works inside nested dicts and lists, not just top-level values
- Values starting with `!` are excluded from path resolution

### Earlier versions

- Initial release with YAML loading, `varsubst`, update operations, encrypted passwords, and env var parsing
