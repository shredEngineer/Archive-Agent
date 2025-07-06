[![Verified on MseeP](https://mseep.ai/badge.svg)](https://mseep.ai/app/499d8d83-02c8-4c9b-9e4f-8e8391395482)

🍀 **Collaborators welcome**  
You are invited to contribute to this open source project!  
Feel free to [file issues](https://github.com/shredEngineer/Archive-Agent/issues) and [submit pull requests](https://github.com/shredEngineer/Archive-Agent/pulls) anytime.

---

# 🧠 Archive Agent

**Archive Agent** is an open-source semantic file tracker with OCR + AI search.  

- **Smart Indexer with [RAG](https://en.wikipedia.org/wiki/Retrieval-augmented_generation) Engine**
- **Supported AI providers: [OpenAI](https://platform.openai.com/docs/overview), [Ollama](https://ollama.com/), [LM Studio](https://lmstudio.ai/)**
- **[MCP](https://modelcontextprotocol.io/introduction) server for automation through IDE or AI extension**
- Fast and effective semantic chunking (**smart chunking**)
- [Qdrant](https://qdrant.tech/) vector DB *(running locally)* for storage and search 

![Archive Agent Logo](archive_agent/assets/Archive-Agent-400x300.png)

---

🤓 **[Watch me explain this on YouTube](https://www.youtube.com/watch?v=dyKovjez4-g)**

**Want to know the nitty-gritty details? 👉 [How Archive Agent works](#how-archive-agent-works)**

**Looking for the CLI command reference? 👉 [Run Archive Agent](#run-archive-agent)**

**Looking for the MCP tool reference? 👉 [MCP Tools](#mcp-tools)**

**Want to upgrade for the latest features? 👉 [Update Archive Agent](#update-archive-agent)**

---

📷 Screenshot of **command-line** interface (CLI) using *Typer*:

![](archive_agent/assets/Screenshot-CLI.png)

📷 Screenshot of **graphical** user interface (GUI) using *Streamlit*:
[(enlarge)](archive_agent/assets/Screenshot-GUI.png)

![](archive_agent/assets/Screenshot-GUI.png)

## Structure

<!-- TOC -->
* [🧠 Archive Agent](#-archive-agent)
  * [Structure](#structure)
  * [Supported OS](#supported-os)
  * [Install requirements](#install-requirements)
  * [Install Archive Agent on Linux](#install-archive-agent-on-linux)
  * [AI provider setup](#ai-provider-setup)
    * [OpenAI provider setup](#openai-provider-setup)
    * [Ollama provider setup](#ollama-provider-setup)
    * [LM Studio provider setup](#lm-studio-provider-setup)
  * [How Archive Agent works](#how-archive-agent-works)
    * [Which files are processed](#which-files-are-processed)
    * [How files are processed](#how-files-are-processed)
    * [How smart chunking works](#how-smart-chunking-works)
    * [How chunks are retrieved](#how-chunks-are-retrieved)
    * [How files are selected for tracking](#how-files-are-selected-for-tracking)
  * [Run Archive Agent](#run-archive-agent)
    * [Show list of commands](#show-list-of-commands)
    * [Create or switch profile](#create-or-switch-profile)
    * [Open current profile config in nano](#open-current-profile-config-in-nano)
    * [Add included patterns](#add-included-patterns)
    * [Add excluded patterns](#add-excluded-patterns)
    * [Remove included / excluded patterns](#remove-included--excluded-patterns)
    * [List included / excluded patterns](#list-included--excluded-patterns)
    * [Resolve patterns and track files](#resolve-patterns-and-track-files)
    * [List tracked files](#list-tracked-files)
    * [List changed files](#list-changed-files)
    * [Commit changed files to database](#commit-changed-files-to-database)
    * [Combined track and commit](#combined-track-and-commit)
    * [Search your files](#search-your-files)
    * [Query your files](#query-your-files)
    * [Launch Archive Agent GUI](#launch-archive-agent-gui)
    * [Start MCP Server](#start-mcp-server)
  * [MCP Tools](#mcp-tools)
  * [Update Archive Agent](#update-archive-agent)
  * [Archive Agent settings](#archive-agent-settings)
  * [Qdrant database](#qdrant-database)
  * [Developer's guide](#developers-guide)
    * [Important modules](#important-modules)
    * [Testing and code analysis](#testing-and-code-analysis)
    * [PDF image debugger window](#pdf-image-debugger-window)
  * [Known bugs](#known-bugs)
  * [Licensed under GNU GPL v3.0](#licensed-under-gnu-gpl-v30)
<!-- TOC -->

---

## Supported OS

**Archive Agent** has been tested with these configurations:

- **Ubuntu 24.04** (PC x64)
- **macOS 15 Sequoia** (MacBook Air M1) with Rosetta, **experimental**: [Install Archive Agent on macOS](macos.md)

If you're using **Archive Agent** with another setup, please let me know and I'll add it here! 

---

## Install requirements

Please install these requirements first: 

- [Docker](https://docs.docker.com/engine/install/) *(for running Qdrant server)*
- [Python](https://www.python.org/downloads/) **>= 3.10, < 3.13** *(core runtime)*
- [Poetry](https://python-poetry.org/docs/#installation) *(dependency management)*

---

## Install Archive Agent on Linux

This should work on any Linux distribution derived from Ubuntu (e.g. Linux Mint). 

To install **Archive Agent** in the current directory of your choice, run this once:

```bash
git clone https://github.com/shredEngineer/Archive-Agent
cd Archive-Agent
chmod +x install.sh
./install.sh
```

This will download the Qdrant docker image and launch it with persistent storage and auto-restart.

This will create a global `archive-agent` command for the current user.

🚀 **Archive Agent is now installed!** Please complete the [AI provider setup](#ai-provider-setup) next.
Afterward, you're ready to [Run Archive Agent](#run-archive-agent).

---

## AI provider setup

**Archive Agent** lets you choose between different AI providers:

- Remote APIs *(higher performance and costs, less privacy)*:
  - **OpenAI**: Requires an OpenAI API key.


- Local APIs *(lower performance and costs, best privacy)*:
  - **Ollama**: Requires Ollama running locally.
  - **LM Studio**: Requires LM Studio running locally.

💡 **Good to know:** You will be prompted to choose an AI provider at startup; see: [Run Archive Agent](#run-archive-agent).

📌 **Note:** You *can* customize the specific **models** used by the AI provider in the [Archive Agent settings](#archive-agent-settings). However, you *cannot* change the AI provider of an *existing* profile, as the embeddings will be incompatible; to choose a different AI provider, create a new profile instead.

### OpenAI provider setup

If the OpenAI provider is selected, **Archive Agent** requires the OpenAI API key.

To export your [OpenAI API key](https://platform.openai.com/api-keys), replace `sk-...` with your actual key and run this once:

```bash
echo "export OPENAI_API_KEY='sk-...'" >> ~/.bashrc && source ~/.bashrc
```

This will persist the export for the current user.

💡 **Good to know:** [OpenAI won't use your data for training.](https://platform.openai.com/docs/guides/your-data)

### Ollama provider setup

If the Ollama provider is selected, **Archive Agent** requires Ollama running at `http://localhost:11434`.

- [How to install Ollama.](https://ollama.com/download)

With the default [Archive Agent Settings](#archive-agent-settings), these Ollama models are expected to be installed: 

```bash
ollama pull llama3.1:8b             # for chunk/query
ollama pull llava:7b-v1.6           # for vision
ollama pull nomic-embed-text:v1.5   # for embed
```

💡 **Good to know:** Ollama also works without a GPU.
At least 32 GiB RAM is recommended for smooth performance.

### LM Studio provider setup

If the LM Studio provider is selected, **Archive Agent** requires LM Studio running at `http://localhost:1234`.

- [How to install LM Studio.](https://lmstudio.ai/download)

With the default [Archive Agent Settings](#archive-agent-settings), these LM Studio models are expected to be installed: 

```bash
meta-llama-3.1-8b-instruct              # for chunk/query
llava-v1.5-7b                           # for vision
text-embedding-nomic-embed-text-v1.5    # for embed
```

💡 **Good to know:** LM Studio also works without a GPU.
At least 32 GiB RAM is recommended for smooth performance.

---

## How Archive Agent works

###  Which files are processed

**Archive Agent** currently supports these file types:
- Text:
  - Plaintext: `.txt`, `.md`
  - Documents:
    - ASCII documents: `.html`, `.htm`
    - Binary documents: `.odt`, `.docx` (including images)
  - PDF documents: `.pdf` (including images, see note below)
- Images: `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`, `.bmp`

📌 **Note:** There are different OCR strategies supported by **Archive Agent**:

- **Strict** OCR strategy:
  - PDF OCR text layer is *ignored*.
  - PDF pages are treated as images.
  - **Expensive and slow, but more accurate.**

- **Relaxed** OCR strategy:
  - PDF OCR text layer is extracted.
  - PDF foreground images are decoded, but background images are *ignored*.
  - **Cheap and fast, but less accurate.**

💡 **Good to know:** You will be prompted to choose an OCR strategy at startup; see: [Run Archive Agent](#run-archive-agent).

### How files are processed

Ultimately, **Archive Agent** decodes everything to text like this:
- Plaintext files are decoded to UTF-8.
- Documents are converted to plaintext, images are extracted.
- PDF documents are decoded according to the OCR strategy.
- Images are decoded to text using AI vision.
  - The vision model will reject unintelligible images.

Using *Pandoc* for documents, *PyMuPDF4LLM* for PDFs, *Pillow* for images.

📌 **Note:** Unsupported files are tracked but not processed.

### How smart chunking works

**Archive Agent** processes decoded text like this:
- Decoded text is sanitized and split into sentences.
- Sentences are grouped into reasonably-sized blocks.
- **Each block is split into smaller chunks using an AI model.**
  - Block boundaries are handled gracefully (last chunk carries over).
- Each chunk is turned into a vector using AI embeddings.
- Each vector is turned into a *point* with file metadata.
- Each *point* is stored in the Qdrant database.

💡 **Good to know:** This **smart chunking** improves the accuracy and effectiveness of the retrieval. 

### How chunks are retrieved

**Archive Agent** retrieves chunks related to your question like this:
- The question is turned into a vector using AI embeddings.
- Points with similar vectors are retrieved from the Qdrant database.
- Chunks of points with sufficient score are returned.

**Archive Agent** answers your question using retrieved chunks like this:
- The LLM receives the retrieved chunks as context to the question.
- The LLM's answer is returned and formatted.

The LLM's answer is structured to be multi-faceted, making **Archive Agent** a helpful assistant.

### How files are selected for tracking

**Archive Agent** uses *patterns* to select your files:

- Patterns can be actual file paths.
- Patterns can be paths containing wildcards that resolve to actual file paths.
- Patterns must be specified as (or resolve to) *absolute* paths, e.g. `/home/user/Documents/*.txt` (or `~/Documents/*.txt`).
- Patterns may use the wildcard `**` to match any files and zero or more directories, subdirectories, and symbolic links to directories.

There are *included patterns* and *excluded patterns*:

- The set of resolved excluded files is removed from the set of resolved included files.
- Only the remaining set of files (included but not excluded) is tracked by **Archive Agent**. 
- Hidden files are always ignored!

This approach gives you the best control over the specific files or file types to track.

---

## Run Archive Agent

### Show list of commands

To show the list of supported commands, run this:

```bash
archive-agent
```

### Create or switch profile

To switch to a new or existing profile, run this:

```bash
archive-agent switch "My Other Profile"
```

📌 **Note:** **Always use quotes** for the profile name argument,
**or skip it** to get an interactive prompt.

💡 **Good to know:** Profiles are useful to manage *independent* Qdrant collections and [Archive Agent settings](#archive-agent-settings).

### Open current profile config in nano

To open the current profile's config (JSON) in the `nano` editor, run this:

```bash
archive-agent config
```

See [Archive Agent settings](#archive-agent-settings) for details.

### Add included patterns

To add one or more included patterns, run this:

```bash
archive-agent include "~/Documents/*.txt"
```

📌 **Note:** **Always use quotes** for the pattern argument (to prevent your shell's wildcard expansion),
**or skip it** to get an interactive prompt.

### Add excluded patterns

To add one or more excluded patterns, run this:

```bash
archive-agent exclude "~/Documents/*.txt"
```

📌 **Note:** **Always use quotes** for the pattern argument (to prevent your shell's wildcard expansion),
**or skip it** to get an interactive prompt.

### Remove included / excluded patterns

To remove one or more previously included / excluded patterns, run this:

```bash
archive-agent remove "~/Documents/*.txt"
```

📌 **Note:** **Always use quotes** for the pattern argument (to prevent your shell's wildcard expansion),
**or skip it** to get an interactive prompt.

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

To show the list of tracked files, run this: 

```bash
archive-agent list
```

📌 **Note:** Don't forget to `track` your files first.

### List changed files

To show the list of changed files, run this: 

```bash
archive-agent diff
```

📌 **Note:** Don't forget to `track` your files first.

### Commit changed files to database

To sync changes to your files with the Qdrant database, run this:

```bash
archive-agent commit
```

💡 **Good to know:** Changes are triggered by:
- File added
- File removed
- File changed:
  - Different file size
  - Different modification date

📌 **Note:** Don't forget to `track` your files first.

### Combined track and commit

To `track` and then `commit` in one go, run this:

```bash
archive-agent update
```

### Search your files

```bash
archive-agent search "Which files mention donuts?"
```

Lists files relevant to the question.

📌 **Note:** **Always use quotes** for the question argument, **or skip it** to get an interactive prompt.

### Query your files

```bash
archive-agent query "Which files mention donuts?"
```

Answers your question using RAG.

📌 **Note:** **Always use quotes** for the question argument, **or skip it** to get an interactive prompt.

### Launch Archive Agent GUI

To launch the **Archive Agent** GUI in your browser, run this:

```bash
archive-agent gui
```

📌 **Note:** Press `CTRL+C` in the console to close the GUI server.

### Start MCP Server

To start the **Archive Agent** MCP server, run this:

```bash
archive-agent mcp
```

📌 **Note:** Press `CTRL+C` in the console to close the MCP server.

💡 **Good to know:** Use these MCP configurations to let your IDE or AI extension automate **Archive Agent**:

- [`.vscode/mcp.json`](.vscode/mcp.json) for [GitHub Copilot agent mode (VS Code)](https://code.visualstudio.com/blogs/2025/02/24/introducing-copilot-agent-mode): 
- [`.roo/mcp.json`](.roo/mcp.json) for [Roo Code (VS Code extension)](https://marketplace.visualstudio.com/items?itemName=RooVeterinaryInc.roo-cline)

---

## MCP Tools

**Archive Agent** exposes these tools via MCP:

| MCP tool            | Equivalent CLI command(s) | Argument(s) | Description                                     |
|---------------------|---------------------------|-------------|-------------------------------------------------|
| `get_patterns`      | `patterns`                | None        | Get the list of included / excluded patterns.   |
| `get_files_tracked` | `track` and then `list`   | None        | Get the list of tracked files.                  |
| `get_files_changed` | `track` and then `diff`   | None        | Get the list of changed files.                  |
| `get_search_result` | `search`                  | `question`  | Get the list of files relevant to the question. |
| `get_answer_rag`    | `query`                   | `question`  | Get answer to question using RAG.               |

📌 **Note:** These commands are **read-only**, preventing the AI from changing your Qdrant database.

💡 **Good to know:** Just type `#get_answer_rag` (e.g.) in your IDE or AI extension to call the tool directly.

---

## Update Archive Agent

This step is not needed right away if you just installed Archive Agent.
However, to get the latest features, you should update your installation regularly.

To update your **Archive Agent** installation, run this in the installation directory:

```bash
git pull
poetry install
```

📌 **Note:** If updating doesn't work, try removing the installation directory and installing **Archive Agent** again.
Your config and data are safely stored in another place;
see [Archive Agent settings](#archive-agent-settings) and [Qdrant database](#qdrant-database) for details.

💡 **Good to know:** To also update the Qdrant docker image, run this:

```bash
sudo ./manage-qdrant.sh update
```

---

## Archive Agent settings

**Archive Agent** settings are organized as profile folders in `~/.archive-agent-settings/`.

E.g., the `default` profile is located in `~/.archive-agent-settings/default/`.

The currently used profile is stored in `~/.archive-agent-settings/profile.json`.

Each profile folder contains these files:

- `config.json`:

  | Key                    | Description                                                                                   |
  |------------------------|-----------------------------------------------------------------------------------------------|
  | `config_version`       | Config version                                                                                |
  | `ocr_strategy`         | OCR strategy in [`DecoderSettings.py`](archive_agent/config/DecoderSettings.py)               |
  | `ai_provider`          | AI provider in [`ai_provider_registry.py`](archive_agent/ai_provider/ai_provider_registry.py) |
  | `ai_server_url`        | AI server URL                                                                                 |
  | `ai_model_chunk`       | AI model used for chunking                                                                    |
  | `ai_model_embed`       | AI model used for embedding                                                                   |
  | `ai_model_query`       | AI model used for queries                                                                     |
  | `ai_model_vision`      | AI model used for vision (`""` disables vision)                                               |
  | `ai_vector_size`       | Vector size of embeddings (used for Qdrant collection)                                        |
  | `ai_temperature_query` | Temperature of the query model                                                                |
  | `qdrant_server_url`    | URL of the Qdrant server                                                                      |
  | `qdrant_collection`    | Name of the Qdrant collection                                                                 |
  | `qdrant_score_min`     | Minimum similarity score of retrieved chunks (`0`...`1`)                                      |
  | `qdrant_chunks_max`    | Maximum number of retrieved chunks                                                            |
  | `chunk_lines_block`    | Number of lines per block for chunking                                                        |
  | `mcp_server_port`      | MCP server port (default `8008`)                                                              |

💡 **Good to know:** Use the `config` CLI command to open the current profile's config (JSON) in the `nano` editor.

- `watchlist.json`:
  - Managed via the `include` / `exclude` / `remove` / `track` / `commit` / `update` commands.

📌 **Note:** To delete a profile, simply delete the folder. This will not delete the Qdrant collection.

---

## Qdrant database

The Qdrant database is stored in `~/.archive-agent-qdrant-storage/`.

📌 **Note:** This folder is created by the Qdrant Docker image running as root.

💡 **Good to know:** Visit your [Qdrant dashboard](http://localhost:6333/dashboard#/collections) to manage collections and snapshots.

---

## Developer's guide

**Archive Agent** was written from scratch for educational purposes (on either end of the software).

### Important modules

To get started, check out these epic modules:

- The app context is initialized in [`archive_agent/core/ContextManager.py`](archive_agent/core/ContextManager.py)
- The default config is defined in [`archive_agent/config/ConfigManager.py`](archive_agent/config/ConfigManager.py)  
- The CLI commands are defined in [`archive_agent/__main__.py`](archive_agent/__main__.py)
- The commit logic is implemented in [`archive_agent/core/CommitManager.py`](archive_agent/core/CommitManager.py)
- The CLI verbosity can be adjusted in [`archive_agent/util/CliManager.py`](archive_agent/util/CliManager.py)
- The GUI is implemented in [`archive_agent/core/GuiManager.py`](archive_agent/core/GuiManager.py)
- The AI API prompts for chunking, embedding, vision, and querying are defined in [`archive_agent/ai/AiManager.py`](archive_agent/ai/AiManager.py) 
- The AI provider registry is located in [`archive_agent/ai_provider/ai_provider_registry.py`](archive_agent/ai_provider/ai_provider_registry.py)

If you miss something or spot bad patterns, feel free to contribute and refactor!

### Testing and code analysis

To run unit tests, check types, and check style, run this:

```bash
./audit.sh
```

(Some remaining type errors need to be fixed…)

### PDF image debugger window

To enable the PDF image debugger window, run this in your current shell:
```bash
export ARCHIVE_AGENT_IMAGE_DEBUGGER=1
```

📌 **Note:** PDF image debugger windows must be closed manually in order to proceed.

---

## Known bugs

- [ ] While `track` initially reports a file as *added*, subsequent `track` calls report it as *changed*. 


- [ ] Removing and restoring a tracked file in the tracking phase is currently not handled properly:
  - Removing a tracked file sets `{size=0, mtime=0, diff=removed}`.
  - Restoring a tracked file sets `{size=X, mtime=Y, diff=added}`.
  - Because `size` and `mtime` were cleared, we lost the information to detect a restored file.

---

## Licensed under GNU GPL v3.0

Copyright © 2025 Dr.-Ing. Paul Wilhelm <[paul@wilhelm.dev](mailto:paul@wilhelm.dev)>

```
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
```

See [LICENSE](LICENSE) for details.
