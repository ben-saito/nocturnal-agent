"""Danger detection system to prevent harmful operations."""

import logging
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum


logger = logging.getLogger(__name__)


class DangerLevel(Enum):
    """Danger level classification."""
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class DangerPattern:
    """Definition of a dangerous pattern."""
    name: str
    pattern: str
    danger_level: DangerLevel
    description: str
    category: str
    regex_flags: int = re.IGNORECASE
    enabled: bool = True


@dataclass
class DangerDetection:
    """Result of danger detection."""
    is_dangerous: bool
    danger_level: DangerLevel
    detected_patterns: List[DangerPattern]
    risk_description: str
    recommended_action: str
    blocked_operations: List[str] = field(default_factory=list)


class DangerDetector:
    """Detects and prevents dangerous operations during autonomous execution."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize danger detector.
        
        Args:
            config: Danger detection configuration
        """
        self.config = config
        
        # Protection settings
        self.block_on_high_danger = config.get('block_on_high_danger', True)
        self.block_on_critical_danger = config.get('block_on_critical_danger', True)
        self.require_confirmation = config.get('require_confirmation', True)
        
        # Protected paths (relative to project root)
        self.protected_paths = set(config.get('protected_paths', [
            '.git/',
            'requirements.txt',
            'package.json',
            'Cargo.toml',
            'pyproject.toml',
            '.env',
            'config/',
            'secrets/',
            'certificates/'
        ]))
        
        # Critical system files/directories
        self.critical_system_paths = set(config.get('critical_system_paths', [
            '/etc/',
            '/bin/',
            '/sbin/',
            '/usr/bin/',
            '/usr/sbin/',
            '/System/',
            '/Library/',
            'C:\\Windows\\',
            'C:\\Program Files\\',
            'C:\\System32\\'
        ]))
        
        # Danger patterns for code and commands
        self.danger_patterns = self._initialize_danger_patterns()
        
        # Statistics
        self.detection_stats = {
            'total_checks': 0,
            'dangers_detected': 0,
            'operations_blocked': 0,
            'false_positives_reported': 0,
            'pattern_matches': {}
        }
    
    def _initialize_danger_patterns(self) -> List[DangerPattern]:
        """Initialize danger detection patterns.
        
        Returns:
            List of danger patterns
        """
        patterns = [
            # File system operations - Critical
            DangerPattern(
                name="rm_recursive",
                pattern=r'\brm\s+.*-[rf]+.*\*|rm\s+-[rf]+\s*/',
                danger_level=DangerLevel.CRITICAL,
                description="Recursive file deletion command",
                category="filesystem"
            ),
            DangerPattern(
                name="format_drive",
                pattern=r'\bformat\s+[a-z]:|diskutil\s+eraseDisk|mkfs\.',
                danger_level=DangerLevel.CRITICAL,
                description="Drive formatting command",
                category="filesystem"
            ),
            DangerPattern(
                name="chmod_777",
                pattern=r'\bchmod\s+777\s+/',
                danger_level=DangerLevel.HIGH,
                description="Setting dangerous permissions on system directories",
                category="filesystem"
            ),
            
            # Network operations - High
            DangerPattern(
                name="curl_pipe_bash",
                pattern=r'curl\s+.*\|\s*bash|wget\s+.*\|\s*sh',
                danger_level=DangerLevel.HIGH,
                description="Downloading and executing remote scripts",
                category="network"
            ),
            DangerPattern(
                name="nc_backdoor",
                pattern=r'\bnc\s+.*-[el]+.*\d+.*sh\b|netcat\s+.*-[el]+.*\d+.*sh\b',
                danger_level=DangerLevel.CRITICAL,
                description="Creating network backdoor",
                category="network"
            ),
            
            # System modification - Critical
            DangerPattern(
                name="sudoers_modification",
                pattern=r'echo\s+.*>>\s*/etc/sudoers|visudo',
                danger_level=DangerLevel.CRITICAL,
                description="Modifying sudo configuration",
                category="system"
            ),
            DangerPattern(
                name="crontab_modification",
                pattern=r'crontab\s+-[er]|echo\s+.*>>\s*/etc/crontab',
                danger_level=DangerLevel.HIGH,
                description="Modifying scheduled tasks",
                category="system"
            ),
            DangerPattern(
                name="service_manipulation",
                pattern=r'systemctl\s+disable|service\s+.*stop|launchctl\s+unload',
                danger_level=DangerLevel.HIGH,
                description="Disabling system services",
                category="system"
            ),
            
            # Code injection patterns - High
            DangerPattern(
                name="eval_injection",
                pattern=r'\beval\s*\(\s*["\'].*user|exec\s*\(\s*["\'].*input',
                danger_level=DangerLevel.HIGH,
                description="Potential code injection via eval/exec",
                category="code"
            ),
            DangerPattern(
                name="sql_injection_pattern",
                pattern=r'execute\s*\(\s*["\'].*%s|query\s*\(\s*["\'].*\+',
                danger_level=DangerLevel.HIGH,
                description="Potential SQL injection pattern",
                category="code"
            ),
            
            # Crypto/Security - Medium to High
            DangerPattern(
                name="hardcoded_secrets",
                pattern=r'password\s*=\s*["\'][^"\']{8,}["\']|api[_-]?key\s*=\s*["\'][^"\']{16,}["\']',
                danger_level=DangerLevel.MEDIUM,
                description="Hardcoded secrets in code",
                category="security"
            ),
            DangerPattern(
                name="crypto_key_generation",
                pattern=r'openssl\s+genrsa|ssh-keygen\s+.*-f\s*/|gpg\s+--gen-key',
                danger_level=DangerLevel.MEDIUM,
                description="Cryptographic key generation",
                category="security"
            ),
            
            # Data destruction - Critical
            DangerPattern(
                name="database_drop",
                pattern=r'DROP\s+DATABASE|DELETE\s+FROM\s+\*|TRUNCATE\s+TABLE',
                danger_level=DangerLevel.CRITICAL,
                description="Database destruction commands",
                category="database"
            ),
            
            # Process manipulation - High
            DangerPattern(
                name="kill_system_processes",
                pattern=r'pkill\s+-9|killall\s+.*ssh|kill\s+-9\s+1\b',
                danger_level=DangerLevel.HIGH,
                description="Killing critical system processes",
                category="process"
            ),
            
            # Git operations - Medium to High
            DangerPattern(
                name="git_force_operations",
                pattern=r'git\s+push\s+.*--force|git\s+reset\s+--hard\s+HEAD~\d+',
                danger_level=DangerLevel.MEDIUM,
                description="Destructive git operations",
                category="git"
            ),
            DangerPattern(
                name="git_clean_force",
                pattern=r'git\s+clean\s+-[fxd]+',
                danger_level=DangerLevel.MEDIUM,
                description="Aggressive git cleanup",
                category="git"
            ),
            
            # Environment manipulation - Medium
            DangerPattern(
                name="path_manipulation",
                pattern=r'export\s+PATH\s*=\s*["\']?/tmp|PATH\s*=\s*["\']?/var/tmp',
                danger_level=DangerLevel.MEDIUM,
                description="Dangerous PATH modifications",
                category="environment"
            )
        ]
        
        # Add user-defined patterns from config
        user_patterns = self.config.get('custom_patterns', [])
        for pattern_config in user_patterns:
            pattern = DangerPattern(
                name=pattern_config['name'],
                pattern=pattern_config['pattern'],
                danger_level=DangerLevel(pattern_config.get('danger_level', 'medium')),
                description=pattern_config.get('description', ''),
                category=pattern_config.get('category', 'custom'),
                enabled=pattern_config.get('enabled', True)
            )
            patterns.append(pattern)
        
        return [p for p in patterns if p.enabled]
    
    def analyze_code(self, code: str, context: Optional[Dict[str, Any]] = None) -> DangerDetection:
        """Analyze code for dangerous patterns.
        
        Args:
            code: Code to analyze
            context: Optional context information
            
        Returns:
            Danger detection result
        """
        self.detection_stats['total_checks'] += 1
        
        detected_patterns = []
        max_danger_level = DangerLevel.SAFE
        blocked_operations = []
        
        # Check each pattern
        for pattern in self.danger_patterns:
            if not pattern.enabled:
                continue
            
            regex = re.compile(pattern.pattern, pattern.regex_flags)
            matches = regex.findall(code)
            
            if matches:
                detected_patterns.append(pattern)
                
                # Track statistics
                if pattern.name not in self.detection_stats['pattern_matches']:
                    self.detection_stats['pattern_matches'][pattern.name] = 0
                self.detection_stats['pattern_matches'][pattern.name] += len(matches)
                
                # Update max danger level
                if self._danger_level_value(pattern.danger_level) > self._danger_level_value(max_danger_level):
                    max_danger_level = pattern.danger_level
                
                # Check if operation should be blocked
                if self._should_block_operation(pattern.danger_level):
                    blocked_operations.extend(matches)
        
        # Generate risk description and recommendations
        is_dangerous = len(detected_patterns) > 0
        
        if is_dangerous:
            self.detection_stats['dangers_detected'] += 1
            
        if blocked_operations:
            self.detection_stats['operations_blocked'] += 1
        
        risk_description = self._generate_risk_description(detected_patterns, max_danger_level)
        recommended_action = self._generate_recommendations(detected_patterns, max_danger_level)
        
        return DangerDetection(
            is_dangerous=is_dangerous,
            danger_level=max_danger_level,
            detected_patterns=detected_patterns,
            risk_description=risk_description,
            recommended_action=recommended_action,
            blocked_operations=blocked_operations
        )
    
    def analyze_file_operation(self, operation: str, file_path: str) -> DangerDetection:
        """Analyze a file operation for potential dangers.
        
        Args:
            operation: Type of operation (read, write, delete, etc.)
            file_path: Path being operated on
            
        Returns:
            Danger detection result
        """
        self.detection_stats['total_checks'] += 1
        
        detected_patterns = []
        danger_level = DangerLevel.SAFE
        blocked_operations = []
        
        path = Path(file_path)
        
        # Check if path is protected
        if self._is_protected_path(path):
            if operation in ['delete', 'overwrite', 'modify']:
                danger_level = DangerLevel.HIGH
                detected_patterns.append(DangerPattern(
                    name="protected_path_modification",
                    pattern=f"{operation} {file_path}",
                    danger_level=DangerLevel.HIGH,
                    description=f"Attempting to {operation} protected file",
                    category="filesystem"
                ))
                
                if self._should_block_operation(danger_level):
                    blocked_operations.append(f"{operation} {file_path}")
        
        # Check if path is critical system path
        if self._is_critical_system_path(path):
            danger_level = DangerLevel.CRITICAL
            detected_patterns.append(DangerPattern(
                name="critical_system_path_access",
                pattern=f"{operation} {file_path}",
                danger_level=DangerLevel.CRITICAL,
                description=f"Attempting to {operation} critical system path",
                category="system"
            ))
            
            blocked_operations.append(f"{operation} {file_path}")
        
        # Check for bulk operations on many files
        if '*' in file_path or file_path.endswith('/'):
            if operation in ['delete']:
                danger_level = max(danger_level, DangerLevel.MEDIUM, key=self._danger_level_value)
                detected_patterns.append(DangerPattern(
                    name="bulk_file_deletion",
                    pattern=f"{operation} {file_path}",
                    danger_level=DangerLevel.MEDIUM,
                    description="Bulk file deletion operation",
                    category="filesystem"
                ))
        
        is_dangerous = len(detected_patterns) > 0
        
        if is_dangerous:
            self.detection_stats['dangers_detected'] += 1
            
        if blocked_operations:
            self.detection_stats['operations_blocked'] += 1
        
        risk_description = self._generate_risk_description(detected_patterns, danger_level)
        recommended_action = self._generate_recommendations(detected_patterns, danger_level)
        
        return DangerDetection(
            is_dangerous=is_dangerous,
            danger_level=danger_level,
            detected_patterns=detected_patterns,
            risk_description=risk_description,
            recommended_action=recommended_action,
            blocked_operations=blocked_operations
        )
    
    def analyze_command(self, command: str, context: Optional[Dict[str, Any]] = None) -> DangerDetection:
        """Analyze a shell command for potential dangers.
        
        Args:
            command: Shell command to analyze
            context: Optional context information
            
        Returns:
            Danger detection result
        """
        # Use code analysis for command analysis
        return self.analyze_code(command, context)
    
    def _is_protected_path(self, path: Path) -> bool:
        """Check if a path is protected.
        
        Args:
            path: Path to check
            
        Returns:
            True if path is protected
        """
        path_str = str(path)
        
        for protected in self.protected_paths:
            if protected.endswith('/'):
                # Directory protection
                if path_str.startswith(protected) or f"/{protected}" in path_str:
                    return True
            else:
                # File protection
                if path.name == protected or path_str.endswith(protected):
                    return True
        
        return False
    
    def _is_critical_system_path(self, path: Path) -> bool:
        """Check if a path is a critical system path.
        
        Args:
            path: Path to check
            
        Returns:
            True if path is critical system path
        """
        path_str = str(path.resolve())
        
        for critical in self.critical_system_paths:
            if path_str.startswith(critical):
                return True
        
        return False
    
    def _should_block_operation(self, danger_level: DangerLevel) -> bool:
        """Determine if an operation should be blocked based on danger level.
        
        Args:
            danger_level: Detected danger level
            
        Returns:
            True if operation should be blocked
        """
        if danger_level == DangerLevel.CRITICAL:
            return self.block_on_critical_danger
        elif danger_level == DangerLevel.HIGH:
            return self.block_on_high_danger
        
        return False
    
    def _danger_level_value(self, danger_level: DangerLevel) -> int:
        """Get numeric value for danger level comparison.
        
        Args:
            danger_level: Danger level
            
        Returns:
            Numeric value (higher = more dangerous)
        """
        return {
            DangerLevel.SAFE: 0,
            DangerLevel.LOW: 1,
            DangerLevel.MEDIUM: 2,
            DangerLevel.HIGH: 3,
            DangerLevel.CRITICAL: 4
        }[danger_level]
    
    def _generate_risk_description(self, patterns: List[DangerPattern], max_level: DangerLevel) -> str:
        """Generate risk description based on detected patterns.
        
        Args:
            patterns: Detected dangerous patterns
            max_level: Maximum danger level detected
            
        Returns:
            Risk description string
        """
        if not patterns:
            return "No dangerous patterns detected"
        
        if max_level == DangerLevel.CRITICAL:
            base_desc = "CRITICAL: Extremely dangerous operation detected"
        elif max_level == DangerLevel.HIGH:
            base_desc = "HIGH RISK: Potentially harmful operation detected"
        elif max_level == DangerLevel.MEDIUM:
            base_desc = "MEDIUM RISK: Potentially unsafe operation detected"
        else:
            base_desc = "LOW RISK: Suspicious operation detected"
        
        # Add specific pattern descriptions
        pattern_descriptions = [f"- {p.description}" for p in patterns[:3]]  # Top 3
        
        if len(patterns) > 3:
            pattern_descriptions.append(f"... and {len(patterns) - 3} more patterns")
        
        return f"{base_desc}:\n" + "\n".join(pattern_descriptions)
    
    def _generate_recommendations(self, patterns: List[DangerPattern], max_level: DangerLevel) -> str:
        """Generate recommendations based on detected patterns.
        
        Args:
            patterns: Detected dangerous patterns
            max_level: Maximum danger level detected
            
        Returns:
            Recommendation string
        """
        if not patterns:
            return "Operation appears safe to proceed"
        
        recommendations = []
        
        if max_level in [DangerLevel.CRITICAL, DangerLevel.HIGH]:
            recommendations.append("BLOCK: Operation should not be executed")
            recommendations.append("Manual review required before proceeding")
        elif max_level == DangerLevel.MEDIUM:
            recommendations.append("CAUTION: Review operation carefully before execution")
            recommendations.append("Consider safer alternatives if available")
        else:
            recommendations.append("WARNING: Monitor execution closely")
        
        # Category-specific recommendations
        categories = {p.category for p in patterns}
        
        if 'filesystem' in categories:
            recommendations.append("• Verify file paths and backup important data")
        if 'system' in categories:
            recommendations.append("• Check system integrity after operation")
        if 'network' in categories:
            recommendations.append("• Monitor network connections and traffic")
        if 'security' in categories:
            recommendations.append("• Review security implications and access controls")
        if 'database' in categories:
            recommendations.append("• Ensure database backup before proceeding")
        
        return "\n".join(recommendations)
    
    def add_custom_pattern(self, pattern: DangerPattern) -> bool:
        """Add a custom danger pattern.
        
        Args:
            pattern: Custom pattern to add
            
        Returns:
            True if pattern was added successfully
        """
        try:
            # Validate regex pattern
            re.compile(pattern.pattern, pattern.regex_flags)
            
            # Check if pattern already exists
            if any(p.name == pattern.name for p in self.danger_patterns):
                logger.warning(f"Pattern with name '{pattern.name}' already exists")
                return False
            
            self.danger_patterns.append(pattern)
            logger.info(f"Added custom danger pattern: {pattern.name}")
            return True
            
        except re.error as e:
            logger.error(f"Invalid regex pattern '{pattern.pattern}': {e}")
            return False
    
    def remove_pattern(self, pattern_name: str) -> bool:
        """Remove a danger pattern by name.
        
        Args:
            pattern_name: Name of pattern to remove
            
        Returns:
            True if pattern was removed
        """
        for i, pattern in enumerate(self.danger_patterns):
            if pattern.name == pattern_name:
                self.danger_patterns.pop(i)
                logger.info(f"Removed danger pattern: {pattern_name}")
                return True
        
        logger.warning(f"Pattern not found: {pattern_name}")
        return False
    
    def enable_pattern(self, pattern_name: str) -> bool:
        """Enable a danger pattern.
        
        Args:
            pattern_name: Name of pattern to enable
            
        Returns:
            True if pattern was enabled
        """
        for pattern in self.danger_patterns:
            if pattern.name == pattern_name:
                pattern.enabled = True
                logger.info(f"Enabled danger pattern: {pattern_name}")
                return True
        
        logger.warning(f"Pattern not found: {pattern_name}")
        return False
    
    def disable_pattern(self, pattern_name: str) -> bool:
        """Disable a danger pattern.
        
        Args:
            pattern_name: Name of pattern to disable
            
        Returns:
            True if pattern was disabled
        """
        for pattern in self.danger_patterns:
            if pattern.name == pattern_name:
                pattern.enabled = False
                logger.info(f"Disabled danger pattern: {pattern_name}")
                return True
        
        logger.warning(f"Pattern not found: {pattern_name}")
        return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get danger detector status.
        
        Returns:
            Status information
        """
        enabled_patterns = sum(1 for p in self.danger_patterns if p.enabled)
        patterns_by_level = {}
        patterns_by_category = {}
        
        for pattern in self.danger_patterns:
            if pattern.enabled:
                level = pattern.danger_level.value
                patterns_by_level[level] = patterns_by_level.get(level, 0) + 1
                
                category = pattern.category
                patterns_by_category[category] = patterns_by_category.get(category, 0) + 1
        
        return {
            'total_patterns': len(self.danger_patterns),
            'enabled_patterns': enabled_patterns,
            'patterns_by_level': patterns_by_level,
            'patterns_by_category': patterns_by_category,
            'protection_settings': {
                'block_on_high_danger': self.block_on_high_danger,
                'block_on_critical_danger': self.block_on_critical_danger,
                'require_confirmation': self.require_confirmation
            },
            'protected_paths_count': len(self.protected_paths),
            'critical_system_paths_count': len(self.critical_system_paths),
            'detection_statistics': self.detection_stats.copy()
        }
    
    def list_patterns(self, category: Optional[str] = None, danger_level: Optional[DangerLevel] = None) -> List[Dict[str, Any]]:
        """List danger patterns with optional filtering.
        
        Args:
            category: Optional category filter
            danger_level: Optional danger level filter
            
        Returns:
            List of pattern information
        """
        filtered_patterns = self.danger_patterns
        
        if category:
            filtered_patterns = [p for p in filtered_patterns if p.category == category]
        
        if danger_level:
            filtered_patterns = [p for p in filtered_patterns if p.danger_level == danger_level]
        
        return [
            {
                'name': p.name,
                'pattern': p.pattern,
                'danger_level': p.danger_level.value,
                'description': p.description,
                'category': p.category,
                'enabled': p.enabled,
                'matches': self.detection_stats['pattern_matches'].get(p.name, 0)
            }
            for p in filtered_patterns
        ]
    
    def report_false_positive(self, pattern_name: str, context: str = "") -> bool:
        """Report a false positive detection.
        
        Args:
            pattern_name: Name of pattern that triggered false positive
            context: Context information about the false positive
            
        Returns:
            True if report was recorded
        """
        self.detection_stats['false_positives_reported'] += 1
        
        logger.info(f"False positive reported for pattern '{pattern_name}': {context}")
        
        # In a full implementation, this could:
        # - Store false positive examples for pattern refinement
        # - Adjust pattern sensitivity
        # - Generate training data for ML-based improvements
        
        return True