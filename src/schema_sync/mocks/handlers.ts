import { http, HttpResponse } from 'msw';
import type { paths, components } from '../types/api';

type Task = components['schemas']['Task'];

// Schema-Driven: 型定義を用いてモックデータを安全に構築
const mockTasks: Task[] = [
  {
    id: "t-001",
    title: "Implement Schema-Driven Dev",
    description: "Generate types using openapi-typescript",
    status: "DONE"
  },
  {
    id: "t-002",
    title: "Setup MSW",
    description: "Create robust mock server",
    status: "IN_PROGRESS"
  }
];

export const handlers = [
  // 型安全なAPIエンドポイント定義
  http.get('http://api.example.com/v1/tasks', () => {
    // ResponseBodyも自動生成された型(paths)に準拠させるように実装可能
    return HttpResponse.json(mockTasks);
  }),
  
  http.get('http://api.example.com/v1/tasks/:taskId', ({ params }) => {
    const task = mockTasks.find(t => t.id === params.taskId);
    if (!task) {
      return new HttpResponse(null, { status: 404 });
    }
    return HttpResponse.json(task);
  }),
];
