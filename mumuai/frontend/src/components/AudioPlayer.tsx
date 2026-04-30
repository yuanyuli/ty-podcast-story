import React, { useRef, useState } from 'react';
import { Button, Space, Typography } from 'antd';
import { PlayCircleOutlined, PauseCircleOutlined, DownloadOutlined } from '@ant-design/icons';

interface Props {
  src: string;
  title: string;
  duration: number;
  onDownload: () => void;
}

const formatDuration = (seconds: number): string => {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
};

const AudioPlayer: React.FC<Props> = ({ src, title, duration, onDownload }) => {
  const [playing, setPlaying] = useState(false);
  const audioRef = useRef<HTMLAudioElement>(null);

  const togglePlay = () => {
    if (playing) {
      audioRef.current?.pause();
    } else {
      audioRef.current?.play();
    }
    setPlaying(!playing);
  };

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '8px 0' }}>
      <Button
        type="primary"
        shape="circle"
        icon={playing ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
        onClick={togglePlay}
      />
      <div style={{ flex: 1 }}>
        <Typography.Text strong>{title}</Typography.Text>
        <br />
        <Typography.Text type="secondary">{formatDuration(duration)}</Typography.Text>
      </div>
      <Button icon={<DownloadOutlined />} onClick={onDownload}>
        下载
      </Button>
      <audio
        ref={audioRef}
        src={src}
        onEnded={() => setPlaying(false)}
        style={{ display: 'none' }}
      />
    </div>
  );
};

export default AudioPlayer;
