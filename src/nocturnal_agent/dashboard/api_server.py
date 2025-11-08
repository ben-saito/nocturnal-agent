"""
進捗ダッシュボード用APIサーバー
FastAPIを使用してエージェントの進捗状況を提供
"""

import json
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from collections import defaultdict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from ..execution.implementation_task_manager import (
    ImplementationTaskManager,
    TaskStatus,
    TaskPriority,
    ImplementationTask
)
from ..log_system.structured_logger import StructuredLogger, LogLevel, LogCategory
from ..config.config_manager import ConfigManager


class TaskResponse(BaseModel):
    """タスクレスポンスモデル"""
    task_id: str
    title: str
    description: str
    priority: str
    status: str
    estimated_hours: float
    created_at: str
    updated_at: str
    started_at: Optional[str] = None
    assigned_to: Optional[str] = None
    dependencies: List[str]
    technical_requirements: List[str]
    acceptance_criteria: List[str]
    execution_log: List[Dict[str, Any]]


class AgentProgressResponse(BaseModel):
    """エージェント進捗レスポンスモデル"""
    agent_name: str
    total_tasks: int
    completed_tasks: int
    in_progress_tasks: int
    pending_tasks: int
    failed_tasks: int
    progress_percentage: float
    tasks: List[TaskResponse]


class DashboardStatsResponse(BaseModel):
    """ダッシュボード統計レスポンスモデル"""
    total_tasks: int
    completed_tasks: int
    in_progress_tasks: int
    pending_tasks: int
    failed_tasks: int
    overall_progress: float
    agents: List[AgentProgressResponse]
    recent_logs: List[Dict[str, Any]]


