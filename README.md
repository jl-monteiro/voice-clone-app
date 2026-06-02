# Voice Clone Demo

Demo local de clonagem de voz com Gradio e Chatterbox Multilingual TTS.

O app usa portugues como idioma padrao (`language_id="pt"`). O usuario pode gravar audio pelo microfone, selecionar o microfone, enviar um arquivo, digitar um texto e gerar um WAV em `outputs/voz_clonada.wav`.

## Aviso etico

Use somente a sua propria voz ou uma voz com autorizacao clara. Nao use este projeto para imitar pessoas sem consentimento, produzir fraude, assedio, desinformacao ou qualquer conteudo que possa causar dano.

## Como funciona

- O front-end em Gradio usa HTML, CSS e JavaScript para gravar audio no navegador.
- A gravacao ou upload vira um arquivo temporario em `outputs/referencia_usuario.wav`.
- O Chatterbox Multilingual TTS roda localmente no computador.
- Os pesos do modelo ficam em `.models/chatterbox`.
- Cada geracao sobrescreve `outputs/voz_clonada.wav`.
- O app nao usa API paga, login, banco de dados ou armazenamento permanente de vozes.

## Requisitos

- Python 3.10 ou 3.11 recomendado.
- Internet no primeiro uso para baixar os pesos gratuitos do Chatterbox.
- Cerca de 3 GB livres para os pesos do modelo em `.models/chatterbox`.
- GPU acelera bastante, mas CPU tambem funciona com mais paciencia.

## Rodando apos clonar o repositorio

Clone o repositorio:

```bash
git clone <url-do-repositorio>
cd voice-clone-demo
```

Se o repositorio clonado tiver varias pastas e `voice-clone-demo` estiver dentro dele, entre na pasta do projeto:

```bash
cd voice-clone-demo
```

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider
.\.venv\Scripts\python.exe app.py
```

Abra o endereco exibido pelo Gradio, normalmente:

```text
http://127.0.0.1:7860
```

### macOS ou Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pytest -p no:cacheprovider
python app.py
```

Abra o endereco exibido pelo Gradio, normalmente:

```text
http://127.0.0.1:7860
```

## Primeiro uso

Na primeira geracao, o app pode baixar os pesos do Chatterbox para:

```text
.models/chatterbox
```

Esse download e grande, em torno de 3 GB. Ele nao e baixado a cada geracao. Depois que os arquivos estao no disco, o app reutiliza o modelo local.

## Como usar

1. Escolha o microfone no seletor `Microfone`.
2. Se a lista estiver vazia, clique em `Atualizar` e permita o microfone no navegador.
3. Clique em `Iniciar gravacao`, fale por alguns segundos e depois clique em `Parar gravacao`.
4. Use `Ouvir previa` ou o player nativo para conferir a referencia.
5. Digite o texto em portugues.
6. Clique em `Gerar WAV Clonado`.
7. Ouca o resultado no player de saida.

O arquivo final e salvo sempre em:

```text
outputs/voz_clonada.wav
```

## Uso em Colab

1. Clone o repositorio no Colab.
2. Entre na pasta `voice-clone-demo`.
3. Rode:

```bash
pip install -r requirements.txt
pytest -p no:cacheprovider
GRADIO_SHARE=1 python app.py
```

No Colab, `GRADIO_SHARE=1` cria um link publico temporario do Gradio. Use esse link apenas para demonstracoes controladas e nunca envie audio de terceiros sem autorizacao.

## Limitacoes

- A qualidade depende muito do audio de referencia.
- Audio com ruido, musica, eco ou varias pessoas falando pode gerar resultados ruins.
- A primeira geracao pode demorar porque o modelo precisa ser carregado.
- Em CPU, a geracao pode ser lenta.
- O demo foi feito para sala de aula e apresentacoes locais, nao para producao.

## Estrutura

```text
voice-clone-demo/
  app.py
  requirements.txt
  README.md
  src/__init__.py
  src/audio_utils.py
  src/tts_service.py
  tests/test_audio_utils.py
  outputs/.gitkeep
```
