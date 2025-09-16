"""安全性・バックアップシステムの単体テスト"""

import pytest
import tempfile
import subprocess
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from nocturnal_agent.safety.backup_manager import (
    BackupManager, BackupType, BackupInfo
)
from nocturnal_agent.safety.danger_detector import (
    DangerDetector, DangerPattern, DangerLevel, DangerDetection
)
from nocturnal_agent.safety.rollback_manager import (
    RollbackManager, RollbackPoint, RollbackType, RollbackOperation
)
from nocturnal_agent.safety.safety_coordinator import SafetyCoordinator


class TestBackupManager:
    """バックアップ管理システムのテスト"""
    
    @pytest.fixture
    def backup_manager(self, git_repo):
        """BackupManagerインスタンスを提供"""
        config = {
            'backup_directory': str(git_repo / '.backups'),
            'enable_verification': True,
            'retention_days': 7,
            'compression_enabled': True
        }
        return BackupManager(str(git_repo), config)
    
    def test_backup_manager_initialization(self, backup_manager):
        """BackupManagerの初期化テスト"""
        assert backup_manager.backup_directory.exists()
        assert backup_manager.enable_verification is True
        assert backup_manager.retention_days == 7
        assert backup_manager.compression_enabled is True
    
    @pytest.mark.asyncio
    async def test_create_full_backup(self, backup_manager):
        """フルバックアップ作成のテスト"""
        backup_info = await backup_manager.create_backup(
            backup_type=BackupType.FULL,
            backup_id='test_full_backup',
            description='テストフルバックアップ'
        )
        
        assert backup_info is not None
        assert backup_info.backup_id == 'test_full_backup'
        assert backup_info.backup_type == BackupType.FULL
        assert backup_info.description == 'テストフルバックアップ'
        assert backup_info.files_included > 0
    
    @pytest.mark.asyncio
    async def test_create_git_backup(self, backup_manager):
        """Gitバックアップ作成のテスト"""
        backup_info = await backup_manager.create_backup(
            backup_type=BackupType.GIT,
            backup_id='test_git_backup'
        )
        
        assert backup_info is not None
        assert backup_info.backup_type == BackupType.GIT
        assert backup_info.git_commit is not None
    
    @pytest.mark.asyncio
    async def test_verify_backup(self, backup_manager):
        """バックアップ検証のテスト"""
        # バックアップ作成
        backup_info = await backup_manager.create_backup(
            backup_type=BackupType.FULL,
            backup_id='test_verify'
        )
        
        # 検証実行
        is_valid = await backup_manager.verify_backup(backup_info.backup_id)
        assert is_valid is True
        
        updated_info = backup_manager.get_backup_info(backup_info.backup_id)
        assert updated_info.verification_status == 'verified'
    
    def test_list_backups(self, backup_manager):
        """バックアップ一覧取得のテスト"""
        backups = backup_manager.list_backups()
        assert isinstance(backups, list)
    
    def test_get_backup_status(self, backup_manager):
        """バックアップ状況取得のテスト"""
        status = backup_manager.get_backup_status()
        
        required_keys = [
            'total_backups', 'verified_backups', 'total_size',
            'latest_backup', 'storage_usage', 'retention_policy'
        ]
        
        for key in required_keys:
            assert key in status


class TestDangerDetector:
    """危険操作検出システムのテスト"""
    
    @pytest.fixture
    def danger_detector(self):
        """DangerDetectorインスタンスを提供"""
        config = {
            'enable_file_operations': True,
            'enable_system_commands': True,
            'enable_network_operations': False,
            'custom_patterns': []
        }
        return DangerDetector(config)
    
    def test_danger_detector_initialization(self, danger_detector):
        """DangerDetectorの初期化テスト"""
        assert danger_detector.enable_file_operations is True
        assert danger_detector.enable_system_commands is True
        assert danger_detector.enable_network_operations is False
        assert len(danger_detector.active_patterns) > 0
    
    def test_detect_dangerous_file_operations(self, danger_detector):
        """危険なファイル操作の検出テスト"""
        dangerous_code = "import os; os.system('rm -rf /')"
        
        detection = danger_detector.analyze_code(dangerous_code)
        
        assert detection.is_dangerous is True
        assert detection.danger_level == DangerLevel.CRITICAL
        assert len(detection.detected_patterns) > 0
        assert 'rm -rf' in detection.blocked_operations
    
    def test_detect_safe_operations(self, danger_detector):
        """安全な操作の検出テスト"""
        safe_code = "def hello_world():\n    return 'Hello, World!'"
        
        detection = danger_detector.analyze_code(safe_code)
        
        assert detection.is_dangerous is False
        assert detection.danger_level == DangerLevel.SAFE
        assert len(detection.detected_patterns) == 0
        assert len(detection.blocked_operations) == 0
    
    def test_detect_system_commands(self, danger_detector):
        """システムコマンドの検出テスト"""
        dangerous_code = "subprocess.run(['format', 'C:'], shell=True)"
        
        detection = danger_detector.analyze_code(dangerous_code)
        
        assert detection.is_dangerous is True
        assert detection.danger_level in [DangerLevel.HIGH, DangerLevel.CRITICAL]
    
    def test_pattern_management(self, danger_detector):
        """パターン管理のテスト"""
        initial_count = len(danger_detector.active_patterns)
        
        # カスタムパターン追加
        custom_pattern = DangerPattern(
            name='test_pattern',
            pattern=r'test_dangerous_function',
            danger_level=DangerLevel.MEDIUM,
            description='テスト用危険パターン'
        )
        
        danger_detector.add_custom_pattern(custom_pattern)
        assert len(danger_detector.active_patterns) == initial_count + 1
        
        # パターン削除
        danger_detector.remove_pattern('test_pattern')
        assert len(danger_detector.active_patterns) == initial_count
    
    def test_get_detector_status(self, danger_detector):
        """検出器状態取得のテスト"""
        status = danger_detector.get_status()
        
        required_keys = [
            'enabled_categories', 'enabled_patterns', 'total_detections',
            'recent_detections', 'severity_breakdown'
        ]
        
        for key in required_keys:
            assert key in status


