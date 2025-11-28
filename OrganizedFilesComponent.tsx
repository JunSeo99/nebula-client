/**
 * Organized Files UI 컴포넌트
 *
 * 사용자가 폴더를 선택하고 파일을 정리할 수 있는 React 컴포넌트
 */

import React, { useState } from "react";
import {
  inspectAndOrganizeFolder,
  inspectAndOrganizeBatch,
} from "./frontend-client";

interface OrganizeState {
  loading: boolean;
  error: string | null;
  success: boolean;
  result?: {
    directory: string;
    totalFiles: number;
    savedCount: number;
    updatedCount: number;
    failedCount: number;
  };
}

/**
 * 파일 정리 컴포넌트
 *
 * 기능:
 * - 폴더 경로 입력
 * - 단일 처리 (소규모 폴더)
 * - 배치 처리 (대용량 폴더)
 * - 처리 결과 표시
 */
export function OrganizedFilesComponent() {
  const [folderPath, setFolderPath] = useState("");
  const [state, setState] = useState<OrganizeState>({
    loading: false,
    error: null,
    success: false,
  });

  // 단일 폴더 처리
  const handleOrganize = async () => {
    if (!folderPath.trim()) {
      setState((prev) => ({ ...prev, error: "폴더 경로를 입력해주세요" }));
      return;
    }

    setState({ loading: true, error: null, success: false });

    try {
      const result = await inspectAndOrganizeFolder(folderPath);

      if (result.status === "success") {
        setState({
          loading: false,
          error: null,
          success: true,
          result: {
            directory: result.directory,
            totalFiles: result.totalFiles,
            savedCount: result.savedCount,
            updatedCount: result.updatedCount,
            failedCount: result.failedCount,
          },
        });
      } else {
        setState({
          loading: false,
          error: result.message,
          success: false,
        });
      }
    } catch (err) {
      setState({
        loading: false,
        error: err instanceof Error ? err.message : "알 수 없는 에러가 발생했습니다",
        success: false,
      });
    }
  };

  // 배치 폴더 처리
  const handleOrganizeBatch = async () => {
    if (!folderPath.trim()) {
      setState((prev) => ({ ...prev, error: "폴더 경로를 입력해주세요" }));
      return;
    }

    setState({ loading: true, error: null, success: false });

    try {
      const result = await inspectAndOrganizeBatch(folderPath);

      setState({
        loading: false,
        error: null,
        success: true,
        result: {
          directory: result.directory,
          totalFiles: result.totalFiles,
          savedCount: 0,
          updatedCount: 0,
          failedCount: 0,
        },
      });

      // 배치 처리 안내
      alert(
        `배치 처리가 시작되었습니다.\n` +
          `총 ${result.totalFiles}개 파일을 ${result.totalBatches}개 배치로 처리 중입니다.`
      );
    } catch (err) {
      setState({
        loading: false,
        error: err instanceof Error ? err.message : "알 수 없는 에러가 발생했습니다",
        success: false,
      });
    }
  };

  // 폴더 선택 (네이티브 다이얼로그)
  const handleSelectFolder = async () => {
    // Electron IPC 또는 웹 File API 사용
    // 예: window.electronAPI.selectFolder()
    alert("폴더 선택 기능을 구현해주세요");
  };

  return (
    <div style={styles.container}>
      <h2 style={styles.title}>파일 정리</h2>

      {/* 폴더 경로 입력 */}
      <div style={styles.inputGroup}>
        <label style={styles.label}>폴더 경로:</label>
        <div style={styles.inputWrapper}>
          <input
            type="text"
            value={folderPath}
            onChange={(e) => setFolderPath(e.target.value)}
            placeholder="/Users/jun/Documents/MyFolder"
            style={styles.input}
            disabled={state.loading}
          />
          <button
            onClick={handleSelectFolder}
            style={styles.browseButton}
            disabled={state.loading}
          >
            폴더 선택
          </button>
        </div>
      </div>

      {/* 처리 버튼 */}
      <div style={styles.buttonGroup}>
        <button
          onClick={handleOrganize}
          style={{
            ...styles.button,
            ...styles.primaryButton,
            opacity: state.loading ? 0.6 : 1,
          }}
          disabled={state.loading}
        >
          {state.loading ? "처리 중..." : "파일 정리 (단일)"}
        </button>
        <button
          onClick={handleOrganizeBatch}
          style={{
            ...styles.button,
            ...styles.secondaryButton,
            opacity: state.loading ? 0.6 : 1,
          }}
          disabled={state.loading}
        >
          {state.loading ? "처리 중..." : "파일 정리 (배치)"}
        </button>
      </div>

      {/* 에러 메시지 */}
      {state.error && (
        <div style={styles.errorBox}>
          <strong>❌ 에러:</strong> {state.error}
        </div>
      )}

      {/* 성공 메시지 */}
      {state.success && state.result && (
        <div style={styles.successBox}>
          <strong>✅ 완료!</strong>
          <div style={styles.resultDetails}>
            <p>
              <strong>디렉토리:</strong> {state.result.directory}
            </p>
            <p>
              <strong>총 파일:</strong> {state.result.totalFiles}개
            </p>
            <p>
              <strong>저장:</strong> {state.result.savedCount}개
            </p>
            <p>
              <strong>업데이트:</strong> {state.result.updatedCount}개
            </p>
            {state.result.failedCount > 0 && (
              <p style={styles.failedCount}>
                <strong>실패:</strong> {state.result.failedCount}개
              </p>
            )}
          </div>
        </div>
      )}

      {/* 정보 */}
      <div style={styles.infoBox}>
        <h4>💡 사용 가이드:</h4>
        <ul style={styles.infoList}>
          <li>
            <strong>단일 처리:</strong> 100개 미만의 파일을 가진 폴더에 권장
          </li>
          <li>
            <strong>배치 처리:</strong> 100개 이상의 파일을 가진 폴더에 권장
            (비동기 처리)
          </li>
          <li>절대 경로를 사용해주세요</li>
          <li>
            키워드는 파일 타입(PDF, 이미지, 스프레드시트)에 따라 자동 추출됩니다
          </li>
        </ul>
      </div>
    </div>
  );
}

