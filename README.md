

## Installation

```
conda create -n stimme python=3.10.13
conda activate stimme
pip install -r requirements.txt
```

Note: You might want to replace the Python version.

Install Ollama: https://ollama.com/

Pull the model:

```
ollama pull gemma2:27b
```

## Start

```
gradio run.py
```

## Access


```
http://0.0.0.0:8001/?__theme=light
```