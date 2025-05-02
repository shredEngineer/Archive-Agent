# Install Archive Agent on macOS

To install **Archive Agent** on macOS, run this:

```bash
brew install git pyenv poetry pandoc tkinter docker

pyenv install 3.10.13
pyenv global 3.10.13

git clone https://github.com/shredEngineer/Archive-Agent
cd Archive-Agent

poetry env use $(pyenv which python)
poetry install
poetry run python -m spacy download xx_sent_ud_sm

chmod +x *.sh
echo "alias archive-agent='$(pwd)/archive-agent.sh'" >> ~/.zshrc && source ~/.zshrc

./ensure-qdrant.sh
```