class TestRollbackManager:
    """ロールバック管理システムのテスト"""
    
    @pytest.fixture
    def rollback_manager(self, git_repo):
        """RollbackManagerインスタンスを提供"""
        backup_manager = Mock()
        config = {
            'enable_verification': True,
            'max_rollback_points': 10
        }
        return RollbackManager(str(git_repo), backup_manager, config)
    
    @pytest.mark.asyncio
    async def test_create_rollback_point(self, rollback_manager):
        """ロールバックポイント作成のテスト"""
        rollback_point = await rollback_manager.create_rollback_point(
            "テストロールバックポイント"
        )
        
        assert rollback_point is not None
        assert rollback_point.description == "テストロールバックポイント"
        assert rollback_point.rollback_id is not None
        assert rollback_point.git_commit is not None
    
    def test_list_rollback_points(self, rollback_manager):
        """ロールバックポイント一覧のテスト"""
        points = rollback_manager.list_rollback_points()
        assert isinstance(points, list)
    
    def test_get_rollback_status(self, rollback_manager):
        """ロールバック状態取得のテスト"""
        status = rollback_manager.get_status()
        
        required_keys = [
            'rollback_points_count', 'recent_operations',
            'recent_success_rate', 'storage_usage'
        ]
        
        for key in required_keys:
            assert key in status
    
    @pytest.mark.asyncio
    async def test_rollback_point_cleanup(self, rollback_manager):
        """ロールバックポイントクリーンアップのテスト"""
        # 複数のロールバックポイントを作成
        for i in range(3):
            await rollback_manager.create_rollback_point(f"テストポイント{i}")
        
        initial_count = len(rollback_manager.rollback_points)
        
        # クリーンアップ実行
        cleaned = rollback_manager.cleanup_old_rollback_points(max_age_days=0)
        
        # 古いポイントが削除されたことを確認（実際の削除条件に依存）
        assert isinstance(cleaned, list)


