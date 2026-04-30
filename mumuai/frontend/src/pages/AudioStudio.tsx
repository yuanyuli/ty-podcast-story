import React, { useState, useEffect } from 'react';
import { Card, Row, Col, Tag, Typography } from 'antd';
import { useParams } from 'react-router-dom';
import AudioPlayer from '../components/AudioPlayer';
import AudioProgressModal from '../components/AudioProgressModal';
import { audioApi } from '../services/api';
import { chaptersApi } from '../services/api';
import type { AudioFile, BGMPreset } from '../types';

const AudioStudio: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const [chapters, setChapters] = useState<any[]>([]);
  const [audioFiles, setAudioFiles] = useState<Record<string, AudioFile>>({});
  const [bgmPresets, setBgmPresets] = useState<BGMPreset[]>([]);
  const [modalChapterId, setModalChapterId] = useState<string | null>(null);
  const [bgmStyle, setBgmStyle] = useState('ancient children adventure');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!projectId) return;
    chaptersApi.getList(projectId).then((res: any) => {
      setChapters(res.data.items || []);
    });
    audioApi.getBGMPresets().then((res: any) => {
      setBgmPresets(res.data.presets || []);
    });
  }, [projectId]);

  const handleGenerate = (chapterId: string) => {
    setModalChapterId(chapterId);
  };

  const handleAudioDone = (filePath: string) => {
    if (modalChapterId) {
      audioApi.getStatus(modalChapterId).then((res: any) => {
        setAudioFiles((prev) => ({
          ...prev,
          [modalChapterId]: {
            id: res.data.id,
            chapter_id: modalChapterId,
            file_path: filePath,
            duration_seconds: res.data.duration_seconds || 0,
            file_size_bytes: 0,
            format: 'mp3',
            created_at: new Date().toISOString(),
          },
        }));
      });
    }
    setModalChapterId(null);
  };

  return (
    <div style={{ padding: 24 }}>
      <Typography.Title level={3}>音频工作室</Typography.Title>

      {bgmPresets.length > 0 && (
        <Card title="BGM 预设风格" size="small" style={{ marginBottom: 24 }}>
          <Row gutter={[8, 8]}>
            {bgmPresets.map((preset) => (
              <Col key={preset.id}>
                <Tag
                  color={bgmStyle === preset.tags[0] ? 'blue' : 'default'}
                  style={{ cursor: 'pointer' }}
                  onClick={() => setBgmStyle(preset.tags[0] || preset.style)}
                >
                  {preset.name}
                </Tag>
              </Col>
            ))}
          </Row>
        </Card>
      )}

      <Card title="剧集列表">
        {chapters.map((ch: any) => (
          <div
            key={ch.id}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '12px 0',
              borderBottom: '1px solid #f0f0f0',
            }}
          >
            <div>
              <Typography.Text strong>
                第{ch.chapter_number}集 {ch.title}
              </Typography.Text>
              {ch.status === 'completed' && (
                <Tag color="green" style={{ marginLeft: 8 }}>
                  已生成内容
                </Tag>
              )}
            </div>
            <div>
              {audioFiles[ch.id] ? (
                <AudioPlayer
                  src={`/api/chapters/${ch.id}/audio/download`}
                  title={`第${ch.chapter_number}集 - ${ch.title}`}
                  duration={audioFiles[ch.id].duration_seconds}
                  onDownload={() => {
                    window.open(`/api/chapters/${ch.id}/audio/download`);
                  }}
                />
              ) : (
                <a onClick={() => handleGenerate(ch.id)} style={{ cursor: 'pointer' }}>
                  生成音频
                </a>
              )}
            </div>
          </div>
        ))}
        {chapters.length === 0 && (
          <Typography.Text type="secondary">暂无剧集</Typography.Text>
        )}
      </Card>

      <AudioProgressModal
        open={!!modalChapterId}
        chapterId={modalChapterId || ''}
        bgmStyle={bgmStyle}
        onClose={() => setModalChapterId(null)}
        onDone={handleAudioDone}
      />
    </div>
  );
};

export default AudioStudio;
