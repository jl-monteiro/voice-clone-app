# Trabalho de Clonagem de Voz

Demo local de clonagem de voz com **Gradio** e **Chatterbox Multilingual TTS**.

O aplicativo usa português como idioma padrão (`language_id="pt"`). O usuário pode gravar áudio pelo microfone, selecionar o microfone, enviar um arquivo, digitar um texto e gerar um WAV em `outputs/voz_clonada.wav`.

## Resumo para apresentação

Este trabalho demonstra um pipeline simples de clonagem de voz local:

1. O usuário grava ou envia uma voz de referência.
2. O áudio é salvo temporariamente em `outputs/referencia_usuario.wav`.
3. O texto digitado é enviado para o modelo **Chatterbox Multilingual TTS**.
4. O modelo usa a voz de referência como prompt vocal e gera uma nova fala em português.
5. O resultado final é salvo em `outputs/voz_clonada.wav`.

O objetivo do projeto é mostrar, de forma prática, como um modelo de TTS multilíngue pode usar uma amostra curta de voz para sintetizar um novo áudio com características parecidas.

## Modelo utilizado

O modelo usado é:

```text
Chatterbox Multilingual TTS
```

Configuração principal:

```python
language_id = "pt"
```

O modelo roda localmente no computador. Não usamos ElevenLabs, NVIDIA, API paga, serviço externo pago, login, banco de dados ou armazenamento permanente de vozes.

## Como fizemos

### Interface

A interface foi feita com **Gradio**, usando HTML, CSS e JavaScript customizados para melhorar a experiência:

- seleção de microfone;
- gravação pelo navegador;
- medidor visual de áudio ao vivo;
- upload de arquivo de áudio;
- campo de texto em português;
- player para ouvir a referência;
- player para ouvir o WAV clonado.

### Captura de áudio

No navegador, usamos `navigator.mediaDevices.getUserMedia()` para acessar o microfone. A gravação é convertida para WAV no próprio front-end e enviada ao backend como `data URL`.

### Backend

O backend em Python valida:

- texto vazio;
- áudio ausente;
- arquivo de áudio inexistente;
- áudio vazio.

Depois disso, o serviço de TTS carrega o Chatterbox e gera a voz clonada.

### Geração da voz

O Chatterbox recebe:

- o texto digitado;
- o caminho do áudio de referência;
- o idioma `pt`.

O áudio final é salvo sempre em:

```text
outputs/voz_clonada.wav
```

## Aviso ético

Use somente a sua própria voz ou uma voz com autorização clara. Não use este projeto para imitar pessoas sem consentimento, produzir fraude, assédio, desinformação ou qualquer conteúdo que possa causar dano.

## Requisitos

- Python 3.10 ou 3.11 recomendado.
- Internet no primeiro uso para baixar os pesos gratuitos do Chatterbox.
- Cerca de 3 GB livres para os pesos do modelo em `.models/chatterbox`.
- GPU acelera bastante, mas CPU também funciona com mais paciência.

## Rodando após clonar o repositório

Clone o repositório:

```bash
git clone <url-do-repositorio>
cd voice-clone-app
```

Se o repositório clonado tiver várias pastas e `voice-clone-app` estiver dentro dele, entre na pasta do projeto:

```bash
cd voice-clone-app
```

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider
.\.venv\Scripts\python.exe app.py
```

Abra o endereço exibido pelo Gradio, normalmente:

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

Abra o endereço exibido pelo Gradio, normalmente:

```text
http://127.0.0.1:7860
```

## Primeiro uso

Na primeira geração, o app pode baixar os pesos do Chatterbox para:

```text
.models/chatterbox
```

Esse download é grande, em torno de 3 GB. Ele não é baixado a cada geração. Depois que os arquivos estão no disco, o app reutiliza o modelo local.

## Como usar

1. Escolha o microfone no seletor `Microfone`.
2. Se a lista estiver vazia, clique em `Atualizar` e permita o microfone no navegador.
3. Clique em `Iniciar gravação`, fale por alguns segundos e depois clique em `Parar gravação`.
4. Use `Ouvir prévia` ou o player nativo para conferir a referência.
5. Digite o texto em português.
6. Clique em `Gerar WAV Clonado`.
7. Ouça o resultado no player de saída.

## Limitações

- A qualidade depende muito do áudio de referência.
- Áudio com ruído, música, eco ou várias pessoas falando pode gerar resultados ruins.
- A primeira geração pode demorar porque o modelo precisa ser carregado.
- Em CPU, a geração pode ser lenta.
- O demo foi feito para sala de aula e apresentações locais, não para produção.

## Estrutura

```text
voice-clone-app/
  app.py
  requirements.txt
  README.md
  src/__init__.py
  src/audio_utils.py
  src/tts_service.py
  tests/test_audio_utils.py
  outputs/.gitkeep
```
