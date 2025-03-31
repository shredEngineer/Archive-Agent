# Archive Agent

**Smart Indexer with [RAG](https://en.wikipedia.org/wiki/Retrieval-augmented_generation) Engine**

- OpenAI API for embeddings and queries
- Qdrant *(running locally)* for storage and search 

![Archive Agent Logo](archive_agent/assets/Archive-Agent-400x300.png)

**Archive Agent** tracks your files, syncs changes, and powers smart queries.  

---

## Install Requirements

- [Docker](https://docs.docker.com/engine/install/) *(for running Qdrant server)*
- [Python](https://www.python.org/downloads/) **>= 3.9** *(core runtime)*
- [Poetry](https://python-poetry.org/docs/#installation) *(dependency management)*


- **Tested with Ubuntu 24.04**

---

## Export OpenAI API key

To export your [OpenAI API key](https://platform.openai.com/api-keys), replace `sk-...` with your actual key and run this once:

```bash
echo "export OPENAI_API_KEY='sk-...'" >> ~/.bashrc && source ~/.bashrc
```

This will persist the export for the current user.

**NOTE:** Embeddings and queries will incur OpenAI API token costs. **Use at your own risk.**

---

## Install Archive Agent

To install **Archive Agent** in the current directory of your choice, run this once:

```bash
git clone https://github.com/shredEngineer/Archive-Agent
cd Archive-Agent
poetry install
chmod +x *.sh
echo "alias archive-agent='$(pwd)/archive-agent.sh'" >> ~/.bashrc && source ~/.bashrc
```

This will create a global `archive-agent` command for the current user.

---

## Setup Qdrant server

**IMPORTANT:** To manage Docker without root, run this once **and reboot**:

```bash
sudo usermod -aG docker $USER
```

To launch Qdrant with persistent storage and auto-restart, run this once:

```bash
./ensure-qdrant.sh
```

This will download the Qdrant docker image on the first run.

**NOTE:** In case you need to stop the Qdrant Docker image, run this:

```bash
docker stop archive-agent-qdrant-server
```

---

## Run Archive Agent

The default settings profile is created on the first run. (See [Storage](#storage) section.)

### How patterns work with Archive Agent

**Archive Agent** uses *patterns* to select your files:

- Patterns can be actual filenames.
- Patterns can be paths containing wildcards that resolve to actual filenames.
- Patterns must be specified as (or resolve to) *absolute* paths, e.g. `/home/user/Documents/*.txt` (or `~/Documents/*.txt`).
- Patterns may use the wildcard `**` to match any files and zero or more directories, subdirectories and symbolic links to directories.

There are *included patterns* and *excluded patterns*:

- The set of resolved excluded files is removed from the set of resolved included files.   
- Only the remaining set of files (included but not excluded) is tracked by **Archive Agent**. 

**NOTE:** Hidden files are always ignored.

### List usage info

To show the list of supported commands, run this:

```bash
archive-agent
```

### Add included patterns

To add one or more included patterns, run this:

```bash
archive-agent include ~/Documents/*.txt
```

### Add excluded patterns

To add one or more excluded patterns, run this:

```bash
archive-agent exclude "~/Documents/*.txt"
```

**NOTE:** Always enclose each pattern argument in quotes, preventing your shell from expanding them prematurely.

**NOTE:** To get an interactive prompt, skip the pattern argument.

### Remove included / excluded patterns

To remove one or more previously included / excluded patterns, run this:

```bash
archive-agent remove "~/Documents/*.txt"
```

**NOTE:** Always enclose each pattern argument in quotes, preventing your shell from expanding them prematurely.

**NOTE:** To get an interactive prompt, skip the pattern argument.

### List included / excluded patterns

To show the list of included / excluded patterns, run this: 

```bash
archive-agent patterns
```

### Resolve patterns and track files

To resolve all patterns and track changes to your files, run this:

```bash
archive-agent track
```

### List tracked files

To show the full list of tracked files, run this: 

```bash
archive-agent list
```

### List changed files

To show the list of changed files, run this: 

```bash
archive-agent diff
```

### Commit changed files to database

To sync changes to your files with the Qdrant database, run this:

```bash
archive-agent commit
```

**NOTE:** Changes are triggered by:

- File added
- File removed
- File changed:
  - Different file size
  - Different modification date

### Search your files

```bash
archive-agent search "Which files mention donuts?"
```

Lists files matching the question.

**NOTE:** To get an interactive prompt, skip the question argument.

### Query your files

```bash
archive-agent query "Which files mention donuts?"
```

Answers your question using RAG.

**NOTE:** To get an interactive prompt, skip the question argument.

---

## Storage

### Archive Agent settings

**Archive Agent** settings are stored in `~/.archive-agent-settings/`. 

The default settings profile is located in `default/`:

- `config.json`:
  - `openai_model_embed`: OpenAI model for embedding
  - `openai_model_query`: OpenAI model for query
  - `qdrant_collection`: Qdrant collection name
  - `qdrant_server_url`: Qdrant server URL


- `watchlist.json`:
  - Managed via the `include` / `exclude` / `remove` / `track` / `commit` commands.

### Qdrant database

The Qdrant database is stored in `~/.archive-agent-qdrant-storage/`.

**NOTE:** This folder is created by the Qdrant Docker image running as root.

Visit your [Qdrant dashboard](http://localhost:6333/dashboard#/collections) to manage collections and snapshots.

---

## TODO

**Archive Agent** is fully functional right now.

However, the following features could make it even better:

- [ ] Switch profiles (use folder other than `default/`)
- [ ] Save RAG answers to file (could also be indexed, enables feedback loop)

---

## License: GNU GPL v3.0

Copyright © 2025 Dr.-Ing. Paul Wilhelm <[paul@wilhelm.dev](mailto:paul@wilhelm.dev)>

```
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
```

See [LICENSE](LICENSE) for details.
