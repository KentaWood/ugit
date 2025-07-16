import os  # File and directory handling
import itertools  # Useful tools for iterating, like takewhile
import operator  # Functional equivalents of Python operators (e.g., truth)
from collections import deque, namedtuple  # Lightweight class for storing commit data
from . import data  # Custom module for low-level object database (blobs, trees, commits)
from . import diff
import string

def init():
    data.init()
    data.update_ref('HEAD',data.RefValue(symbolic=True,value='refs/heads/master'))


def write_tree():
    # Convert flat index (filename → oid) into a nested tree-like structure
    index_as_tree = {}

    with data.get_index() as index:
        for path, oid in index.items():
            # Split file path into directories and filename
            path = path.split('/')
            dirpath, filename = path[:-1], path[-1]

            current = index_as_tree
            # Traverse or create intermediate directories
            for dirname in dirpath:
                current = current.setdefault(dirname, {})  # Create sub-dict if missing
            
            # Assign file (blob) oid at the correct location
            current[filename] = oid

    # Recursively write tree objects for each directory
    def write_tree_recursive(tree_dict):
        entries = []

        for name, value in tree_dict.items():
            if type(value) is dict:
                # It's a directory → write subtree
                type_ = 'tree'
                oid = write_tree_recursive(value)
            else:
                # It's a file → use blob oid
                type_ = 'blob'
                oid = value

            entries.append((name, oid, type_))

        # Format entries and write to object database as a 'tree'
        tree = ''.join(
            f'{type_} {oid} {name}\n'
            for name, oid, type_ in sorted(entries)
        )

        return data.hash_object(tree.encode(), 'tree')

    # Start writing from the root of the index tree
    return write_tree_recursive(index_as_tree)


# Generator that yields each entry from a tree object
def _iter_tree_entries(oid):
    if not oid:
        return  # Return nothing if OID is invalid

    tree = data.get_object(oid, 'tree')  # Read tree object from the database
    for entry in tree.decode().splitlines():  # Split into lines like: "blob <oid> <name>"
        type_, oid, name = entry.split(' ', 2)
        yield type_, oid, name

# Returns a dictionary of all blobs under a tree: {path: oid}
def get_tree(oid, base_path=''):
    # print(f'get_tree called with oid: {oid}')
    results = {}

    for type_, oid2, name in _iter_tree_entries(oid):
        # print(f'tree entry: {type_}, {oid2}, {name}')
        assert '/' not in name  # Names should not contain slashes
        assert name not in ('..', '.')  # Skip special directories

        path = base_path + name  # Build relative path from root

        if type_ == 'blob':
            results[path] = oid2  # Record the file and its oid
        elif type_ == 'tree':
            results.update(get_tree(oid2, f'{path}/'))  # Recurse for nested tree
        else:
            assert False, f'Unknown tree entry {type_}'  # Should never happen

    # print(f'get_tree results: {results}')
    return results

def get_working_tree():
    
    result = {}
    
    for root, _, filenames in os.walk('.'):
        for filename in filenames:
            path = os.path.relpath(f'{root}/{filename}')
        
        if is_ignored(path) and not os.path.isfile(path):
            continue
        with open(path, 'rb') as f:
            result[path] = data.hash_object(f.read())
            
    return result


def get_index_tree ():
    with data.get_index () as index:
        return index

            

# Deletes everything in the current directory except .ugit
def _empty_current_directory():
    for root, dirnames, filenames in os.walk('.', topdown=False):  # Bottom-up traversal
        for filename in filenames:
            path = os.path.relpath(f'{root}/{filename}')  # Relative path for consistency
            if is_ignored(path) or not os.path.isfile(path):
                continue
            os.remove(path)

        for dirname in dirnames:
            path = os.path.relpath(f'{root}/{dirname}')
            if is_ignored(path):
                continue
            try:
                os.rmdir(path)  # Only removes empty dirs
            except (FileNotFoundError, OSError):
                pass  # Directory might not be empty


