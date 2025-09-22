# ugit

A lightweight, educational implementation of a Git-like version control system written in Python.
This project re-creates core Git concepts — objects, commits, branches, merges, diffs, and remotes — in a simplified way to make the internals of Git easier to understand.

---

## Features

* **Repository Initialization** (`ugit init`)
  Creates a `.ugit` directory with storage for objects and references.

* **Object Storage** (`hash-object`, `cat-file`)
  Store files as hashed objects and retrieve them.

* **Tree & Index Management** (`write-tree`, `read-tree`)
  Capture the state of the working directory as tree objects and restore them later.

* **Committing & Logging** (`commit`, `log`, `show`)
  Save snapshots of your project and browse history.

* **Branches & Tags** (`branch`, `checkout`, `tag`)
  Manage multiple lines of development.

* **Diffs** (`diff`, `status`)
  Compare working tree, index, and commit trees using `diff`.

* **Merging** (`merge`, `merge-base`)
  Perform three-way merges with conflict markers using `diff3`.

* **Remotes** (`fetch`, `push`)
  Synchronize objects and references between repositories.

* **Graph Visualization** (`ugit k`)
  Generate commit graphs as PNGs using Graphviz.

---

## Installation

```bash
git clone <this-repo>
cd <this-repo>
pip install .
```

This will install the `ugit` CLI command via the entry point defined in `setup.py`.

---

## Usage

After installation, you can use `ugit` just like Git:

```bash
# Initialize repository
ugit init

# Add files and commit
ugit add file1.py file2.py
ugit commit -m "Initial commit"

# View history
ugit log

# Create a branch
ugit branch feature-x
ugit checkout feature-x

# Show status
ugit status

# Diff changes
ugit diff

# Merge a branch
ugit merge master
ugit commit -m "Merge master into feature-x"

# Work with remotes
ugit fetch ../path/to/other/repo
ugit push ../path/to/other/repo branch-name

# Visualize commits
ugit k
```

---

## Project Structure

```
ugit/
│── cli.py      # CLI entry point, argument parsing, command mapping
│── base.py     # Core Git-like operations (commit, checkout, merge, branch)
│── data.py     # Object database and references (HEAD, refs, index)
│── diff.py     # File/tree diffing and merging
│── remote.py   # Fetch and push support
│── __init__.py
setup.py         # Packaging and installation config
```

---

## Requirements

* Python 3.8+
* `graphviz` (for `ugit k` visualization)
* Unix tools: `diff`, `diff3` (for file diffs and merges)

---

## Credits

This project is based on **[Nikita Leshenko’s “Build Your Own Git” guide](https://www.leshenko.net/p/ugit/)**, which walks through creating a minimal version-control system from scratch in Python.
My implementation follows and extends concepts from that guide.

MIT License. See [LICENSE](LICENSE) for details.

---

Would you like me to **add a "Learning Notes" section** where you can highlight what you personally learned while building this (like trees, commits, branching, merges), so the README doubles as a portfolio piece for recruiters?
