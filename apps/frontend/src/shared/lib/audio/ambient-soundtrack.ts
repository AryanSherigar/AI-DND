import { ScenarioMood } from "@/features/play/types/audio.types";

const CROSSFADE_DURATION_SECONDS = 4.0;
const MIN_COOLDOWN_MS = 45000;
const GAIN_MIN = 0.0001;
const STORAGE_KEY_VOLUME = "ai_dnd_audio_volume";
const STORAGE_KEY_MUTED = "ai_dnd_audio_muted";

interface AudioChannel {
  element: HTMLAudioElement;
  sourceNode: MediaElementAudioSourceNode | null;
  gainNode: GainNode | null;
}

export type MoodListener = (mood: ScenarioMood) => void;

export class AmbientSoundtrackController {
  private audioContext: AudioContext | null = null;
  private masterGain: GainNode | null = null;
  private channelA: AudioChannel | null = null;
  private channelB: AudioChannel | null = null;
  private activeChannelIndex: 0 | 1 = 0;
  private currentMood: ScenarioMood | null = null;
  private lastTransitionTime = 0;
  private volume = 0.6;
  private isMuted = false;
  private isUnlocked = false;
  private moodListeners: Set<MoodListener> = new Set();

  constructor() {
    this.loadSavedPreferences();
  }

  public onMoodChange(listener: MoodListener): () => void {
    this.moodListeners.add(listener);
    return () => {
      this.moodListeners.delete(listener);
    };
  }

  private notifyMoodChange(mood: ScenarioMood): void {
    for (const listener of this.moodListeners) {
      try {
        listener(mood);
      } catch {
        // Suppress listener error
      }
    }
  }

  public getMood(): ScenarioMood | null {
    return this.currentMood;
  }

  public getVolume(): number {
    return this.volume;
  }

  public getIsMuted(): boolean {
    return this.isMuted;
  }

  public init(): void {
    if (typeof window === "undefined" || this.audioContext) return;
    this.setupAudioContext();
    this.setupAutoplayUnlock();
  }

  public setVolume(vol: number): void {
    this.volume = Math.max(0.0, Math.min(1.0, vol));
    this.savePreferences();
    if (this.masterGain && this.audioContext && !this.isMuted) {
      this.masterGain.gain.setValueAtTime(
        this.volume,
        this.audioContext.currentTime,
      );
    }
  }

  public toggleMute(): boolean {
    this.isMuted = !this.isMuted;
    this.savePreferences();
    if (this.masterGain && this.audioContext) {
      const target = this.isMuted ? 0 : this.volume;
      this.masterGain.gain.setValueAtTime(
        target,
        this.audioContext.currentTime,
      );
    }
    return this.isMuted;
  }

  public transitionTo(
    newMood: ScenarioMood,
    isForce: boolean = false,
  ): boolean {
    if (!this.shouldAllowTransition(newMood, isForce)) {
      return false;
    }

    this.init();
    this.ensureContextRunning();
    this.executeCrossfade(newMood);
    this.currentMood = newMood;
    this.lastTransitionTime = Date.now();
    this.notifyMoodChange(newMood);
    return true;
  }

  public stop(): void {
    if (this.channelA?.element) {
      this.channelA.element.pause();
    }
    if (this.channelB?.element) {
      this.channelB.element.pause();
    }
    this.currentMood = null;
  }

  private shouldAllowTransition(
    newMood: ScenarioMood,
    isForce: boolean,
  ): boolean {
    if (newMood === this.currentMood) return false;
    if (isForce || newMood === "combat") return true;

    const timeSinceLast = Date.now() - this.lastTransitionTime;
    return timeSinceLast >= MIN_COOLDOWN_MS;
  }

