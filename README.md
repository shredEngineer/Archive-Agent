# Archive Agent

**Smart Indexer with [RAG](https://en.wikipedia.org/wiki/Retrieval-augmented_generation) Engine**

**Archive Agent** tracks your files, syncs changes, and powers smart queries.  

![Archive Agent Logo](archive_agent/assets/Archive-Agent-400x300.png)

---

## Tech Stack

- OpenAI API for embeddings and intelligence
- Qdrant *(running locally)* for storage and search 

## Supported OS

- Tested with Ubuntu 24.04

## Install Requirements

- [Docker](https://docs.docker.com/engine/install/) *(for running Qdrant container)*
- [Python](https://www.python.org/downloads/) **>= 3.9** *(core runtime)*
- [Poetry](https://python-poetry.org/docs/#installation) *(dependency management)*

---

## Export OpenAI API key

Run this once, replacing `sk-...` with your actual [OpenAI API key](https://platform.openai.com/api-keys):

```bash
echo "export OPENAI_API_KEY='sk-...'" >> ~/.bashrc && source ~/.bashrc
```

This will persist the export for the current user, so you don't have to execute it every time.

**NOTE:** Embeddings and queries will incur OpenAI API token costs. Use at your own risk.

---

## Install Archive Agent

Install **Archive Agent** wherever you choose, creating a global `archive-agent` command:

```bash
git clone https://github.com/shredEngineer/Archive-Agent
cd Archive-Agent
poetry install
chmod +x *.sh
echo "alias archive-agent='$(pwd)/archive-agent.sh'" >> ~/.bashrc && source ~/.bashrc
```

---

## Setup Qdrant

**IMPORTANT:** To manage Docker without root, run this once **and reboot**:

```bash
sudo usermod -aG docker $USER
```

Then launch Qdrant with persistent storage and auto-restart (downloads the image on the first run):

```bash
./ensure-qdrant.sh
```

To stop the Qdrant Docker image, run:

```bash
docker stop archive-agent-qdrant-server
```

---

## Run Archive Agent

Default settings are created on the first run. See *Storage* section below.

### Usage info

```bash
archive-agent
```

Displays usage info.

### Watch patterns

Specify one or more patterns to be watched:

```bash
archive-agent watch ~/Documents/*.txt
```

(Run `archive-agent commit` to apply changes.) 

### Unwatch patterns

Specify one or more patterns to be unwatched:

```bash
archive-agent unwatch ~/Documents/*.txt
```

(Run `archive-agent commit` to apply changes.)

### List watched patterns

```bash
archive-agent list
```

Displays watched and unwatched patterns.

### Commit files to database

```bash
archive-agent commit
```

Resolves patterns, detects changes, and syncs Qdrant database.

Changes are triggered by:
- File added
- File removed
- File size changed
- File date changed

### Search your files

```bash
archive-agent search "Which files mention donuts?"
```

Lists paths matching the question.

### Query your files

```bash
archive-agent query "Which files mention donuts?"
```

Answers your question using RAG.

---

## Storage

### Archive Agent settings

**Archive Agent** settings are stored in `~/.archive-agent-settings/`. 

- `config.json` can be customized if you know what you're doing.
- `watchlist.json` is managed via the `watch` / `unwatch` / `commit` commands.

### Qdrant database

Qdrant database is stored in `~/.archive-agent-qdrant-storage/`.

**NOTE:** This folder is created by the Qdrant Docker image running as root.

Visit your [Qdrant dashboard](http://localhost:6333/dashboard#/collections) to manage collections and snapshots.

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
