import os
from pathlib import Path
from typing import Any

import gradio as gr

from src.audio_utils import save_reference_audio_from_data_url, validate_audio_path
from src.tts_service import OUTPUT_DIR, generate_cloned_voice

THEME = gr.themes.Base()

RECORDER_HTML = """
<section id="voice-recorder" class="recorder-shell" aria-label="Gravador de voz">
  <div class="card-header">
    <div>
      <p class="section-kicker">Entrada de voz</p>
      <h2 class="card-title">Voz de referência</h2>
      <p class="card-description">Grave uma amostra curta e confira a prévia antes de gerar.</p>
    </div>
    <span id="mic-state" class="ui-badge" aria-live="polite">Pronto</span>
  </div>

  <div class="meter-wrap">
    <canvas id="voice-meter" role="img" aria-label="Medidor visual do microfone"></canvas>
    <div class="meter-footer">
      <span id="recording-time">00:00</span>
    </div>
  </div>

  <div class="device-picker">
    <label class="field-label" for="microphone-select">Microfone</label>
    <div class="device-controls">
      <select id="microphone-select" class="ui-select" name="microphone_device" aria-label="Selecionar microfone">
        <option value="">Microfone padrão</option>
      </select>
      <button id="refresh-microphones" class="ui-button ui-button-outline" type="button">
        Atualizar
      </button>
    </div>
  </div>

  <div class="recorder-actions" aria-label="Controles do gravador">
    <button id="record-toggle" class="ui-button ui-button-primary" type="button">
      Iniciar gravação
    </button>
    <button id="play-reference" class="ui-button ui-button-secondary" type="button" disabled>
      Ouvir prévia
    </button>
    <label class="ui-button ui-button-outline" for="audio-upload">
      Enviar áudio
    </label>
    <input id="audio-upload" class="file-input" name="reference_audio_file" type="file" accept="audio/*" aria-label="Enviar arquivo de áudio" />
  </div>

  <audio id="reference-player" class="native-audio" controls preload="metadata" aria-label="Prévia da voz gravada"></audio>

  <p id="recorder-message" class="recorder-message" aria-live="polite">
    Clique em Iniciar Gravação, permita o microfone e fale por alguns segundos.
  </p>
</section>
"""

