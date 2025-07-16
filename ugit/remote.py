import os
from . import data
from . import base

REMOTE_REFS_BASE='refs/heads/'
LOCAL_REFS_BASE='refs/remote/'

# List the branch refs available in the remote repository (no actual data is fetched yet)
def fetch (remote_path):

    refs = _get_remote_refs(remote_path, REMOTE_REFS_BASE)
    
    for oid in base.iter_objects_in_commits(refs.values):
        data.fetch_object_if_missing(oid,remote_path)
    
    for remote_name, value in refs.items():
        refname = os.path.relpath(remote_name,REMOTE_REFS_BASE)
        data.update_ref(f'{LOCAL_REFS_BASE}/{refname}',
                        data.RefValue(symbolic=False,value=value)
                        )

# Temporarily switch to the remote .ugit directory and return all refs (e.g., branches) and their OIDs
def _get_remote_refs (remote_path, prefix=''):
    with data.change_git_dir (remote_path):
        return {refname: ref.value for refname, ref in data.iter_refs (prefix)}


def push (remote_path, refname):
    # Get refs data
    remote_refs = _get_remote_refs (remote_path)
    remote_ref = remote_refs.get(refname)
    
    local_ref = data.get_ref (refname).value
    
    
    assert local_ref
    
    
    assert not remote_refs or base.is_ancestor_of(local_ref, remote_refs)
    # Compute which objects the server doesn't have
    
    # Filter remote refs to only those whose objects already exist locally
    known_remote_refs = filter(data.object_exists, remote_refs.values())

    # Get all reachable objects (commits, trees, blobs) from the filtered remote refs
    remote_objects = set(base.iter_objects_in_commits(known_remote_refs))

    # Get all reachable objects from the local ref (e.g., local branch)
    local_objects = set(base.iter_objects_in_commits({local_ref}))

    # Determine which objects exist locally but not in the remote — these need to be pushed
    objects_to_push = local_objects - remote_objects


    # Push missing objects
    for oid in objects_to_push:
        data.push_object (oid, remote_path)

    # Update server ref to our value
    with data.change_git_dir (remote_path):
        data.update_ref (refname,
                         data.RefValue (symbolic=False, value=local_ref))