// 스타일
const styles = {
  container: {
    maxWidth: "600px",
    margin: "20px auto",
    padding: "20px",
    border: "1px solid #ddd",
    borderRadius: "8px",
    fontFamily: "sans-serif",
  },
  title: {
    fontSize: "24px",
    marginBottom: "20px",
    color: "#333",
  },
  inputGroup: {
    marginBottom: "20px",
  },
  label: {
    display: "block",
    marginBottom: "8px",
    fontWeight: "bold",
    color: "#555",
  },
  inputWrapper: {
    display: "flex",
    gap: "10px",
  },
  input: {
    flex: 1,
    padding: "10px",
    border: "1px solid #ccc",
    borderRadius: "4px",
    fontSize: "14px",
    fontFamily: "monospace",
  },
  browseButton: {
    padding: "10px 15px",
    backgroundColor: "#f0f0f0",
    border: "1px solid #ccc",
    borderRadius: "4px",
    cursor: "pointer",
    fontSize: "14px",
  },
  buttonGroup: {
    display: "flex",
    gap: "10px",
    marginBottom: "20px",
  },
  button: {
    flex: 1,
    padding: "12px",
    border: "none",
    borderRadius: "4px",
    fontSize: "14px",
    fontWeight: "bold",
    cursor: "pointer",
    transition: "background-color 0.2s",
  },
  primaryButton: {
    backgroundColor: "#007bff",
    color: "white",
  },
  secondaryButton: {
    backgroundColor: "#28a745",
    color: "white",
  },
  errorBox: {
    padding: "12px",
    marginBottom: "20px",
    backgroundColor: "#f8d7da",
    border: "1px solid #f5c6cb",
    borderRadius: "4px",
    color: "#721c24",
  },
  successBox: {
    padding: "12px",
    marginBottom: "20px",
    backgroundColor: "#d4edda",
    border: "1px solid #c3e6cb",
    borderRadius: "4px",
    color: "#155724",
  },
  resultDetails: {
    marginTop: "10px",
    fontSize: "14px",
  },
  failedCount: {
    color: "#d32f2f",
  },
  infoBox: {
    padding: "12px",
    backgroundColor: "#e7f3ff",
    border: "1px solid #b3d9ff",
    borderRadius: "4px",
    fontSize: "13px",
    color: "#004085",
  },
  infoList: {
    margin: "10px 0 0 0",
    paddingLeft: "20px",
  },
} as const;