APP_JS = r"""
() => {
  const findElementById = (id, root = document) => {
    if (!root) {
      return null;
    }

    if (root.getElementById) {
      const directMatch = root.getElementById(id);
      if (directMatch) {
        return directMatch;
      }
    }

    const nodes = root.querySelectorAll ? root.querySelectorAll("*") : [];
    for (const node of nodes) {
      if (node.id === id) {
        return node;
      }
      if (node.shadowRoot) {
        const shadowMatch = findElementById(id, node.shadowRoot);
        if (shadowMatch) {
          return shadowMatch;
        }
      }
    }

    return null;
  };

  const boot = () => {
    const root = findElementById("voice-recorder");
    const payloadRoot = findElementById("reference-payload");
    if (!root || !payloadRoot) {
      window.setTimeout(boot, 250);
      return;
    }
    if (root.dataset.ready === "true") {
      return;
    }
    root.dataset.ready = "true";

    const canvas = findElementById("voice-meter");
    const ctx = canvas.getContext("2d");
    const recordButton = findElementById("record-toggle");
    const playButton = findElementById("play-reference");
    const uploadInput = findElementById("audio-upload");
    const microphoneSelect = findElementById("microphone-select");
    const refreshMicrophonesButton = findElementById("refresh-microphones");
    const player = findElementById("reference-player");
    const statePill = findElementById("mic-state");
    const timerLabel = findElementById("recording-time");
    const message = findElementById("recorder-message");
    const payloadInput = payloadRoot.querySelector("textarea, input");
    const promptRoot = findElementById("prompt-text");
    const promptInput = promptRoot ? promptRoot.querySelector("textarea") : null;

    let audioContext = null;
    let analyser = null;
    let processor = null;
    let stream = null;
    let animationId = null;
    let isRecording = false;
    let recordingStartedAt = 0;
    let recordedChunks = [];
    let recordedSamples = 0;
    let lastSelectedMicrophoneId = "";

    if (payloadInput) {
      payloadInput.setAttribute("name", "reference_audio_payload");
      payloadInput.setAttribute("autocomplete", "off");
      payloadInput.setAttribute("tabindex", "-1");
      payloadInput.setAttribute("aria-hidden", "true");
    }
    if (promptInput) {
      promptInput.setAttribute("name", "prompt_text");
      promptInput.setAttribute("autocomplete", "off");
    }

    const setPayload = (value) => {
      if (!payloadInput) {
        return;
      }
      const descriptor = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(payloadInput), "value");
      if (descriptor && descriptor.set) {
        descriptor.set.call(payloadInput, value);
      } else {
        payloadInput.value = value;
      }
      payloadInput.dispatchEvent(new Event("input", { bubbles: true, composed: true }));
      payloadInput.dispatchEvent(new Event("change", { bubbles: true, composed: true }));
    };

    const setMicrophoneOptions = (devices) => {
      if (!microphoneSelect) {
        return;
      }

      const previousValue = microphoneSelect.value || lastSelectedMicrophoneId;
      microphoneSelect.innerHTML = "";

      const defaultOption = document.createElement("option");
      defaultOption.value = "";
      defaultOption.textContent = "Microfone padrão";
      microphoneSelect.appendChild(defaultOption);

      devices.forEach((device, index) => {
        const option = document.createElement("option");
        option.value = device.deviceId;
        option.textContent = device.label || `Microfone ${index + 1}`;
        microphoneSelect.appendChild(option);
      });

      const hasPrevious = Array.from(microphoneSelect.options).some((option) => option.value === previousValue);
      microphoneSelect.value = hasPrevious ? previousValue : "";
      lastSelectedMicrophoneId = microphoneSelect.value;
    };

    const listMicrophones = async (requestPermission = false) => {
      if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) {
        setMessage("Seu navegador não permite listar microfones. Use Chrome, Edge ou Firefox atualizado.", "error");
        return;
      }

      try {
        if (requestPermission && !isRecording) {
          const permissionStream = await navigator.mediaDevices.getUserMedia({ audio: true });
          permissionStream.getTracks().forEach((track) => track.stop());
        }

        const devices = await navigator.mediaDevices.enumerateDevices();
        const microphones = devices.filter((device) => device.kind === "audioinput");
        setMicrophoneOptions(microphones);

        if (microphones.length === 0) {
          setMessage("Nenhum microfone encontrado. Confira se o dispositivo está conectado.", "error");
        } else if (requestPermission) {
          setMessage("Lista de microfones atualizada. Escolha a entrada antes de gravar.", "ok");
        }
      } catch (error) {
        setMessage("Não consegui listar os microfones. Permita o microfone no navegador e tente atualizar.", "error");
      }
    };

    const setMessage = (text, tone = "neutral") => {
      message.textContent = text;
      message.dataset.tone = tone;
    };

    const setState = (text, recording = false) => {
      statePill.textContent = text;
      statePill.dataset.recording = recording ? "true" : "false";
    };

    const formatTime = (seconds) => {
      const safeSeconds = Math.max(0, Math.floor(seconds));
      const minutes = String(Math.floor(safeSeconds / 60)).padStart(2, "0");
      const rest = String(safeSeconds % 60).padStart(2, "0");
      return `${minutes}:${rest}`;
    };

    const resizeCanvas = () => {
      const ratio = window.devicePixelRatio || 1;
      const width = Math.max(320, canvas.clientWidth);
      const height = Math.max(160, canvas.clientHeight);
      canvas.width = Math.floor(width * ratio);
      canvas.height = Math.floor(height * ratio);
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    };

    const drawIdle = () => {
      resizeCanvas();
      const width = canvas.clientWidth;
      const height = canvas.clientHeight;
      ctx.clearRect(0, 0, width, height);
      ctx.fillStyle = "#f8fbff";
      ctx.fillRect(0, 0, width, height);
      ctx.strokeStyle = "#dbe7f5";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(0, height / 2);
      ctx.lineTo(width, height / 2);
      ctx.stroke();

      const bars = 36;
      const gap = 5;
      const barWidth = (width - gap * (bars - 1)) / bars;
      for (let index = 0; index < bars; index += 1) {
        const wave = Math.sin(index * 0.7) * 0.5 + 0.5;
        const barHeight = 12 + wave * 26;
        const x = index * (barWidth + gap);
        const y = height / 2 - barHeight / 2;
        ctx.fillStyle = index % 3 === 0 ? "#bfdbfe" : "#d7e6f8";
        ctx.fillRect(x, y, barWidth, barHeight);
      }
    };

    const drawLiveMeter = () => {
      if (!analyser || !isRecording) {
        return;
      }

      const width = canvas.clientWidth;
      const height = canvas.clientHeight;
      const frequencyData = new Uint8Array(analyser.frequencyBinCount);
      const timeData = new Uint8Array(analyser.fftSize);
      analyser.getByteFrequencyData(frequencyData);
      analyser.getByteTimeDomainData(timeData);

      let peak = 0;
      for (let index = 0; index < timeData.length; index += 1) {
        peak = Math.max(peak, Math.abs(timeData[index] - 128) / 128);
      }

      ctx.clearRect(0, 0, width, height);
      ctx.fillStyle = "#f8fbff";
      ctx.fillRect(0, 0, width, height);

      const bars = 42;
      const gap = 4;
      const barWidth = (width - gap * (bars - 1)) / bars;
      for (let index = 0; index < bars; index += 1) {
        const value = frequencyData[Math.floor((index / bars) * frequencyData.length)] / 255;
        const movement = Math.max(value, peak * (0.45 + (index % 5) * 0.09));
        const barHeight = Math.max(10, movement * (height - 34));
        const x = index * (barWidth + gap);
        const y = height - barHeight - 16;
        const gradient = ctx.createLinearGradient(0, y, 0, height);
        gradient.addColorStop(0, "#0f766e");
        gradient.addColorStop(0.55, "#2563eb");
        gradient.addColorStop(1, "#93c5fd");
        ctx.fillStyle = gradient;
        ctx.fillRect(x, y, barWidth, barHeight);
      }

      timerLabel.textContent = formatTime((performance.now() - recordingStartedAt) / 1000);
      animationId = window.requestAnimationFrame(drawLiveMeter);
    };

    const mergeBuffers = (chunks, sampleCount) => {
      const result = new Float32Array(sampleCount);
      let offset = 0;
      chunks.forEach((chunk) => {
        result.set(chunk, offset);
        offset += chunk.length;
      });
      return result;
    };

    const writeString = (view, offset, string) => {
      for (let index = 0; index < string.length; index += 1) {
        view.setUint8(offset + index, string.charCodeAt(index));
      }
    };

    const floatTo16BitPcm = (view, offset, input) => {
      for (let index = 0; index < input.length; index += 1, offset += 2) {
        const sample = Math.max(-1, Math.min(1, input[index]));
        view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
      }
    };

    const encodeWav = (samples, sampleRate) => {
      const buffer = new ArrayBuffer(44 + samples.length * 2);
      const view = new DataView(buffer);
      writeString(view, 0, "RIFF");
      view.setUint32(4, 36 + samples.length * 2, true);
      writeString(view, 8, "WAVE");
      writeString(view, 12, "fmt ");
      view.setUint32(16, 16, true);
      view.setUint16(20, 1, true);
      view.setUint16(22, 1, true);
      view.setUint32(24, sampleRate, true);
      view.setUint32(28, sampleRate * 2, true);
      view.setUint16(32, 2, true);
      view.setUint16(34, 16, true);
      writeString(view, 36, "data");
      view.setUint32(40, samples.length * 2, true);
      floatTo16BitPcm(view, 44, samples);
      return buffer;
    };

    const blobToDataUrl = (blob) => new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = () => reject(reader.error);
      reader.readAsDataURL(blob);
    });

    const updatePlayerSource = (sourceUrl) => {
      player.src = sourceUrl;
      player.load();
    };

    const stopStream = async () => {
      if (processor) {
        processor.disconnect();
        processor = null;
      }
      if (analyser) {
        analyser.disconnect();
        analyser = null;
      }
      if (stream) {
        stream.getTracks().forEach((track) => track.stop());
        stream = null;
      }
      if (audioContext) {
        await audioContext.close();
        audioContext = null;
      }
    };

    const stopRecording = async () => {
      if (!isRecording) {
        return;
      }

      isRecording = false;
      recordButton.textContent = "Iniciar gravação";
      setState("Processando");
      if (animationId) {
        window.cancelAnimationFrame(animationId);
        animationId = null;
      }

      const sampleRate = audioContext ? audioContext.sampleRate : 44100;
      await stopStream();

      if (recordedSamples < sampleRate / 2) {
        setMessage("Áudio muito curto. Grave pelo menos 1 segundo de fala.", "error");
        setState("Pronto");
        drawIdle();
        return;
      }

      const samples = mergeBuffers(recordedChunks, recordedSamples);
      const wavBuffer = encodeWav(samples, sampleRate);
      const blob = new Blob([wavBuffer], { type: "audio/wav" });
      const objectUrl = URL.createObjectURL(blob);
      updatePlayerSource(objectUrl);
      playButton.disabled = false;
      setPayload(await blobToDataUrl(blob));
      setMessage("Gravação pronta. Clique em Ouvir prévia para conferir.", "ok");
      setState("Pronto");
      drawIdle();
    };

    const startRecording = async () => {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        setMessage("Seu navegador não permite gravação por microfone. Use Chrome, Edge ou Firefox atualizado.", "error");
        setState("Indisponivel");
        return;
      }

      try {
        const selectedDeviceId = microphoneSelect ? microphoneSelect.value : "";
        lastSelectedMicrophoneId = selectedDeviceId;
        const audioConstraints = {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        };

        if (selectedDeviceId) {
          audioConstraints.deviceId = { exact: selectedDeviceId };
        }

        stream = await navigator.mediaDevices.getUserMedia({
          audio: audioConstraints
        });
        await listMicrophones(false);
      } catch (error) {
        if (error && error.name === "OverconstrainedError") {
          setMessage("Esse microfone não está disponível agora. Atualize a lista e escolha outro.", "error");
        } else {
          setMessage("Não consegui acessar o microfone. Confira a permissão do navegador.", "error");
        }
        setState("Bloqueado");
        return;
      }

      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      audioContext = new AudioContextClass();
      const source = audioContext.createMediaStreamSource(stream);
      analyser = audioContext.createAnalyser();
      analyser.fftSize = 128;
      processor = audioContext.createScriptProcessor(4096, 1, 1);

      recordedChunks = [];
      recordedSamples = 0;
      source.connect(analyser);
      source.connect(processor);
      processor.connect(audioContext.destination);
      processor.onaudioprocess = (event) => {
        const output = event.outputBuffer.getChannelData(0);
        output.fill(0);
        if (!isRecording) {
          return;
        }
        const input = event.inputBuffer.getChannelData(0);
        recordedChunks.push(new Float32Array(input));
        recordedSamples += input.length;
      };

      isRecording = true;
      recordingStartedAt = performance.now();
      timerLabel.textContent = "00:00";
      player.removeAttribute("src");
      player.load();
      playButton.disabled = true;
      setPayload("");
      recordButton.textContent = "Parar gravação";
      setMessage("Gravando agora. Fale perto do microfone.", "recording");
      setState("Gravando", true);
      resizeCanvas();
      drawLiveMeter();
    };

    recordButton.addEventListener("click", () => {
      if (isRecording) {
        stopRecording();
      } else {
        startRecording();
      }
    });

    if (microphoneSelect) {
      microphoneSelect.addEventListener("change", () => {
        lastSelectedMicrophoneId = microphoneSelect.value;
        const selectedLabel = microphoneSelect.options[microphoneSelect.selectedIndex]?.textContent || "Microfone padrão";
        setMessage(`Entrada selecionada: ${selectedLabel}.`, "ok");
      });
    }

    if (refreshMicrophonesButton) {
      refreshMicrophonesButton.addEventListener("click", () => {
        listMicrophones(true);
      });
    }

    if (navigator.mediaDevices && navigator.mediaDevices.addEventListener) {
      navigator.mediaDevices.addEventListener("devicechange", () => {
        listMicrophones(false);
      });
    }

    playButton.addEventListener("click", async () => {
      if (!player.src) {
        return;
      }
      try {
        await player.play();
      } catch (error) {
        setMessage("O navegador bloqueou o play automático. Use o controle do player abaixo.", "error");
      }
    });

    uploadInput.addEventListener("change", async (event) => {
      const file = event.target.files && event.target.files[0];
      if (!file) {
        return;
      }
      if (isRecording) {
        await stopRecording();
      }
      const objectUrl = URL.createObjectURL(file);
      updatePlayerSource(objectUrl);
      playButton.disabled = false;
      setPayload(await blobToDataUrl(file));
      setMessage(`Arquivo carregado: ${file.name}. Confira no player antes de gerar.`, "ok");
      setState("Arquivo");
      timerLabel.textContent = "00:00";
      drawIdle();
    });

    window.addEventListener("resize", drawIdle);
    listMicrophones(false);
    drawIdle();
  };

  boot();
}
"""