def read_tree (tree_oid, update_working=False):
    with data.get_index () as index:
        index.clear ()
        index.update (get_tree (tree_oid))

        if update_working:
            _checkout_index (index)


def read_tree_merged(t_base, t_HEAD, t_other, update_working=False):
    with data.get_index() as index:
        index.clear()  # Clear the current index

        # Merge the three trees and update the index with the result
        index.update(diff.merge_trees(
            get_tree(t_base),   # common ancestor
            get_tree(t_HEAD),   # current branch
            get_tree(t_other)   # other branch to merge in
        ))

        # If requested, apply the merged index to the working directory
        if update_working:
            _checkout_index(index)


def _checkout_index(index):
    _empty_current_directory()  # Remove all files and dirs (except .ugit)

    for path, oid in index.items():
        # Make sure parent directories exist
        os.makedirs(os.path.dirname(f'./{path}'), exist_ok=True)

        # Write the file content from the object database
        with open(path, 'wb') as f:
            f.write(data.get_object(oid, 'blob'))

# Create and store a new commit with optional parent
def commit(message):
    commit = f'tree {write_tree()}\n'  # First line: tree reference

    
    HEAD = data.get_ref('HEAD').value
    
    if HEAD:
        commit += f'parent {HEAD}\n'  # If a previous commit exists, add as parent
        
    MERGE_HEAD = data.get_ref('MERGE_HEAD').value
    if MERGE_HEAD:
        commit += f'parent {MERGE_HEAD}\n'
        data.delete_ref(MERGE_HEAD,deref=False)
    

    commit += '\n'  # Empty line before message
    commit += f'{message}\n'  # Commit message

    oid = data.hash_object(commit.encode(), 'commit')  # Store commit in database
    data.update_ref( 'HEAD', data.RefValue(symbolic=False, value=oid))  # Update HEAD to point to new commit

    return oid  # Return the commit's OID

# Checkout a specific commit: update files and HEAD
def checkout(name):
    
    oid = get_oid(name)
    
    commit = get_commit(oid)  # Get parsed commit object
    read_tree(commit.tree)  # Restore its tree into the working directory
    
    if is_branch(name):
        HEAD = data.RefValue(symbolic=True, value=f'refs/heads/{name}')
    else:
        HEAD = data.RefValue(symbolic=False,  value=oid)
    
    data.update_ref('HEAD',HEAD,deref=False)

def iter_branch_names():
    
    for refname, _ in data.iter_refs('refs/heads/'):
        yield os.path.relpath(refname, 'refs/heads/')
    
        

def is_branch(branch):
    return data.get_ref(f'refs/heads/{branch}').value is not None


def merge (other):
    HEAD = data.get_ref('HEAD').value
    assert HEAD
    
    merge_base = get_merge_base(other, HEAD)
    
    
    
    c_other = get_commit (other)
    
    if merge_base == HEAD:
        read_tree(c_other.tree)
        data.update_ref('HEAD',
                        data.RefValue(symbolic=False, value=other)
                        )
        print('Fast-forward merge, no need to commit')
        return 

    data.update_ref('MERGE_HEAD', data.RefValue(symbolic=False,value=other)
                    
                    )
    
    c_HEAD = get_commit(HEAD)
    c_base = get_commit(merge_base)
    
    read_tree_merged (c_HEAD.tree, c_base.tree,c_other.tree)
    print ('Merged in working tree\nPlease commit')

def get_merge_base(oid1, oid2):
    parents1 = set(iter_commits_and_parents({oid1}))
    
    for oid in iter_commits_and_parents({oid2}):
        
        if oid in parents1:
            return oid
        

def is_ancestor_of(commit, maybe_ancestor):
    return maybe_ancestor in iter_commits_and_parents(commit)

# Placeholder for tagging functionality (not yet implemented)
def create_tag(name, oid):
    
    data.update_ref(f'refs/tags/{name}',data.RefValue(symbolic=False, value=oid))

