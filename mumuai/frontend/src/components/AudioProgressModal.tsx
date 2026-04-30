import React, { useState, useEffect, useRef } from 'react';
import { Modal, Progress, List } from 'antd';
import { CheckCircleOutlined, SyncOutlined, SoundOutlined } from '@ant-design/icons';
import type { AudioSSEEvent } from '../types';

interface Props {
  open: boolean;
  chapterId: string;
  bgmStyle?: string;
  onClose: () => void;
  onDone: (filePath: string) => void;
}

const stepNames = ['解析对话', '生成语音', '背景音乐', '混音合成'];

const AudioProgressModal: React.FC<Props> = ({
  open,
  chapterId,
  bgmStyle,
  onClose,
  onDone,
}) => {
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState('');
  const [stepIndex, setStepIndex] = useState(0);
  // 使用 ref 避免闭包问题
  const stepRef = useRef(0);

  const [steps, setSteps] = useState<
    { name: string; status: 'wait' | 'process' | 'finish' | 'error' }[]
  >(stepNames.map((name) => ({ name, status: 'wait' })));

  useEffect(() => {
    if (!open || !chapterId) return;

    const url = `/api/chapters/${chapterId}/audio/stream?bgm_style=${encodeURIComponent(
      bgmStyle || 'ancient children adventure'
    )}`;
    const eventSource = new EventSource(url);

    eventSource.onmessage = (event: MessageEvent) => {
      const data: AudioSSEEvent = JSON.parse(event.data);

      if (data.type === 'progress') {
        setProgress(data.progress || 0);
        setMessage(data.message || '');

        const newStepIndex = stepNames.findIndex((name) => {
          if (data.step === 'parsing') return name === '解析对话';
          if (data.step === 'tts') return name === '生成语音';
          if (data.step === 'bgm') return name === '背景音乐';
          if (data.step === 'mixing') return name === '混音合成';
          if (data.step === 'done') return name === '混音合成';
          return false;
        });

        if (newStepIndex >= 0) {
          setStepIndex(newStepIndex);
          stepRef.current = newStepIndex;
          setSteps((prev) =>
            prev.map((s, i) => {
              if (i < newStepIndex) return { ...s, status: 'finish' as const };
              if (i === newStepIndex) return { ...s, status: 'process' as const };
              return s;
            })
          );
        }
      }

      if (data.type === 'done' || data.type === 'result') {
        onDone(data.file_path || '');
        eventSource.close();
      }

      if (data.type === 'error') {
        setSteps((prev) =>
          prev.map((s, i) =>
            i === stepRef.current ? { ...s, status: 'error' as const } : s
          )
        );
        setMessage(data.message || '生成失败');
        eventSource.close();
      }
    };

    return () => eventSource.close();
  }, [open, chapterId, bgmStyle]);

  return (
    <Modal
      title="生成播客音频"
      open={open}
      onCancel={onClose}
      footer={null}
      width={480}
    >
      <Progress
        percent={progress}
        status={progress === 100 ? 'success' : 'active'}
        style={{ marginBottom: 16 }}
      />
      <div style={{ marginBottom: 16, color: '#666' }}>{message || '准备中...'}</div>
      <List
        size="small"
        dataSource={steps}
        renderItem={(item) => (
          <List.Item>
            {item.status === 'finish' && (
              <CheckCircleOutlined style={{ color: '#52c41a', marginRight: 8 }} />
            )}
            {item.status === 'process' && (
              <SyncOutlined spin style={{ color: '#1890ff', marginRight: 8 }} />
            )}
            {item.status === 'error' && (
              <SoundOutlined style={{ color: '#ff4d4f', marginRight: 8 }} />
            )}
            {item.status === 'wait' && (
              <SoundOutlined style={{ color: '#d9d9d9', marginRight: 8 }} />
            )}
            {item.name}
          </List.Item>
        )}
      />
    </Modal>
  );
};

export default AudioProgressModal;