APP_HEAD = f"<script>({APP_JS})();</script>"

CSS = """
@import url("https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700;800&display=swap");

:root {
  color-scheme: light;
  --background: #f8fafc;
  --foreground: #0f172a;
  --card: #ffffff;
  --card-foreground: #0f172a;
  --popover: #ffffff;
  --popover-foreground: #0f172a;
  --primary: #2563eb;
  --primary-foreground: #ffffff;
  --secondary: #f1f5f9;
  --secondary-foreground: #0f172a;
  --muted: #f1f5f9;
  --muted-foreground: #64748b;
  --accent: #ecfeff;
  --accent-foreground: #155e75;
  --destructive: #dc2626;
  --destructive-foreground: #ffffff;
  --success: #0f766e;
  --success-soft: #ccfbf1;
  --warning: #d97706;
  --warning-soft: #ffedd5;
  --border: #e2e8f0;
  --input: #cbd5e1;
  --ring: #2563eb;
  --radius: 0.625rem;
  --font-sans: "Geist", Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --font-mono: "JetBrains Mono", "Fira Code", Consolas, monospace;
  --space-1: 0.25rem;
  --space-2: 0.5rem;
  --space-3: 0.75rem;
  --space-4: 1rem;
  --space-5: 1.25rem;
  --space-6: 1.5rem;
  --space-8: 2rem;
  --shadow-card: 0 1px 2px rgba(15, 23, 42, 0.05);
  --shadow-pop: 0 18px 45px rgba(15, 23, 42, 0.10);
}

html,
body,
gradio-app {
  min-height: 100%;
  background: var(--background) !important;
  color: var(--foreground) !important;
}

body {
  margin: 0 !important;
  overflow-x: hidden;
}

.gradio-container {
  width: min(1180px, calc(100vw - 48px)) !important;
  max-width: none !important;
  min-height: 100vh !important;
  margin: 0 auto !important;
  padding: var(--space-8) 0 3rem !important;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.82), rgba(248, 250, 252, 0.96)),
    radial-gradient(circle at 1px 1px, rgba(100, 116, 139, 0.18) 1px, transparent 0) !important;
  background-size: auto, 24px 24px !important;
  color: var(--foreground) !important;
  font-family: var(--font-sans) !important;
}

.contain,
.block,
.wrap,
.form,
.panel,
.gradio-container .prose {
  background: transparent !important;
  color: var(--foreground) !important;
  border-color: transparent !important;
}

#app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-2) 0 var(--space-6);
}

.brand-lockup {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-width: 0;
}

.brand-mark {
  display: grid;
  place-items: center;
  width: 2.75rem;
  height: 2.75rem;
  border-radius: var(--radius);
  border: 1px solid var(--border);
  background: var(--foreground);
  color: var(--primary-foreground);
  font-size: 0.875rem;
  font-weight: 800;
  box-shadow: var(--shadow-card);
}

#app-header h1 {
  margin: 0;
  color: var(--foreground);
  font-size: 1.875rem;
  line-height: 1.2;
  letter-spacing: 0;
}

.header-actions,
.recorder-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.section-kicker {
  margin: 0 0 var(--space-1);
  color: var(--muted-foreground);
  font-size: 0.75rem;
  font-weight: 700;
  line-height: 1;
  letter-spacing: 0;
  text-transform: uppercase;
}

.app-grid {
  align-items: stretch;
  gap: var(--space-5) !important;
}

.tool-panel {
  min-width: 0 !important;
  border: 1px solid var(--border);
  background: var(--card);
  color: var(--card-foreground);
  border-radius: var(--radius);
  padding: var(--space-5);
  box-shadow: var(--shadow-pop);
}

.tool-panel h2,
.tool-panel label span {
  color: var(--foreground) !important;
}

.card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-5);
}

.card-title {
  margin: 0;
  color: var(--foreground);
  font-size: 1.125rem;
  font-weight: 700;
  line-height: 1.35;
  letter-spacing: 0;
}

.card-description {
  margin: var(--space-1) 0 0;
  color: var(--muted-foreground);
  font-size: 0.875rem;
  line-height: 1.5;
}

.recorder-shell {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.ui-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: fit-content;
  min-height: 1.625rem;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--card);
  color: var(--foreground);
  padding: 0 var(--space-2);
  font-size: 0.75rem;
  font-weight: 700;
  white-space: nowrap;
}

.ui-badge-secondary {
  background: var(--secondary);
  color: var(--secondary-foreground);
}

.ui-badge[data-recording="true"] {
  border-color: #fecaca;
  background: #fef2f2;
  color: var(--destructive);
}

.meter-wrap {
  overflow: hidden;
  border: 1px solid var(--border);
  background: var(--muted);
  border-radius: var(--radius);
}

#voice-meter {
  display: block;
  width: 100%;
  height: 13rem;
  touch-action: manipulation;
}

.meter-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  border-top: 1px solid var(--border);
  background: var(--card);
  color: var(--muted-foreground);
  padding: var(--space-3);
  font-size: 0.8125rem;
}

#recording-time {
  color: var(--foreground);
  font-variant-numeric: tabular-nums;
  font-weight: 700;
}

.device-picker {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.field-label {
  color: var(--foreground);
  font-size: 0.875rem;
  font-weight: 600;
}

.device-controls {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: var(--space-2);
}

.ui-select {
  min-width: 0;
  min-height: 2.5rem;
  border: 1px solid var(--input);
  background: var(--card);
  color: var(--foreground);
  border-radius: var(--radius);
  padding: 0 var(--space-3);
  font: inherit;
  font-size: 0.875rem;
  font-weight: 500;
  touch-action: manipulation;
}

.ui-select:focus-visible,
.ui-button:focus-visible,
#prompt-text textarea:focus-visible,
#generate-button button:focus-visible {
  outline: 2px solid var(--ring) !important;
  outline-offset: 2px;
}

.ui-button {
  appearance: none;
  border: 1px solid var(--border);
  background: var(--card);
  color: var(--foreground);
  border-radius: var(--radius);
  min-height: 2.5rem;
  padding: 0 var(--space-4);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  font: inherit;
  font-size: 0.875rem;
  font-weight: 700;
  cursor: pointer;
  transition: background-color 150ms ease, border-color 150ms ease, color 150ms ease, transform 150ms ease;
  touch-action: manipulation;
  -webkit-tap-highlight-color: transparent;
}

.ui-button:hover:not(:disabled) {
  background: var(--secondary);
  transform: translateY(-1px);
}

.ui-button:disabled {
  cursor: not-allowed;
  opacity: 0.48;
}

.ui-button-primary {
  border-color: var(--primary);
  background: var(--primary);
  color: var(--primary-foreground);
}

.ui-button-primary:hover:not(:disabled) {
  background: #1d4ed8;
  border-color: #1d4ed8;
}

.ui-button-secondary {
  background: var(--secondary);
  color: var(--secondary-foreground);
}

.ui-button-outline {
  background: transparent;
}

.file-input {
  position: absolute;
  width: 1px;
  height: 1px;
  opacity: 0;
  overflow: hidden;
  pointer-events: none;
}

.native-audio {
  width: 100%;
  min-height: 2.75rem;
  accent-color: var(--primary);
}

.recorder-message,
.status {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--muted);
  color: var(--muted-foreground);
  font-size: 0.875rem;
  line-height: 1.5;
  padding: var(--space-3);
}

.recorder-message[data-tone="ok"],
.status-ok {
  border-color: #99f6e4;
  background: var(--success-soft);
  color: #134e4a;
}

.recorder-message[data-tone="recording"] {
  border-color: #fecaca;
  background: #fef2f2;
  color: var(--destructive);
}

.recorder-message[data-tone="error"],
.status-error {
  border-color: #fecaca;
  background: #fef2f2;
  color: var(--destructive);
}

.status-muted {
  background: var(--muted);
  color: var(--muted-foreground);
}

.status strong {
  color: var(--foreground);
}

#reference-payload,
.hidden-transport {
  display: none !important;
}

#text-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

#prompt-text label span {
  color: var(--foreground) !important;
  font-size: 0.875rem !important;
  font-weight: 600 !important;
}

#prompt-text textarea {
  min-height: 14rem !important;
  border: 1px solid var(--input) !important;
  background: var(--card) !important;
  color: var(--foreground) !important;
  border-radius: var(--radius) !important;
  padding: var(--space-3) !important;
  font-family: var(--font-sans) !important;
  font-size: 0.9375rem !important;
  line-height: 1.6 !important;
  box-shadow: var(--shadow-card);
}

#prompt-text textarea::placeholder {
  color: var(--muted-foreground) !important;
}

#generate-button button {
  width: 100%;
  min-height: 2.75rem;
  border-radius: var(--radius) !important;
  border: 1px solid var(--primary) !important;
  background: var(--primary) !important;
  color: var(--primary-foreground) !important;
  font-size: 0.9375rem;
  font-weight: 800 !important;
  transition: background-color 150ms ease, transform 150ms ease, box-shadow 150ms ease;
}

#generate-button button:hover {
  background: #1d4ed8 !important;
  transform: translateY(-1px);
  box-shadow: 0 10px 22px rgba(37, 99, 235, 0.18);
}

#output-audio {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  background: var(--card);
}

footer,
.footer {
  display: none !important;
}

@media (prefers-reduced-motion: reduce) {
  .ui-button,
  #generate-button button {
    transition: none;
    transform: none !important;
  }
}

@media (max-width: 780px) {
  .gradio-container {
    width: min(100vw - 24px, 1180px) !important;
    padding: var(--space-5) 0 var(--space-8) !important;
  }

  #app-header {
    align-items: flex-start;
    flex-direction: column;
  }

  #app-header h1 {
    font-size: 1.5rem;
  }

  .tool-panel {
    padding: var(--space-4);
  }

    .card-header,
    .meter-footer {
    flex-direction: column;
  }

  .device-controls {
    grid-template-columns: 1fr;
  }

  .ui-button,
  .recorder-actions label {
    width: 100%;
  }
}
"""


