# 🧠 ArchiveAgent: Minimalist RAG Engine with Qdrant + OpenAI

> One file. One diff. One step closer to memory.

---

## 🚀 What It Does

- 🔍 Takes a `.md` file path as input
- 🧠 Embeds its content via OpenAI
- 💾 Stores vector and metadata in **local Qdrant**
- 📦 Tracks file changes using content hash
- 🧾 Ideal for diff-based RAG workflows

---

## 🛠 Requirements

```bash
pip install -r requirements.txt
```

Make sure your Python version is 3.8 or above.

---

## 🔑 Setup

### OpenAI API Key

```bash
export OPENAI_API_KEY="sk-..."
```

### Run Qdrant Locally

#### 🐳 Docker

Run once:
```
sudo docker run -p 6333:6333 qdrant/qdrant
```

Then run:
```bash
sudo docker run -p 6333:6333 qdrant/qdrant
```

ArchiveAgent needs the docker image running in the background.

#### 🧱 Native (Linux)

```bash
curl -LO https://github.com/qdrant/qdrant/releases/latest/download/qdrant-linux-x86_64.tar.gz
tar -xzf qdrant-linux-x86_64.tar.gz
./qdrant
```

---

## ▶️ Usage

Run the agent on a file:

```bash
python main.py Example.md
```

You'll get:

- Embedding preview
- Local vector storage
- Snapshot diff tracking

---

## 📁 Project Structure

```
.
├── main.py          # Main script: diff + embed + store
├── Example.md       # Test file for repeated feedback
├── snapshot.json    # Auto-generated change tracking
├── requirements.txt # Python dependencies
├── README.md        # You are here
```

---

## 📜 License

**GPL v3.0**  
Free to use, modify, extend. Keep it open. Keep it sharp. 🧠⚡