def reset(oid):
    data.update_ref('HEAD',data.RefValue(symbolic=False, value=oid))
    
    
    

def create_branch(name, oid):

    data.update_ref(f'refs/heads/{name}',data.RefValue(symbolic=False,value=oid))

def get_branch_name(): 
    
    HEAD = data.get_ref('HEAD', deref=False)
    
    if not HEAD.symbolic:
        # print('here')
        return None
    
    HEAD = HEAD.value
    assert HEAD.startswith('refs/heads')
    return os.path.relpath(HEAD,'refs/heads')


# Named tuple to represent parsed commit data
Commit = namedtuple('Commit', ['tree', 'parents', 'message'])



# Parse a commit object into tree, parent, and message
def get_commit(oid):
    parents = []  # Default parent
    # tree = None  # Default tree

    commit = data.get_object(oid, 'commit').decode()  # Load and decode commit
    lines = iter(commit.splitlines())  # Make iterable for line-by-line reading

    for line in itertools.takewhile(operator.truth, lines):  # Read until first blank line
        key, val = line.split(' ', 1)
        if key == 'tree':
            tree = val
        elif key == 'parent':
            parents.append(val)
        else:
            assert False, f'Unkown field {key}'  # Error for unexpected fields

    message = '\n'.join(lines)  # Remaining lines are the commit message
    return Commit(tree=tree, parents=parents, message=message)  # Return structured result

def iter_commits_and_parents(oids):
    
    oids = deque(oids)
    visited = set()
    
    while oids:
        
        oid = oids.popleft()
        
        if not oid or oid in visited:
            continue
        
        yield oid
        
        commit = get_commit(oid)
        oids.extendleft(commit.parents[:1])
        oids.extend(commit.parents[1:])

def iter_objects_in_commits (oids):
    # N.B. Must yield the oid before acccessing it (to allow caller to fetch it
    # if needed)

    visited = set ()
    def iter_objects_in_tree (oid):
        visited.add (oid)
        yield oid
        for type_, oid, _ in _iter_tree_entries (oid):
            if oid not in visited:
                if type_ == 'tree':
                    yield from iter_objects_in_tree (oid)
                else:
                    visited.add (oid)
                    yield oid

    for oid in iter_commits_and_parents (oids):
        yield oid
        commit = get_commit (oid)
        if commit.tree not in visited:
            yield from iter_objects_in_tree (commit.tree)


def get_oid(name):
    # return data.get_ref(name) or name
     
    # SAME AS BELOW
    # if name == '@':
    #     name = 'HEAD'
    
    if name == '@' : name = 'HEAD'
    
    refs_to_try= [
        f'{name}',
        f'refs/{name}',
        f'refs/tags/{name}',
        f'refs/heads/{name}',
        
        
    ]
    
    for ref in refs_to_try:
        
        # redudant to make two calls of function
        if data.get_ref(ref, deref=False).value:
            return data.get_ref(ref).value
        
            
    
    is_hex = all(c in string.hexdigits for c in name)
    
    if len(name) == 40 and is_hex:
        return name
    
    assert False, f'Unknown name: {name}'
    
    
def add (filenames):

    def add_file (filename):
        # Normalize path
        
        filename = os.path.relpath (filename)
        with open (filename, 'rb') as f:
            oid = data.hash_object (f.read ())
        
        index[filename] = oid

    def add_directory (dirname):
        for root, _, filenames in os.walk (dirname):
            
            for filename in filenames:
                # Normalize path
               
                path = os.path.relpath (f'{root}/{filename}')
                if is_ignored (path) or not os.path.isfile (path):
                    continue
                
                add_file (path)

    with data.get_index () as index:
        for name in filenames:
            
            if os.path.isfile (name):
                add_file (name)
            
            elif os.path.isdir (name):
                add_directory (name)

# Returns True if the path is inside .ugit (ignored from version control)
def is_ignored(path):
    return '.ugit' in path.split('/')