def _is_gradio_v6_or_newer() -> bool:
    try:
        major_version = int(gr.__version__.split(".", maxsplit=1)[0])
    except (AttributeError, ValueError):
        return False

    return major_version >= 6


def _status(message: str, tone: str = "muted") -> str:
    return f"<div class='status status-{tone}' role='status' aria-live='polite'>{message}</div>"


def _prepare_reference_audio(reference_payload: str | None) -> tuple[str, str | None]:
    try:
        audio_path = save_reference_audio_from_data_url(reference_payload, OUTPUT_DIR)
    except ValueError as exc:
        return _status(str(exc), "error"), None

    return (
        _status(
            f"<strong>Voz pronta.</strong> Arquivo recebido como {Path(audio_path).name}. "
            "Agora dá para gerar o WAV clonado.",
            "ok",
        ),
        str(audio_path),
    )


def _generate_audio(text: str | None, reference_audio_path: str | None) -> tuple[Any, str]:
    try:
        reference_path = validate_audio_path(reference_audio_path)
        output_path = generate_cloned_voice(text, reference_path)
        return (
            gr.update(value=output_path, visible=True),
            _status("<strong>Áudio gerado.</strong> Salvo em outputs/voz_clonada.wav.", "ok"),
        )
    except ValueError as exc:
        raise gr.Error(str(exc)) from exc
    except RuntimeError as exc:
        raise gr.Error(str(exc)) from exc
    except Exception as exc:
        raise gr.Error(f"Não foi possível gerar o áudio: {exc}") from exc


