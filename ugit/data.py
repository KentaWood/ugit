import json
import os  # For file and directory manipulation
import hashlib  # For hashing file contents into SHA-1 hashes
from collections import namedtuple
from contextlib import contextmanager
import shutil
from typing import Iterator, Optional, Tuple, Union

# Define the directory that holds all Git-like internal data
GIT_DIR: Optional[str] = None  # Hidden folder where all version control data is stored

RefValue = namedtuple('RefValue', ['symbolic', 'value'])


@contextmanager
def change_git_dir(new_dir: str):
    global GIT_DIR

    old_dir = GIT_DIR
    GIT_DIR = f'{new_dir}/.ugit'
    yield
    GIT_DIR = old_dir


def init() -> None:
    os.makedirs(GIT_DIR)  # type: ignore
    os.makedirs(f'{GIT_DIR}/objects')  # type: ignore


def update_ref(ref: str, value: RefValue, deref: bool = True) -> None:
    ref = _get_ref_internal(ref, deref)[0]

    assert value.value
    content = f'ref: {value.value}' if value.symbolic else value.value

    ref_path = f'{GIT_DIR}/{ref}'
    os.makedirs(os.path.dirname(ref_path), exist_ok=True)
    with open(ref_path, 'w') as f:
        f.write(content)


def get_ref(ref: str, deref: bool = True) -> RefValue:
    return _get_ref_internal(ref, deref)[1]


def delete_ref(ref: str, deref: bool = True) -> None:
    refname = _get_ref_internal(ref, deref)[0]
    os.remove(f'{GIT_DIR}/{refname}')


def _get_ref_internal(ref: str, deref: bool) -> Tuple[str, RefValue]:
    ref_path = f'{GIT_DIR}/{ref}'
    value: Optional[str] = None

    if os.path.isfile(ref_path):
        with open(ref_path) as f:
            value = f.read().strip()

    symbolic = bool(value) and value.startswith('ref:')
    if symbolic:
        inner_ref = value.split(':', 1)[1].strip()
        if deref:
            return _get_ref_internal(inner_ref, deref=True)

    return ref, RefValue(symbolic=symbolic, value=value)


def iter_refs(prefix: str = '', deref: bool = True) -> Iterator[Tuple[str, RefValue]]:
    refs = ['HEAD', 'MERGE_HEAD']

    for root, _, filenames in os.walk(f'{GIT_DIR}/refs/'):
        root = os.path.relpath(root, GIT_DIR)
        refs.extend(f'{root}/{name}' for name in filenames)

    for refname in refs:
        if not refname.startswith(prefix):
            continue

        ref = get_ref(refname, deref=deref)
        if ref.value:
            yield refname, ref

@contextmanager
def get_index ():
    index = {}
    if os.path.isfile (f'{GIT_DIR}/index'):
        with open (f'{GIT_DIR}/index') as f:
            index = json.load (f)

    yield index

    with open (f'{GIT_DIR}/index', 'w') as f:
        json.dump (index, f)
        
def hash_object(data: bytes, type_: str = 'blob') -> str:
    obj = type_.encode() + b'\x00' + data
    oid = hashlib.sha1(obj).hexdigest()
    path = f'{GIT_DIR}/objects/{oid}'

    with open(path, 'wb') as out:
        out.write(obj)

    return oid


def get_object(oid: str, expected: Optional[str] = 'blob') -> bytes:
    path = f'{GIT_DIR}/objects/{oid}'

    with open(path, 'rb') as f:
        obj = f.read()

    type_, _, content = obj.partition(b'\x00')
    type_str = type_.decode()

    if expected is not None:
        assert type_str == expected, f'Expected {expected}, got {type_str}'

    return content


def object_exists(oid: str) -> bool:
    return os.path.exists(f'{GIT_DIR}/objects/{oid}')


def fetch_object_if_missing(oid: str, remote_git_dir: str) -> None:
    if object_exists(oid):
        return

    remote_git_dir += '/.ugit'

    shutil.copy(
        f'{remote_git_dir}/objects/{oid}',
        f'{GIT_DIR}/objects/{oid}'
    )


def push_object(oid: str, remote_git_dir: str) -> None:
    remote_git_dir += '/.ugit'

    shutil.copy(
        f'{GIT_DIR}/objects/{oid}',
        f'{remote_git_dir}/objects/{oid}'
    )
