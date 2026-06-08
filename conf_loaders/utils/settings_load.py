
from typing import MutableMapping, Mapping, Any, Optional, Dict

import os
import io
from pathlib import Path

from .docrender_utils.aliases import PathLike
from .docrender_utils.files import read_yaml, is_like_relative_path, read_text
from .docrender_utils.lock import get_lock


def _resolve_variables(v: Any, base_dir: Optional[PathLike] = None) -> Any:
    """resolves variable as absolute path is it is relative and is not forbidden to be resolved"""

    if isinstance(v, dict):
        return {
            k: _resolve_variables(vv, base_dir=base_dir)
            for k, vv in v.items()
        }
    if isinstance(v, (list, tuple)):
        return [
            _resolve_variables(vv, base_dir=base_dir) for vv in v
        ]

    if isinstance(v, str):
        if v.startswith('!'):  # when resolution is forbidden
            v = v[1:]
            if v and is_like_relative_path(v):
                return v  # return unresolved
            return '!' + v  # return original
        elif base_dir and is_like_relative_path(v):
            return str(Path(base_dir, v).resolve().absolute())  # return resolved

    return v


def load_settings_from_yaml(
    path: PathLike,
    object_to_update: MutableMapping[str, Any],
    base_dir: Optional[PathLike] = None,
    show_update_errors: bool = True,
):
    """
    performs settings update from yaml file with extra actions such as
        `varsubst`, relative paths resolution, yaml commands execution

    Args:
        path: path to yaml file
        object_to_update: object to be updated using this file, usually locals()
        base_dir: base directory to translate relative paths; None means to disable this translation
        show_update_errors: whether to verbose updating errors

    """
    from varsubst import varsubst

    text = read_text(path)
    text = varsubst(text)

    new_vars = read_yaml(io.StringIO(text))
    if new_vars:
        new_vars = _resolve_variables(new_vars, base_dir=base_dir)

        # much extended version of object_to_update.update(_new_vars)
        from .settings_update import update_data
        update_data(
            commands=new_vars, data=object_to_update,
            show_values_on_error=show_update_errors,
        )


def load_passwords_from_yaml(
    passwords_file: PathLike,
    secret_key_file: PathLike,
    object_to_update: MutableMapping[str, Any],
    password_sep: str = '$'
) -> Dict[str, Dict[str, str]]:
    """
    performs settings update using passwords file and secret
    Args:
        passwords_file: path to yaml with encrypted variables/commands
        secret_key_file: path to secret file
        object_to_update: object to be updated using this file, usually locals()
        password_sep:

    Returns:

    """
    with get_lock(passwords_file, timeout=10):
        passwords_file = Path(passwords_file)
        if not passwords_file.exists():
            # print(f"Not found passwords file: {passwords_file}")
            return {}

        passwords = read_yaml(passwords_file)
        if not passwords:
            return {}
        
    from ..encryption.utils import load_secret
    secret_key = load_secret(secret_key_file)
    if not secret_key:
        return {}

    from ..encryption.encryptor import load_passwords

    try:
        # print(f"Reading passwords file: {passwords_file}")
        return load_passwords(
            passwords=passwords,
            config=object_to_update,
            secret_key=secret_key,
            sep=password_sep,
        )
    except Exception:
        from traceback import print_exc
        print_exc()
        return {}


def _decrypt_vars(
    dct: Dict[str, str],
    secret_key_file: Optional[PathLike] = None,
    password_sep: str = '$',
) -> Optional[Dict[str, str]]:
    if not dct:
        return
    if not secret_key_file:
        print('secret key file is not set but is required to parse some env variables')
        return

    from ..encryption.utils import load_secret
    secret_key = load_secret(secret_key_file)
    if not secret_key:
        return

    from ..encryption.encryptor import decrypt_password
    res = {}
    for k, v in dct.items():
        try:
            v = decrypt_password(v, secret_key=secret_key, sep=password_sep)[0]
            res[k] = v
        except Exception as e:
            print('\t' + e.args[0])

    return res


def load_vars_from_env(
    object_to_update: MutableMapping[str, Any],
    secret_key_file: Optional[PathLike] = None,
    password_sep: str = '$',
    prefix: str = 'TRANSLATE_'
):
    """
    updates object according to env variables rules with encrypted data allowed
    Args:
        object_to_update:
        secret_key_file:
        password_sep:
        prefix: prefix to select env variables to be used

    """

    # locals().update(
    #     parse_vars(
    #         prefix='DREAMOCR_',
    #         initial_vars=locals(),
    #         dict_level_separator='__'
    #     )
    # )

    source_vars = dict(os.environ)
    # filter by prefix
    source_vars = {
        k[len(prefix):]: v for k, v in source_vars.items()
        if k.startswith(prefix)
    }
    if not source_vars:
        return

    # suffix = '_ENCRYPTED'
    # encrypted_vars = {
    #     k[:-len(suffix)]: v for k, v in source_vars.items() if k.endswith(suffix)
    # }
    from ..encryption.encryptor import is_like_secret
    encrypted_vars = {
        k: v for k, v in source_vars.items() if is_like_secret(v)
    }
    if encrypted_vars:
        # remove all encrypted variables from source
        source_vars = {k: v for k, v in source_vars.items() if k not in encrypted_vars}

        print(f"Decrypt vars from environment...")
        decrypted_vars = _decrypt_vars(encrypted_vars, secret_key_file=secret_key_file, password_sep=password_sep)
        if decrypted_vars:
            source_vars.update(decrypted_vars)

    if source_vars:
        from env2dict import parse_vars
        object_to_update.update(
            parse_vars(
                prefix='',
                source=source_vars,
                initial_vars=object_to_update,
                dict_level_separator='__'
            )
        )


def save_settings_debug(settings: Mapping[str, Any]):
    """
    save all settings for debug only purposes
    
    saves them to settings.SAVE_SETTINGS_DEBUG if set
    """
    _s = settings.get("SAVE_SETTINGS_DEBUG", None)
    if _s:
        import json
        import inspect

        _d = {
            k: v
            for k, v in settings.items()
            if not (
                    k.startswith("__")
                    or len(k.strip("_")) < 2
                    or callable(v)
                    or inspect.ismodule(v)
                    or inspect.isclass(v)
            )
        }
        _d["environment"] = dict(os.environ.items())

        p = Path(_s)
        p.parent.mkdir(exist_ok=True, parents=True)
        p.write_text(
            json.dumps(
                _d, default=lambda o: "<not serializable>", indent=2, sort_keys=True
            ),
            encoding="utf-8",
        )
