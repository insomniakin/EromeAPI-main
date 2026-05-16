import { useEffect, useMemo, useRef, useState } from 'react';

type Props = {
  src: string;
  poster?: string | null;
  title: string;
};

function formatTime(time: number) {
  if (!Number.isFinite(time) || time < 0) return '0:00';
  const totalSeconds = Math.floor(time);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
  }
  return `${minutes}:${String(seconds).padStart(2, '0')}`;
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

export default function VideoPlayerClone({ src, poster, title }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const timelinePreviewRef = useRef<HTMLDivElement | null>(null);
  const timelineProgressRef = useRef<HTMLDivElement | null>(null);
  const timelineThumbRef = useRef<HTMLDivElement | null>(null);
  const timelineTooltipRef = useRef<HTMLDivElement | null>(null);
  const hideTimerRef = useRef<number | null>(null);

  const [isPaused, setIsPaused] = useState(true);
  const [isMuted, setIsMuted] = useState(false);
  const [volume, setVolume] = useState(1);
  const [duration, setDuration] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [controlsVisible, setControlsVisible] = useState(true);
  const [scrubPercent, setScrubPercent] = useState(0);
  const [isTheater, setIsTheater] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isMiniPlayer, setIsMiniPlayer] = useState(false);

  const progressPercent = useMemo(() => {
    if (!duration) return 0;
    return clamp(currentTime / duration, 0, 1);
  }, [currentTime, duration]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    video.load();
    setCurrentTime(0);
    setDuration(0);
    setPlaybackRate(1);
    setIsPaused(true);
  }, [src]);

  useEffect(() => {
    const progressWidth = `${progressPercent * 100}%`;
    const scrubWidth = `${scrubPercent * 100}%`;

    if (timelinePreviewRef.current) timelinePreviewRef.current.style.width = scrubWidth;
    if (timelineProgressRef.current) timelineProgressRef.current.style.width = progressWidth;
    if (timelineThumbRef.current) timelineThumbRef.current.style.left = progressWidth;
    if (timelineTooltipRef.current) timelineTooltipRef.current.style.left = scrubWidth;
  }, [progressPercent, scrubPercent]);

  useEffect(() => {
    const onFullscreen = () => {
      setIsFullscreen(Boolean(document.fullscreenElement));
    };
    document.addEventListener('fullscreenchange', onFullscreen);
    return () => document.removeEventListener('fullscreenchange', onFullscreen);
  }, []);

  useEffect(() => {
    return () => {
      if (hideTimerRef.current) {
        window.clearTimeout(hideTimerRef.current);
      }
    };
  }, []);

  function scheduleHideControls() {
    if (hideTimerRef.current) window.clearTimeout(hideTimerRef.current);
    hideTimerRef.current = window.setTimeout(() => {
      if (!videoRef.current?.paused) setControlsVisible(false);
    }, 1800);
  }

  function revealControls() {
    setControlsVisible(true);
    scheduleHideControls();
  }

  function togglePlayPause() {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused) {
      void video.play();
    } else {
      video.pause();
    }
  }

  function toggleMute() {
    const video = videoRef.current;
    if (!video) return;
    video.muted = !video.muted;
    setIsMuted(video.muted);
  }

  function handleVolume(value: number) {
    const video = videoRef.current;
    if (!video) return;
    const nextVolume = clamp(value, 0, 1);
    video.volume = nextVolume;
    video.muted = nextVolume === 0;
    setVolume(nextVolume);
    setIsMuted(video.muted);
  }

  function skip(seconds: number) {
    const video = videoRef.current;
    if (!video) return;
    video.currentTime = clamp(video.currentTime + seconds, 0, duration || video.duration || 0);
  }

  function changePlaybackRate() {
    const video = videoRef.current;
    if (!video) return;
    const next = playbackRate >= 2 ? 0.5 : Number((playbackRate + 0.25).toFixed(2));
    video.playbackRate = next;
    setPlaybackRate(next);
  }

  async function toggleMiniPlayer() {
    const video = videoRef.current;
    if (!video || !document.pictureInPictureEnabled) return;
    try {
      if (document.pictureInPictureElement) {
        await document.exitPictureInPicture();
        setIsMiniPlayer(false);
      } else {
        await video.requestPictureInPicture();
        setIsMiniPlayer(true);
      }
    } catch {
      setIsMiniPlayer(false);
    }
  }

  async function toggleFullscreen() {
    const container = containerRef.current;
    if (!container) return;
    if (document.fullscreenElement) {
      await document.exitFullscreen();
      setIsFullscreen(false);
    } else {
      await container.requestFullscreen();
      setIsFullscreen(true);
    }
  }

  function seekFromPointer(clientX: number) {
    const timeline = containerRef.current?.querySelector<HTMLElement>('.yt-clone-timeline');
    const video = videoRef.current;
    if (!timeline || !video || !duration) return;
    const rect = timeline.getBoundingClientRect();
    const percent = clamp((clientX - rect.left) / rect.width, 0, 1);
    video.currentTime = percent * duration;
    setScrubPercent(percent);
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    const tag = (document.activeElement?.tagName || '').toLowerCase();
    if (tag === 'input' || tag === 'textarea') return;
    switch (event.key.toLowerCase()) {
      case ' ':
      case 'k':
        event.preventDefault();
        togglePlayPause();
        break;
      case 'm':
        toggleMute();
        break;
      case 'f':
        void toggleFullscreen();
        break;
      case 't':
        setIsTheater((value) => !value);
        break;
      case 'i':
        void toggleMiniPlayer();
        break;
      case 'j':
      case 'arrowleft':
        skip(-5);
        break;
      case 'l':
      case 'arrowright':
        skip(5);
        break;
    }
  }

  return (
    <div
      ref={containerRef}
      tabIndex={0}
      className={[
        'yt-clone-player',
        isPaused ? 'paused' : 'playing',
        controlsVisible ? 'show-controls' : '',
        isTheater ? 'theater' : '',
        isFullscreen ? 'full-screen' : '',
        isMiniPlayer ? 'mini-player' : '',
      ].join(' ')}
      onMouseMove={revealControls}
      onMouseLeave={() => !videoRef.current?.paused && setControlsVisible(false)}
      onFocus={revealControls}
      onKeyDown={onKeyDown}
      data-volume-level={isMuted || volume === 0 ? 'muted' : volume < 0.5 ? 'low' : 'high'}
    >
      <video
        ref={videoRef}
        src={src}
        poster={poster ?? undefined}
        playsInline
        preload="metadata"
        onClick={togglePlayPause}
        onLoadedMetadata={(event) => {
          setDuration(event.currentTarget.duration || 0);
          setCurrentTime(event.currentTarget.currentTime || 0);
          setVolume(event.currentTarget.volume);
        }}
        onTimeUpdate={(event) => setCurrentTime(event.currentTarget.currentTime)}
        onPlay={() => {
          setIsPaused(false);
          scheduleHideControls();
        }}
        onPause={() => {
          setIsPaused(true);
          setControlsVisible(true);
        }}
        onVolumeChange={(event) => {
          setVolume(event.currentTarget.volume);
          setIsMuted(event.currentTarget.muted);
        }}
      />

      <div className="yt-clone-shadow" />

      <div className="yt-clone-controls">
        <div
          className="yt-clone-timeline"
          onClick={(event) => seekFromPointer(event.clientX)}
          onMouseMove={(event) => {
            const timeline = event.currentTarget;
            const rect = timeline.getBoundingClientRect();
            const percent = clamp((event.clientX - rect.left) / rect.width, 0, 1);
            setScrubPercent(percent);
          }}
        >
          <div className="yt-clone-timeline-track" />
          <div ref={timelinePreviewRef} className="yt-clone-timeline-preview" />
          <div ref={timelineProgressRef} className="yt-clone-timeline-progress" />
          <div ref={timelineThumbRef} className="yt-clone-thumb" />
          <div ref={timelineTooltipRef} className="yt-clone-tooltip">
            {formatTime((duration || 0) * scrubPercent)}
          </div>
        </div>

        <div className="yt-clone-bar">
          <div className="yt-clone-left-controls">
            <button type="button" className="yt-clone-icon-btn" onClick={togglePlayPause} aria-label="Play or pause">
              {isPaused ? '▶' : '❚❚'}
            </button>
            <div className="yt-clone-volume-group">
              <button type="button" className="yt-clone-icon-btn" onClick={toggleMute} aria-label="Mute">
                {isMuted || volume === 0 ? '🔇' : volume < 0.5 ? '🔉' : '🔊'}
              </button>
              <input
                className="yt-clone-volume-slider"
                type="range"
                min={0}
                max={1}
                step="any"
                value={isMuted ? 0 : volume}
                onChange={(event) => handleVolume(Number(event.target.value))}
                aria-label="Volume"
              />
            </div>
            <div className="yt-clone-time-display">
              <span>{formatTime(currentTime)}</span>
              <span>/</span>
              <span>{formatTime(duration)}</span>
            </div>
          </div>

          <div className="yt-clone-right-controls">
            <button type="button" className="yt-clone-pill-btn" onClick={changePlaybackRate} aria-label="Playback speed">
              {playbackRate}x
            </button>
            <button type="button" className="yt-clone-icon-btn" onClick={() => setIsTheater((value) => !value)} aria-label="Theater mode">
              ◫
            </button>
            <button
              type="button"
              className="yt-clone-icon-btn"
              onClick={() => void toggleMiniPlayer()}
              aria-label="Picture in picture"
              disabled={!document.pictureInPictureEnabled}
            >
              ⧉
            </button>
            <button type="button" className="yt-clone-icon-btn" onClick={() => void toggleFullscreen()} aria-label="Fullscreen">
              {isFullscreen ? '🡽' : '⛶'}
            </button>
          </div>
        </div>
      </div>

      <div className="yt-clone-titlebar">
        <div className="yt-clone-kicker">Inspired by the linked YouTube-style player clone</div>
        <div className="yt-clone-title">{title}</div>
      </div>
    </div>
  );
}
