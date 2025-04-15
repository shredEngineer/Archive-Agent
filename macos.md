# Install Archive Agent on Mac OS

To install **Archive Agent** on Mac OS, run this:

```bash
brew install pyenv poetry pandoc git docker
pyenv install 3.10.13
pyenv global 3.10.13

git clone https://github.com/shredEngineer/Archive-Agent
cd Archive-Agent
poetry env use $(pyenv which python)
poetry install
chmod +x *.sh
poetry run python -m spacy download xx_sent_ud_sm
alias archive-agent="$(pwd)/archive-agent.sh"
./ensure-quadrant.sh
```