def build_interface() -> gr.Blocks:
    blocks_kwargs = {"title": "Clone de voz PT"}
    if not _is_gradio_v6_or_newer():
        blocks_kwargs.update({"theme": THEME, "css": CSS, "js": APP_JS, "head": APP_HEAD})

    with gr.Blocks(**blocks_kwargs) as demo:
        gr.HTML(
            """
            <header id="app-header">
              <div class="brand-lockup">
                <div class="brand-mark" aria-hidden="true">VC</div>
                <div>
                  <p class="section-kicker">Demo local</p>
                  <h1>Voice Clone Studio</h1>
                </div>
              </div>
              <div class="header-actions" aria-label="Contexto do app">
                <span class="ui-badge ui-badge-secondary">Chatterbox</span>
                <span class="ui-badge">PT local</span>
              </div>
            </header>
            """
        )
        reference_payload = gr.Textbox(
          label="Transporte interno do áudio",
            show_label=False,
            lines=1,
            container=False,
            elem_id="reference-payload",
            elem_classes=["hidden-transport"],
        )
        reference_path_state = gr.State(value=None)

        with gr.Row(equal_height=False, elem_classes=["app-grid"]):
            with gr.Column(scale=1, min_width=340, elem_classes=["tool-panel"]):
                gr.HTML(RECORDER_HTML)
                audio_status = gr.HTML(_status("Nenhuma voz recebida ainda.", "muted"))

            with gr.Column(scale=1, min_width=340, elem_classes=["tool-panel"], elem_id="text-panel"):
                gr.HTML(
                    """
                    <div class="card-header">
                      <div>
                        <p class="section-kicker">Saida sintetica</p>
                        <h2 class="card-title">Texto e resultado</h2>
                        <p class="card-description">Escreva em português e gere um WAV com a voz de referência.</p>
                      </div>
                    </div>
                    """
                )
                text = gr.Textbox(
                    label="Texto em português",
                    placeholder="Digite o texto que você quer ouvir...",
                    lines=8,
                    max_lines=12,
                    elem_id="prompt-text",
                )
                generate_button = gr.Button(
                    "Gerar WAV Clonado",
                    variant="primary",
                    elem_id="generate-button",
                )
                generation_status = gr.HTML(_status("Resultado aguardando geracao.", "muted"))
                output_audio = gr.Audio(
                    label="Áudio clonado",
                    type="filepath",
                    format="wav",
                    interactive=False,
                    visible=False,
                    elem_id="output-audio",
                )

        reference_payload.change(
            fn=_prepare_reference_audio,
            inputs=reference_payload,
            outputs=[audio_status, reference_path_state],
            show_progress="hidden",
            queue=False,
        )

        generate_button.click(
            fn=_generate_audio,
            inputs=[text, reference_path_state],
            outputs=[output_audio, generation_status],
            show_progress="full",
            concurrency_limit=1,
        )

    return demo


def launch_app() -> None:
    launch_kwargs = {
        "share": os.getenv("GRADIO_SHARE") == "1",
        "footer_links": [],
    }
    if _is_gradio_v6_or_newer():
        launch_kwargs.update({"theme": THEME, "css": CSS, "js": APP_JS, "head": APP_HEAD})

    build_interface().queue(default_concurrency_limit=1).launch(**launch_kwargs)


if __name__ == "__main__":
    launch_app()