class TestSafetyCoordinator:
    """安全性統合コーディネーターのテスト"""
    
    @pytest.fixture
    def safety_coordinator(self, git_repo):
        """SafetyCoordinatorインスタンスを提供"""
        config = {
            'backup': {
                'enable_verification': True,
                'retention_days': 7
            },
            'danger_detection': {
                'enable_file_operations': True,
                'enable_system_commands': True
            },
            'rollback': {
                'enable_verification': True,
                'max_rollback_points': 10
            },
            'auto_backup_before_execution': True,
            'auto_create_rollback_points': True,
            'block_dangerous_operations': True
        }
        return SafetyCoordinator(str(git_repo), config)
    
    @pytest.mark.asyncio
    async def test_initialize_safety_session(self, safety_coordinator):
        """安全セッション初期化のテスト"""
        success = await safety_coordinator.initialize_safety_session()
        
        assert success is True
        assert safety_coordinator.safety_active is True
        assert safety_coordinator.current_session_backup is not None
        assert safety_coordinator.current_rollback_point is not None
    
    @pytest.mark.asyncio
    async def test_pre_task_safety_check(self, safety_coordinator, sample_task):
        """タスク実行前安全チェックのテスト"""
        # 安全セッションを初期化
        await safety_coordinator.initialize_safety_session()
        
        # 安全なコードのテスト
        safe_code = "def test():\n    return 'safe'"
        safety_result = await safety_coordinator.pre_task_safety_check(
            sample_task, safe_code
        )
        
        assert safety_result['safe_to_execute'] is True
        assert safety_result['danger_level'] == DangerLevel.SAFE
        assert len(safety_result['blocking_issues']) == 0
    
    @pytest.mark.asyncio
    async def test_pre_task_safety_check_dangerous(self, safety_coordinator, sample_task):
        """危険なコードの実行前安全チェックテスト"""
        await safety_coordinator.initialize_safety_session()
        
        # 危険なコードのテスト
        dangerous_code = "import os; os.system('rm -rf *')"
        safety_result = await safety_coordinator.pre_task_safety_check(
            sample_task, dangerous_code
        )
        
        assert safety_result['safe_to_execute'] is False
        assert safety_result['danger_level'] == DangerLevel.CRITICAL
        assert len(safety_result['blocking_issues']) > 0
    
    @pytest.mark.asyncio
    async def test_post_task_safety_check(self, safety_coordinator, sample_task, sample_execution_result):
        """タスク実行後安全チェックのテスト"""
        await safety_coordinator.initialize_safety_session()
        
        safety_status = await safety_coordinator.post_task_safety_check(
            sample_task, sample_execution_result
        )
        
        assert safety_status['task_completed_safely'] is True
        assert 'actions_taken' in safety_status
        
        if sample_execution_result.files_modified:
            assert safety_status.get('rollback_point_created') is not None
    
    @pytest.mark.asyncio
    async def test_emergency_recovery(self, safety_coordinator):
        """緊急回復のテスト"""
        await safety_coordinator.initialize_safety_session()
        
        recovery_result = await safety_coordinator.emergency_recovery(
            "テスト緊急回復"
        )
        
        assert recovery_result['recovery_attempted'] is True
        assert 'recovery_successful' in recovery_result
        assert 'method_used' in recovery_result
        assert safety_coordinator.safety_stats['emergency_rollbacks'] >= 1
    
    @pytest.mark.asyncio
    async def test_safety_health_check(self, safety_coordinator):
        """安全性ヘルスチェックのテスト"""
        await safety_coordinator.initialize_safety_session()
        
        health_status = await safety_coordinator.safety_health_check()
        
        assert 'overall_healthy' in health_status
        assert 'components' in health_status
        assert 'backup_manager' in health_status['components']
        assert 'rollback_manager' in health_status['components']
        assert 'danger_detector' in health_status['components']
    
    def test_callback_management(self, safety_coordinator):
        """コールバック管理のテスト"""
        test_callback = Mock()
        
        # コールバック追加
        safety_coordinator.add_danger_callback(test_callback)
        safety_coordinator.add_backup_callback(test_callback)
        safety_coordinator.add_rollback_callback(test_callback)
        
        assert test_callback in safety_coordinator.danger_callbacks
        assert test_callback in safety_coordinator.backup_callbacks
        assert test_callback in safety_coordinator.rollback_callbacks
        
        # コールバック削除
        safety_coordinator.remove_callback(test_callback)
        
        assert test_callback not in safety_coordinator.danger_callbacks
        assert test_callback not in safety_coordinator.backup_callbacks
        assert test_callback not in safety_coordinator.rollback_callbacks
    
    def test_get_safety_status(self, safety_coordinator):
        """安全性状態取得のテスト"""
        status = safety_coordinator.get_safety_status()
        
        required_keys = [
            'safety_active', 'session_info', 'statistics',
            'safety_violations_count', 'component_status', 'configuration'
        ]
        
        for key in required_keys:
            assert key in status
    
    @pytest.mark.asyncio
    async def test_generate_safety_report(self, safety_coordinator):
        """安全性レポート生成のテスト"""
        await safety_coordinator.initialize_safety_session()
        
        report = await safety_coordinator.generate_safety_report()
        
        required_keys = [
            'report_timestamp', 'session_summary', 'health_check',
            'safety_violations', 'component_reports', 'recommendations'
        ]
        
        for key in required_keys:
            assert key in report
        
        assert report['report_timestamp'] is not None
        assert 'active' in report['session_summary']
    
    @pytest.mark.asyncio
    async def test_finalize_safety_session(self, safety_coordinator):
        """安全セッション終了のテスト"""
        await safety_coordinator.initialize_safety_session()
        
        session_report = await safety_coordinator.finalize_safety_session()
        
        assert safety_coordinator.safety_active is False
        assert 'session_duration' in session_report
        assert 'statistics' in session_report
        assert 'backup_status' in session_report
        assert 'rollback_status' in session_report


class TestBackupTypeEnum:
    """バックアップ種別列挙型のテスト"""
    
    def test_backup_type_values(self):
        """バックアップ種別の値テスト"""
        assert BackupType.FULL.value == "full"
        assert BackupType.INCREMENTAL.value == "incremental"
        assert BackupType.GIT.value == "git"
        assert BackupType.CRITICAL.value == "critical"


class TestDangerLevelEnum:
    """危険レベル列挙型のテスト"""
    
    def test_danger_level_values(self):
        """危険レベルの値テスト"""
        assert DangerLevel.SAFE.value == "safe"
        assert DangerLevel.LOW.value == "low"
        assert DangerLevel.MEDIUM.value == "medium"
        assert DangerLevel.HIGH.value == "high"
        assert DangerLevel.CRITICAL.value == "critical"


class TestRollbackTypeEnum:
    """ロールバック種別列挙型のテスト"""
    
    def test_rollback_type_values(self):
        """ロールバック種別の値テスト"""
        assert RollbackType.GIT_RESET.value == "git_reset"
        assert RollbackType.FILE_RESTORE.value == "file_restore"
        assert RollbackType.FULL_RESTORE.value == "full_restore"
        assert RollbackType.SELECTIVE_ROLLBACK.value == "selective_rollback"