class DashboardAPIServer:
    """進捗ダッシュボードAPIサーバー"""
    
    def __init__(self, workspace_path: str, config_path: Optional[str] = None):
        self.workspace_path = Path(workspace_path)
        self.app = FastAPI(title="Nocturnal Agent Dashboard API")
        
        # CORS設定
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # ロガーとタスクマネージャーの初期化
        self.logger = StructuredLogger(
            log_dir=self.workspace_path / "logs",
            component="dashboard_api"
        )
        
        # 設定マネージャーの初期化
        if config_path:
            self.config_manager = ConfigManager(config_path)
        else:
            config_file = self.workspace_path / "config" / "nocturnal-agent.yaml"
            if config_file.exists():
                self.config_manager = ConfigManager(str(config_file))
            else:
                self.config_manager = None
        
        # タスクマネージャーの初期化
        self.task_manager = ImplementationTaskManager(
            workspace_path=str(self.workspace_path),
            logger=self.logger
        )
        
        # レガシータスクファイル（nocturnal_tasks/tasks.json）も読み込む
        self._load_legacy_tasks()
        
        # APIエンドポイントの設定
        self._setup_routes()
    
    def _load_legacy_tasks(self):
        """レガシータスクファイル（nocturnal_tasks/tasks.json）を読み込む"""
        legacy_tasks_file = self.workspace_path / "nocturnal_tasks" / "tasks.json"
        
        if not legacy_tasks_file.exists():
            return
        
        try:
            with open(legacy_tasks_file, 'r', encoding='utf-8') as f:
                legacy_tasks = json.load(f)
            
            # 配列形式のレガシータスクを処理
            if isinstance(legacy_tasks, list):
                for task_data in legacy_tasks:
                    # レガシータスクを新しい形式に変換
                    task_id = f"legacy_{task_data.get('id', 'unknown')}"
                    
                    # 既に存在する場合はスキップ
                    if task_id in self.task_manager.tasks:
                        continue
                    
                    # 新しいタスク形式に変換
                    from datetime import datetime
                    new_task = ImplementationTask(
                        task_id=task_id,
                        title=task_data.get('description', 'Legacy Task')[:100],
                        description=task_data.get('description', ''),
                        priority=TaskPriority(task_data.get('priority', 'MEDIUM').upper()),
                        status=TaskStatus(task_data.get('status', 'PENDING').upper()),
                        dependencies=[],
                        estimated_hours=task_data.get('estimated_hours', 1.0),
                        technical_requirements=task_data.get('requirements', []),
                        acceptance_criteria=[],
                        created_at=datetime.fromisoformat(task_data.get('created_at', datetime.now().isoformat())),
                        updated_at=datetime.fromisoformat(task_data.get('created_at', datetime.now().isoformat())),
                        assigned_to=None
                    )
                    
                    self.task_manager.tasks[task_id] = new_task
            
            self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                          f"📋 レガシータスクファイルから {len(legacy_tasks) if isinstance(legacy_tasks, list) else 0}個のタスクを読み込み")
        except Exception as e:
            self.logger.log(LogLevel.WARNING, LogCategory.SYSTEM, 
                          f"レガシータスク読み込みエラー: {e}")
    
    def _setup_routes(self):
        """APIルートを設定"""
        
        @self.app.get("/", response_class=HTMLResponse)
        async def root():
            """ルートエンドポイント - ダッシュボードHTMLを返す"""
            return self._get_dashboard_html()
        
        @self.app.get("/api/stats", response_model=DashboardStatsResponse)
        async def get_stats():
            """全体統計を取得"""
            try:
                stats = await self._get_dashboard_stats()
                return stats
            except Exception as e:
                self.logger.log(LogLevel.ERROR, LogCategory.API_CALL, 
                              f"統計取得エラー: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/tasks", response_model=List[TaskResponse])
        async def get_tasks(status: Optional[str] = None):
            """タスク一覧を取得"""
            try:
                tasks = await self._get_tasks(status)
                return tasks
            except Exception as e:
                self.logger.log(LogLevel.ERROR, LogCategory.API_CALL, 
                              f"タスク取得エラー: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/agents", response_model=List[AgentProgressResponse])
        async def get_agents():
            """エージェント別進捗を取得"""
            try:
                agents = await self._get_agent_progress()
                return agents
            except Exception as e:
                self.logger.log(LogLevel.ERROR, LogCategory.API_CALL, 
                              f"エージェント進捗取得エラー: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/agents/{agent_name}", response_model=AgentProgressResponse)
        async def get_agent(agent_name: str):
            """特定エージェントの進捗を取得"""
            try:
                agent = await self._get_agent_progress(agent_name)
                if not agent:
                    raise HTTPException(status_code=404, detail="エージェントが見つかりません")
                return agent[0]
            except HTTPException:
                raise
            except Exception as e:
                self.logger.log(LogLevel.ERROR, LogCategory.API_CALL, 
                              f"エージェント進捗取得エラー: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/logs")
        async def get_logs(limit: int = 100, level: Optional[str] = None):
            """ログを取得"""
            try:
                logs = await self._get_recent_logs(limit, level)
                return logs
            except Exception as e:
                self.logger.log(LogLevel.ERROR, LogCategory.API_CALL, 
                              f"ログ取得エラー: {e}")
                raise HTTPException(status_code=500, detail=str(e))
    
    async def _get_tasks(self, status_filter: Optional[str] = None) -> List[TaskResponse]:
        """タスク一覧を取得"""
        tasks = []
        
        for task in self.task_manager.tasks.values():
            if status_filter and task.status.value != status_filter.upper():
                continue
            
            task_dict = {
                "task_id": task.task_id,
                "title": task.title,
                "description": task.description,
                "priority": task.priority.value,
                "status": task.status.value,
                "estimated_hours": task.estimated_hours,
                "created_at": task.created_at.isoformat(),
                "updated_at": task.updated_at.isoformat(),
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "assigned_to": task.assigned_to,
                "dependencies": task.dependencies,
                "technical_requirements": task.technical_requirements,
                "acceptance_criteria": task.acceptance_criteria,
                "execution_log": task.execution_log
            }
            tasks.append(TaskResponse(**task_dict))
        
        return tasks
    
    async def _get_agent_progress(self, agent_name: Optional[str] = None) -> List[AgentProgressResponse]:
        """エージェント別進捗を取得"""
        # タスクをエージェント別にグループ化
        agent_tasks = defaultdict(list)
        
        for task in self.task_manager.tasks.values():
            # assigned_toからエージェント名を取得、なければ"unassigned"
            agent = task.assigned_to or "unassigned"
            agent_tasks[agent].append(task)
        
        agents = []
        
        for agent, tasks in agent_tasks.items():
            if agent_name and agent != agent_name:
                continue
            
            total = len(tasks)
            completed = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)
            in_progress = sum(1 for t in tasks if t.status == TaskStatus.IN_PROGRESS)
            pending = sum(1 for t in tasks if t.status in [TaskStatus.PENDING, TaskStatus.APPROVED])
            failed = sum(1 for t in tasks if t.status == TaskStatus.FAILED)
            
            progress = (completed / total * 100) if total > 0 else 0.0
            
            task_responses = []
            for task in tasks:
                task_dict = {
                    "task_id": task.task_id,
                    "title": task.title,
                    "description": task.description,
                    "priority": task.priority.value,
                    "status": task.status.value,
                    "estimated_hours": task.estimated_hours,
                    "created_at": task.created_at.isoformat(),
                    "updated_at": task.updated_at.isoformat(),
                    "started_at": task.started_at.isoformat() if task.started_at else None,
                    "assigned_to": task.assigned_to,
                    "dependencies": task.dependencies,
                    "technical_requirements": task.technical_requirements,
                    "acceptance_criteria": task.acceptance_criteria,
                    "execution_log": task.execution_log
                }
                task_responses.append(TaskResponse(**task_dict))
            
            agents.append(AgentProgressResponse(
                agent_name=agent,
                total_tasks=total,
                completed_tasks=completed,
                in_progress_tasks=in_progress,
                pending_tasks=pending,
                failed_tasks=failed,
                progress_percentage=progress,
                tasks=task_responses
            ))
        
        return agents
    
    async def _get_dashboard_stats(self) -> DashboardStatsResponse:
        """ダッシュボード統計を取得"""
        all_tasks = list(self.task_manager.tasks.values())
        
        total = len(all_tasks)
        completed = sum(1 for t in all_tasks if t.status == TaskStatus.COMPLETED)
        in_progress = sum(1 for t in all_tasks if t.status == TaskStatus.IN_PROGRESS)
        pending = sum(1 for t in all_tasks if t.status in [TaskStatus.PENDING, TaskStatus.APPROVED])
        failed = sum(1 for t in all_tasks if t.status == TaskStatus.FAILED)
        
        overall_progress = (completed / total * 100) if total > 0 else 0.0
        
        agents = await self._get_agent_progress()
        recent_logs = await self._get_recent_logs(limit=50)
        
        return DashboardStatsResponse(
            total_tasks=total,
            completed_tasks=completed,
            in_progress_tasks=in_progress,
            pending_tasks=pending,
            failed_tasks=failed,
            overall_progress=overall_progress,
            agents=agents,
            recent_logs=recent_logs
        )
    
    async def _get_recent_logs(self, limit: int = 100, level_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """最近のログを取得"""
        log_file = self.workspace_path / "logs" / "nocturnal_agent.jsonl"
        
        if not log_file.exists():
            return []
        
        logs = []
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                # 最後のlimit行を取得
                for line in lines[-limit:]:
                    try:
                        log_entry = json.loads(line.strip())
                        if level_filter and log_entry.get('level') != level_filter.upper():
                            continue
                        logs.append(log_entry)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            self.logger.log(LogLevel.WARNING, LogCategory.API_CALL, 
                          f"ログ読み込みエラー: {e}")
        
        # 時系列順にソート（新しいものが最後）
        logs.reverse()
        return logs
    
    def _get_dashboard_html(self) -> str:
        """ダッシュボードHTMLを返す"""
        return """
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nocturnal Agent 進捗ダッシュボード</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            color: #333;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        
        .header {
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            margin-bottom: 30px;
            text-align: center;
        }
        
        .header h1 {
            color: #667eea;
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: white;
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            text-align: center;
            transition: transform 0.3s ease;
        }
        
        .stat-card:hover {
            transform: translateY(-5px);
        }
        
        .stat-card h3 {
            color: #666;
            font-size: 0.9em;
            text-transform: uppercase;
            margin-bottom: 10px;
        }
        
        .stat-card .value {
            font-size: 2.5em;
            font-weight: bold;
            color: #667eea;
            margin-bottom: 5px;
        }
        
        .stat-card.completed .value { color: #10b981; }
        .stat-card.in-progress .value { color: #3b82f6; }
        .stat-card.pending .value { color: #f59e0b; }
        .stat-card.failed .value { color: #ef4444; }
        
        .progress-bar {
            width: 100%;
            height: 30px;
            background: #e5e7eb;
            border-radius: 15px;
            overflow: hidden;
            margin-top: 20px;
        }
        
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            transition: width 0.5s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
        }
        
        .agents-section {
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            margin-bottom: 30px;
        }
        
        .agents-section h2 {
            color: #667eea;
            margin-bottom: 20px;
            font-size: 1.8em;
        }
        
        .agent-card {
            border: 2px solid #e5e7eb;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            transition: border-color 0.3s ease;
        }
        
        .agent-card:hover {
            border-color: #667eea;
        }
        
        .agent-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        
        .agent-name {
            font-size: 1.3em;
            font-weight: bold;
            color: #333;
        }
        
        .agent-stats {
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
        }
        
        .agent-stat {
            text-align: center;
        }
        
        .agent-stat .label {
            font-size: 0.8em;
            color: #666;
            margin-bottom: 5px;
        }
        
        .agent-stat .value {
            font-size: 1.5em;
            font-weight: bold;
            color: #667eea;
        }
        
        .tasks-section {
            background: white;
            padding: 30px;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        
        .tasks-section h2 {
            color: #667eea;
            margin-bottom: 20px;
            font-size: 1.8em;
        }
        
        .task-item {
            border-left: 4px solid #e5e7eb;
            padding: 15px;
            margin-bottom: 15px;
            background: #f9fafb;
            border-radius: 5px;
            transition: all 0.3s ease;
        }
        
        .task-item:hover {
            border-left-color: #667eea;
            background: #f3f4f6;
        }
        
        .task-item.completed { border-left-color: #10b981; }
        .task-item.in-progress { border-left-color: #3b82f6; }
        .task-item.pending { border-left-color: #f59e0b; }
        .task-item.failed { border-left-color: #ef4444; }
        
        .task-header {
            display: flex;
            justify-content: space-between;
            align-items: start;
            margin-bottom: 10px;
        }
        
        .task-title {
            font-weight: bold;
            color: #333;
            font-size: 1.1em;
        }
        
        .task-status {
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.8em;
            font-weight: bold;
            text-transform: uppercase;
        }
        
        .task-status.completed { background: #d1fae5; color: #065f46; }
        .task-status.in-progress { background: #dbeafe; color: #1e40af; }
        .task-status.pending { background: #fef3c7; color: #92400e; }
        .task-status.failed { background: #fee2e2; color: #991b1b; }
        
        .task-description {
            color: #666;
            margin-bottom: 10px;
        }
        
        .task-meta {
            display: flex;
            gap: 15px;
            font-size: 0.9em;
            color: #999;
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            color: #666;
        }
        
        .refresh-btn {
            background: #667eea;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 1em;
            margin-bottom: 20px;
            transition: background 0.3s ease;
        }
        
        .refresh-btn:hover {
            background: #5568d3;
        }
        
        @media (max-width: 768px) {
            .stats-grid {
                grid-template-columns: 1fr;
            }
            
            .agent-header {
                flex-direction: column;
                align-items: flex-start;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🌙 Nocturnal Agent 進捗ダッシュボード</h1>
            <p>エージェントの進捗状況をリアルタイムで確認</p>
        </div>
        
        <button class="refresh-btn" onclick="loadDashboard()">🔄 更新</button>
        
        <div id="loading" class="loading">データを読み込み中...</div>
        
        <div id="dashboard" style="display: none;">
            <div class="stats-grid">
                <div class="stat-card">
                    <h3>総タスク数</h3>
                    <div class="value" id="total-tasks">0</div>
                </div>
                <div class="stat-card completed">
                    <h3>完了</h3>
                    <div class="value" id="completed-tasks">0</div>
                </div>
                <div class="stat-card in-progress">
                    <h3>実行中</h3>
                    <div class="value" id="in-progress-tasks">0</div>
                </div>
                <div class="stat-card pending">
                    <h3>待機中</h3>
                    <div class="value" id="pending-tasks">0</div>
                </div>
                <div class="stat-card failed">
                    <h3>失敗</h3>
                    <div class="value" id="failed-tasks">0</div>
                </div>
            </div>
            
            <div class="stat-card">
                <h3>全体進捗</h3>
                <div class="progress-bar">
                    <div class="progress-fill" id="overall-progress" style="width: 0%">0%</div>
                </div>
            </div>
            
            <div class="agents-section">
                <h2>📊 エージェント別進捗</h2>
                <div id="agents-list"></div>
            </div>
            
            <div class="tasks-section">
                <h2>📋 タスク一覧</h2>
                <div id="tasks-list"></div>
            </div>
        </div>
    </div>
    
    <script>
        let refreshInterval;
        
        async function loadDashboard() {
            try {
                const response = await fetch('/api/stats');
                const data = await response.json();
                
                // 統計情報を更新
                document.getElementById('total-tasks').textContent = data.total_tasks;
                document.getElementById('completed-tasks').textContent = data.completed_tasks;
                document.getElementById('in-progress-tasks').textContent = data.in_progress_tasks;
                document.getElementById('pending-tasks').textContent = data.pending_tasks;
                document.getElementById('failed-tasks').textContent = data.failed_tasks;
                
                // 進捗バーを更新
                const progressBar = document.getElementById('overall-progress');
                progressBar.style.width = data.overall_progress + '%';
                progressBar.textContent = data.overall_progress.toFixed(1) + '%';
                
                // エージェントリストを更新
                renderAgents(data.agents);
                
                // タスクリストを更新
                renderTasks(data.agents);
                
                // ダッシュボードを表示
                document.getElementById('loading').style.display = 'none';
                document.getElementById('dashboard').style.display = 'block';
            } catch (error) {
                console.error('ダッシュボード読み込みエラー:', error);
                document.getElementById('loading').textContent = 'エラー: データの読み込みに失敗しました';
            }
        }
        
        function renderAgents(agents) {
            const container = document.getElementById('agents-list');
            container.innerHTML = '';
            
            agents.forEach(agent => {
                const card = document.createElement('div');
                card.className = 'agent-card';
                
                card.innerHTML = `
                    <div class="agent-header">
                        <div class="agent-name">🤖 ${agent.agent_name}</div>
                        <div class="progress-bar" style="width: 200px; height: 20px;">
                            <div class="progress-fill" style="width: ${agent.progress_percentage}%">
                                ${agent.progress_percentage.toFixed(1)}%
                            </div>
                        </div>
                    </div>
                    <div class="agent-stats">
                        <div class="agent-stat">
                            <div class="label">総タスク</div>
                            <div class="value">${agent.total_tasks}</div>
                        </div>
                        <div class="agent-stat">
                            <div class="label">完了</div>
                            <div class="value" style="color: #10b981;">${agent.completed_tasks}</div>
                        </div>
                        <div class="agent-stat">
                            <div class="label">実行中</div>
                            <div class="value" style="color: #3b82f6;">${agent.in_progress_tasks}</div>
                        </div>
                        <div class="agent-stat">
                            <div class="label">待機中</div>
                            <div class="value" style="color: #f59e0b;">${agent.pending_tasks}</div>
                        </div>
                        <div class="agent-stat">
                            <div class="label">失敗</div>
                            <div class="value" style="color: #ef4444;">${agent.failed_tasks}</div>
                        </div>
                    </div>
                `;
                
                container.appendChild(card);
            });
        }
        
        function renderTasks(agents) {
            const container = document.getElementById('tasks-list');
            container.innerHTML = '';
            
            // 全エージェントのタスクを統合
            const allTasks = [];
            agents.forEach(agent => {
                agent.tasks.forEach(task => {
                    allTasks.push({...task, agent_name: agent.agent_name});
                });
            });
            
            // ステータス順にソート（実行中 > 待機中 > 完了 > 失敗）
            const statusOrder = {
                'IN_PROGRESS': 0,
                'PENDING': 1,
                'APPROVED': 1,
                'COMPLETED': 2,
                'FAILED': 3
            };
            
            allTasks.sort((a, b) => {
                const orderA = statusOrder[a.status] ?? 99;
                const orderB = statusOrder[b.status] ?? 99;
                if (orderA !== orderB) return orderA - orderB;
                return new Date(b.updated_at) - new Date(a.updated_at);
            });
            
            allTasks.forEach(task => {
                const item = document.createElement('div');
                item.className = `task-item ${task.status.toLowerCase().replace('_', '-')}`;
                
                const statusClass = task.status.toLowerCase().replace('_', '-');
                const statusLabel = {
                    'completed': '完了',
                    'in-progress': '実行中',
                    'pending': '待機中',
                    'approved': '承認済み',
                    'failed': '失敗'
                }[statusClass] || task.status;
                
                item.innerHTML = `
                    <div class="task-header">
                        <div class="task-title">${task.title}</div>
                        <div class="task-status ${statusClass}">${statusLabel}</div>
                    </div>
                    <div class="task-description">${task.description || '説明なし'}</div>
                    <div class="task-meta">
                        <span>🤖 ${task.agent_name || '未割り当て'}</span>
                        <span>⭐ ${task.priority}</span>
                        <span>⏱️ ${task.estimated_hours}時間</span>
                        <span>📅 ${new Date(task.updated_at).toLocaleString('ja-JP')}</span>
                    </div>
                `;
                
                container.appendChild(item);
            });
        }
        
        // 初回読み込み
        loadDashboard();
        
        // 30秒ごとに自動更新
        refreshInterval = setInterval(loadDashboard, 30000);
    </script>
</body>
</html>
        """
    
    def run(self, host: str = "0.0.0.0", port: int = 8000):
        """APIサーバーを起動"""
        import uvicorn
        self.logger.log(LogLevel.INFO, LogCategory.SYSTEM, 
                      f"🚀 ダッシュボードAPIサーバーを起動: http://{host}:{port}")
        uvicorn.run(self.app, host=host, port=port)


def main():
    """メイン関数"""
    import sys
    from pathlib import Path
    
    if len(sys.argv) > 1:
        workspace_path = sys.argv[1]
    else:
        workspace_path = Path.cwd()
    
    server = DashboardAPIServer(workspace_path=str(workspace_path))
    server.run()


if __name__ == "__main__":
    main()