  private setupAudioContext(): void {
    const AudioCtx =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext: typeof AudioContext })
        .webkitAudioContext;
    if (!AudioCtx) return;

    this.audioContext = new AudioCtx();
    this.masterGain = this.audioContext.createGain();
    this.masterGain.gain.value = this.isMuted ? 0 : this.volume;
    this.masterGain.connect(this.audioContext.destination);

    this.channelA = this.createChannel();
    this.channelB = this.createChannel();
  }

  private createChannel(): AudioChannel {
    const audio = new Audio();
    audio.loop = true;
    audio.preload = "auto";
    let sourceNode: MediaElementAudioSourceNode | null = null;
    let gainNode: GainNode | null = null;

    if (this.audioContext && this.masterGain) {
      try {
        sourceNode = this.audioContext.createMediaElementSource(audio);
        gainNode = this.audioContext.createGain();
        gainNode.gain.value = GAIN_MIN;
        sourceNode.connect(gainNode);
        gainNode.connect(this.masterGain);
      } catch {
        // Fallback for restricted test/headless contexts
      }
    }

    return { element: audio, sourceNode, gainNode };
  }

  private executeCrossfade(newMood: ScenarioMood): void {
    if (!this.channelA || !this.channelB || !this.audioContext) return;

    const outgoing =
      this.activeChannelIndex === 0 ? this.channelA : this.channelB;
    const incoming =
      this.activeChannelIndex === 0 ? this.channelB : this.channelA;
    this.activeChannelIndex = this.activeChannelIndex === 0 ? 1 : 0;

    const now = this.audioContext.currentTime;
    this.fadeChannelOut(outgoing, now);
    this.fadeChannelIn(incoming, newMood, now);
  }

  private fadeChannelOut(channel: AudioChannel, now: number): void {
    if (!channel.gainNode || !this.audioContext) {
      channel.element.pause();
      return;
    }

    const currentGain = Math.max(channel.gainNode.gain.value, GAIN_MIN);
    channel.gainNode.gain.setValueAtTime(currentGain, now);
    channel.gainNode.gain.exponentialRampToValueAtTime(
      GAIN_MIN,
      now + CROSSFADE_DURATION_SECONDS,
    );

    setTimeout(() => {
      channel.element.pause();
    }, CROSSFADE_DURATION_SECONDS * 1000);
  }

  private fadeChannelIn(
    channel: AudioChannel,
    newMood: ScenarioMood,
    now: number,
  ): void {
    channel.element.src = `/audio/moods/${newMood}.wav`;
    const playPromise = channel.element.play();
    if (playPromise !== undefined) {
      playPromise.catch(() => {
        // Autoplay policy blocked; unlocked on next user gesture
      });
    }

    if (!channel.gainNode || !this.audioContext) return;
    channel.gainNode.gain.setValueAtTime(GAIN_MIN, now);
    channel.gainNode.gain.exponentialRampToValueAtTime(
      1.0,
      now + CROSSFADE_DURATION_SECONDS,
    );
  }

  private ensureContextRunning(): void {
    if (this.audioContext?.state === "suspended") {
      void this.audioContext.resume();
    }
  }

  private setupAutoplayUnlock(): void {
    if (this.isUnlocked || typeof window === "undefined") return;

    const unlockHandler = () => {
      this.isUnlocked = true;
      this.ensureContextRunning();
      window.removeEventListener("pointerdown", unlockHandler);
      window.removeEventListener("keydown", unlockHandler);
    };

    window.addEventListener("pointerdown", unlockHandler, { once: true });
    window.addEventListener("keydown", unlockHandler, { once: true });
  }

  private loadSavedPreferences(): void {
    if (typeof localStorage === "undefined") return;
    const savedVol = localStorage.getItem(STORAGE_KEY_VOLUME);
    if (savedVol !== null) {
      const parsed = parseFloat(savedVol);
      if (!isNaN(parsed)) this.volume = Math.max(0.0, Math.min(1.0, parsed));
    }
    const savedMute = localStorage.getItem(STORAGE_KEY_MUTED);
    if (savedMute !== null) {
      this.isMuted = savedMute === "true";
    }
  }

  private savePreferences(): void {
    if (typeof localStorage === "undefined") return;
    localStorage.setItem(STORAGE_KEY_VOLUME, this.volume.toString());
    localStorage.setItem(STORAGE_KEY_MUTED, this.isMuted.toString());
  }
}

export const ambientSoundtrack = new AmbientSoundtrackController();
