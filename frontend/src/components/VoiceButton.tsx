// SPDX-License-Identifier: AGPL-3.0-or-later
// Voice prompt: record a short clip in the browser (MediaRecorder), send it to our API, which
// transcribes it with Whisper on Cloudflare. The audio is never stored.
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, ApiError } from "../api";
import { Icon } from "./icons";

export const MAX_VOICE_SECONDS = 30; // matches VOICE_MAX_SECONDS on the server
const PREFERRED = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/mp4", "audio/webm"];

export function voiceSupported(): boolean {
  return typeof window !== "undefined" && typeof window.MediaRecorder !== "undefined" && Boolean(navigator.mediaDevices?.getUserMedia);
}

function pickMime(): string | undefined {
  return PREFERRED.find((m) => window.MediaRecorder.isTypeSupported?.(m));
}

export default function VoiceButton({ onText, onError }: { onText: (text: string) => void; onError: (err: unknown) => void }) {
  const { t, i18n } = useTranslation();
  const [state, setState] = useState<"idle" | "recording" | "sending">("idle");
  const [seconds, setSeconds] = useState(0);
  const recorder = useRef<MediaRecorder | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | undefined>(undefined);

  useEffect(
    () => () => {
      clearInterval(timer.current);
      recorder.current?.stream.getTracks().forEach((tr) => tr.stop());
    },
    [],
  );

  if (!voiceSupported()) return null;

  const send = async (blob: Blob) => {
    setState("sending");
    try {
      const fd = new FormData();
      fd.append("file", blob, "voice");
      const lang = i18n.language.slice(0, 2);
      if (["uz", "ru", "en"].includes(lang)) fd.append("language", lang);
      const res = await api<{ text: string }>("/api/voice/transcribe", { method: "POST", form: fd });
      if (res.text) onText(res.text);
    } catch (err) {
      onError(err);
    } finally {
      setState("idle");
    }
  };

  const start = async () => {
    onError(null);
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      onError(new ApiError("mic_denied", 0));
      return;
    }
    const mimeType = pickMime();
    const rec = new MediaRecorder(stream, mimeType ? { mimeType, audioBitsPerSecond: 32000 } : undefined);
    const chunks: Blob[] = [];
    rec.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    rec.onstop = () => {
      clearInterval(timer.current);
      stream.getTracks().forEach((tr) => tr.stop());
      recorder.current = null;
      void send(new Blob(chunks, { type: rec.mimeType || "audio/webm" }));
    };
    recorder.current = rec;
    rec.start();
    setSeconds(0);
    setState("recording");
    const began = Date.now();
    timer.current = setInterval(() => {
      const s = Math.floor((Date.now() - began) / 1000);
      setSeconds(s);
      if (s >= MAX_VOICE_SECONDS && rec.state === "recording") rec.stop();
    }, 250);
  };

  const stop = () => {
    if (recorder.current?.state === "recording") recorder.current.stop();
  };

  const recording = state === "recording";
  const label = recording ? t("studio.voiceStop") : state === "sending" ? t("studio.voiceSending") : t("studio.voiceStart");
  return (
    <button
      type="button"
      onClick={() => (recording ? stop() : void start())}
      disabled={state === "sending"}
      aria-label={label}
      title={label}
      aria-pressed={recording}
      className={`flex items-center gap-1.5 rounded-xl border px-3 py-2 text-xs font-medium transition disabled:opacity-60 ${
        recording ? "border-danger/60 bg-danger/10 text-danger" : "border-line bg-bg/60 text-ink hover:border-white/20"
      }`}
    >
      <Icon name={recording ? "stop" : "mic"} size={14} className={state === "sending" ? "animate-pulse" : ""} />
      {recording ? `${seconds}s / ${MAX_VOICE_SECONDS}s` : state === "sending" ? t("studio.voiceSending") : t("studio.voice")}
    </button>
  );
}
