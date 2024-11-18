# Heilbronner Stimme Content Submission Bot

This project combines the AI expertise of Dr. Tristan Behrens with the journalistic vision of Robert Mucha. In collaboration with [42 Heilbronn](https://www.42heilbronn.de/en/) and [Heilbronner Stimme](https://www.stimme.de), we have developed an open-source tool to support reader-reporters and strengthen local journalism through AI-driven technologies.

## Purpose

The tool encourages readers to actively contribute stories, enriching local reporting. It leverages advanced AI technologies to streamline content management and enhance interaction between readers and editorial teams.

## Features

- **AI-Powered Support:** Automated processes to assist reader-reporters.  
- **Open Source:** Fully open-source and free to use.  
- **Community-Oriented:** Promotes local journalism and fosters stronger reader engagement.

## Supported by

This project was made possible through the collaboration with [42 Heilbronn](https://www.42heilbronn.de/en/) and [Heilbronner Stimme](https://www.stimme.de).

## Learn More

- [GitHub Repository](https://github.com/AI-Guru/stimme_contentsubmissionbot)  
- [Tristan's Website](https://ai-guru.de)  
- [Robert on LinkedIn](https://www.linkedin.com/in/robert-mucha-4b323b99/)

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