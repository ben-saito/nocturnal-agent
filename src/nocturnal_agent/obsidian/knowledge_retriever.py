"""Knowledge retrieval and search functionality for Obsidian vault."""

import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from nocturnal_agent.core.models import CodePattern, ConsistencyRule


logger = logging.getLogger(__name__)


class ObsidianKnowledgeRetriever:
    """Retrieves and searches knowledge from Obsidian vault."""
    
    def __init__(self, vault_path: str, project_name: str):
        """Initialize knowledge retriever.
        
        Args:
            vault_path: Path to Obsidian vault
            project_name: Name of the project
        """
        self.vault_path = Path(vault_path)
        self.project_name = project_name
        self.project_dir = self.vault_path / project_name
        
        # Search index cache
        self._search_index: Dict[str, Dict[str, Any]] = {}
        self._index_last_updated: Optional[datetime] = None
        
    async def search_patterns(
        self, 
        query: str, 
        pattern_type: Optional[str] = None,
        min_confidence: float = 0.0,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search for code patterns matching query.
        
        Args:
            query: Search query
            pattern_type: Filter by pattern type
            min_confidence: Minimum confidence threshold
            limit: Maximum number of results
            
        Returns:
            List of matching patterns
        """
        try:
            await self._refresh_search_index()
            
            results = []
            query_lower = query.lower()
            
            patterns_dir = self.project_dir / "patterns"
            if not patterns_dir.exists():
                return results
            
            for pattern_file in patterns_dir.glob("*.md"):
                if pattern_file.name.startswith("consistency-rules"):
                    continue
                
                file_content = pattern_file.read_text(encoding='utf-8')
                frontmatter = self._parse_frontmatter(file_content)
                
                if frontmatter.get('type') != 'pattern':
                    continue
                
                # Apply filters
                if pattern_type and frontmatter.get('pattern_type') != pattern_type:
                    continue
                
                confidence = float(frontmatter.get('confidence', 0.0))
                if confidence < min_confidence:
                    continue
                
                # Check if query matches
                title_match = re.search(r'^# (.+)$', file_content, re.MULTILINE)
                title = title_match.group(1) if title_match else pattern_file.stem
                
                # Search in title, description, and content
                if (query_lower in title.lower() or 
                    query_lower in file_content.lower()):
                    
                    # Extract description
                    desc_match = re.search(r'## Description\n(.*?)\n##', file_content, re.DOTALL)
                    description = desc_match.group(1).strip() if desc_match else ""
                    
                    # Calculate relevance score
                    relevance_score = self._calculate_relevance_score(query, title, description, file_content)
                    
                    result = {
                        'title': title,
                        'pattern_type': frontmatter.get('pattern_type'),
                        'confidence': confidence,
                        'usage_count': int(frontmatter.get('usage_count', 0)),
                        'description': description,
                        'file_path': str(pattern_file),
                        'relevance_score': relevance_score
                    }
                    
                    results.append(result)
            
            # Sort by relevance and confidence
            results.sort(key=lambda x: (x['relevance_score'], x['confidence']), reverse=True)
            
            return results[:limit]
            
        except Exception as e:
            logger.error(f"Pattern search failed: {e}")
            return []
    
    async def search_similar_patterns(
        self,
        reference_pattern: CodePattern,
        similarity_threshold: float = 0.7,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Find patterns similar to a reference pattern.
        
        Args:
            reference_pattern: Pattern to find similarities for
            similarity_threshold: Minimum similarity score
            limit: Maximum number of results
            
        Returns:
            List of similar patterns
        """
        try:
            # Search by pattern type first
            type_matches = await self.search_patterns(
                query=reference_pattern.pattern_type,
                pattern_type=reference_pattern.pattern_type,
                limit=limit * 2
            )
            
            similar_patterns = []
            
            for match in type_matches:
                # Calculate similarity based on description and content
                similarity_score = self._calculate_similarity_score(
                    reference_pattern, match
                )
                
                if similarity_score >= similarity_threshold:
                    match['similarity_score'] = similarity_score
                    similar_patterns.append(match)
            
            # Sort by similarity
            similar_patterns.sort(key=lambda x: x['similarity_score'], reverse=True)
            
            return similar_patterns[:limit]
            
        except Exception as e:
            logger.error(f"Similar pattern search failed: {e}")
            return []
    
    async def search_by_tags(
        self,
        tags: List[str],
        content_type: str = "all",
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Search content by tags.
        
        Args:
            tags: List of tags to search for
            content_type: Type of content ('pattern', 'history', 'rule', 'all')
            limit: Maximum number of results
            
        Returns:
            List of matching content
        """
        try:
            results = []
            search_dirs = []
            
            # Determine search directories based on content type
            if content_type in ['all', 'pattern']:
                search_dirs.append(('patterns', 'pattern'))
            if content_type in ['all', 'history']:
                search_dirs.append(('history', 'development_history'))
            if content_type in ['all', 'rule']:
                search_dirs.append(('patterns/consistency-rules', 'consistency_rule'))
            
            for dir_name, expected_type in search_dirs:
                search_dir = self.project_dir / dir_name
                if not search_dir.exists():
                    continue
                
                for md_file in search_dir.glob("*.md"):
                    file_content = md_file.read_text(encoding='utf-8')
                    frontmatter = self._parse_frontmatter(file_content)
                    
                    # Check content type
                    if expected_type != 'all' and frontmatter.get('type') != expected_type:
                        continue
                    
                    # Check if any tag matches
                    file_tags = frontmatter.get('tags', [])
                    if isinstance(file_tags, str):
                        file_tags = [file_tags]
                    
                    matching_tags = set(tags) & set(file_tags)
                    if not matching_tags:
                        continue
                    
                    # Extract title
                    title_match = re.search(r'^# (.+)$', file_content, re.MULTILINE)
                    title = title_match.group(1) if title_match else md_file.stem
                    
                    result = {
                        'title': title,
                        'type': frontmatter.get('type'),
                        'tags': file_tags,
                        'matching_tags': list(matching_tags),
                        'file_path': str(md_file),
                        'created': frontmatter.get('created'),
                        'tag_match_score': len(matching_tags) / len(tags)
                    }
                    
                    results.append(result)
            
            # Sort by tag match score
            results.sort(key=lambda x: x['tag_match_score'], reverse=True)
            
            return results[:limit]
            
        except Exception as e:
            logger.error(f"Tag search failed: {e}")
            return []
    
    async def get_recent_activity(
        self,
        days: int = 7,
        activity_type: str = "all"
    ) -> List[Dict[str, Any]]:
        """Get recent activity from the vault.
        
        Args:
            days: Number of days to look back
            activity_type: Type of activity ('pattern', 'history', 'all')
            
        Returns:
            List of recent activities
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            activities = []
            
            # Search for recent files
            for file_path in self.project_dir.rglob("*.md"):
                # Skip if file is older than cutoff
                if file_path.stat().st_mtime < cutoff_date.timestamp():
                    continue
                
                file_content = file_path.read_text(encoding='utf-8')
                frontmatter = self._parse_frontmatter(file_content)
                
                content_type = frontmatter.get('type', 'unknown')
                
                # Filter by activity type
                if activity_type != 'all':
                    if activity_type == 'pattern' and content_type != 'pattern':
                        continue
                    if activity_type == 'history' and content_type != 'development_history':
                        continue
                
                # Extract title
                title_match = re.search(r'^# (.+)$', file_content, re.MULTILINE)
                title = title_match.group(1) if title_match else file_path.stem
                
                activity = {
                    'title': title,
                    'type': content_type,
                    'file_path': str(file_path),
                    'modified_time': datetime.fromtimestamp(file_path.stat().st_mtime),
                    'created_time': frontmatter.get('created'),
                    'relative_path': str(file_path.relative_to(self.project_dir))
                }
                
                activities.append(activity)
            
            # Sort by modification time
            activities.sort(key=lambda x: x['modified_time'], reverse=True)
            
            return activities
            
        except Exception as e:
            logger.error(f"Recent activity retrieval failed: {e}")
            return []
    
    async def get_cross_project_knowledge(
        self,
        query: str,
        exclude_current: bool = True
    ) -> List[Dict[str, Any]]:
        """Search knowledge across all projects in the vault.
        
        Args:
            query: Search query
            exclude_current: Whether to exclude current project
            
        Returns:
            List of cross-project knowledge matches
        """
        try:
            results = []
            query_lower = query.lower()
            
            # Find all project directories
            project_dirs = [
                d for d in self.vault_path.iterdir()
                if d.is_dir() and not d.name.startswith('.')
            ]
            
            for project_dir in project_dirs:
                if exclude_current and project_dir.name == self.project_name:
                    continue
                
                # Search patterns in this project
                patterns_dir = project_dir / "patterns"
                if not patterns_dir.exists():
                    continue
                
                for pattern_file in patterns_dir.glob("*.md"):
                    if pattern_file.name.startswith("consistency-rules"):
                        continue
                    
                    file_content = pattern_file.read_text(encoding='utf-8')
                    
                    # Check if query matches
                    if query_lower in file_content.lower():
                        frontmatter = self._parse_frontmatter(file_content)
                        
                        title_match = re.search(r'^# (.+)$', file_content, re.MULTILINE)
                        title = title_match.group(1) if title_match else pattern_file.stem
                        
                        result = {
                            'title': title,
                            'project': project_dir.name,
                            'pattern_type': frontmatter.get('pattern_type'),
                            'confidence': float(frontmatter.get('confidence', 0.0)),
                            'file_path': str(pattern_file),
                            'relevance_score': self._calculate_relevance_score(query, title, file_content, file_content)
                        }
                        
                        results.append(result)
            
            # Sort by relevance and confidence
            results.sort(key=lambda x: (x['relevance_score'], x['confidence']), reverse=True)
            
            return results
            
        except Exception as e:
            logger.error(f"Cross-project search failed: {e}")
            return []
    
    async def get_pattern_usage_statistics(self) -> Dict[str, Any]:
        """Get statistics about pattern usage across the project.
        
        Returns:
            Dictionary with usage statistics
        """
        try:
            patterns_dir = self.project_dir / "patterns"
            if not patterns_dir.exists():
                return {'total_patterns': 0}
            
            patterns_data = []
            pattern_types = {}
            
            for pattern_file in patterns_dir.glob("*.md"):
                if pattern_file.name.startswith("consistency-rules"):
                    continue
                
                file_content = pattern_file.read_text(encoding='utf-8')
                frontmatter = self._parse_frontmatter(file_content)
                
                if frontmatter.get('type') != 'pattern':
                    continue
                
                pattern_type = frontmatter.get('pattern_type', 'unknown')
                confidence = float(frontmatter.get('confidence', 0.0))
                usage_count = int(frontmatter.get('usage_count', 0))
                
                patterns_data.append({
                    'type': pattern_type,
                    'confidence': confidence,
                    'usage_count': usage_count
                })
                
                # Count by type
                if pattern_type not in pattern_types:
                    pattern_types[pattern_type] = {'count': 0, 'avg_confidence': 0.0, 'total_usage': 0}
                
                pattern_types[pattern_type]['count'] += 1
                pattern_types[pattern_type]['avg_confidence'] += confidence
                pattern_types[pattern_type]['total_usage'] += usage_count
            
            # Calculate averages
            for ptype_data in pattern_types.values():
                if ptype_data['count'] > 0:
                    ptype_data['avg_confidence'] /= ptype_data['count']
            
            # Overall statistics
            total_patterns = len(patterns_data)
            avg_confidence = sum(p['confidence'] for p in patterns_data) / total_patterns if total_patterns > 0 else 0.0
            high_confidence_count = sum(1 for p in patterns_data if p['confidence'] > 0.8)
            most_used_pattern = max(patterns_data, key=lambda p: p['usage_count']) if patterns_data else None
            
            return {
                'total_patterns': total_patterns,
                'average_confidence': avg_confidence,
                'high_confidence_patterns': high_confidence_count,
                'pattern_types': pattern_types,
                'most_used_pattern_usage': most_used_pattern['usage_count'] if most_used_pattern else 0,
                'patterns_by_type': {ptype: data['count'] for ptype, data in pattern_types.items()}
            }
            
        except Exception as e:
            logger.error(f"Usage statistics retrieval failed: {e}")
            return {'error': str(e)}
    
    async def suggest_related_knowledge(
        self,
        context: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Suggest related knowledge based on context.
        
        Args:
            context: Context to find related knowledge for
            limit: Maximum number of suggestions
            
        Returns:
            List of related knowledge suggestions
        """
        try:
            suggestions = []
            
            # Extract keywords from context
            keywords = self._extract_keywords(context)
            
            # Search for patterns matching keywords
            for keyword in keywords[:3]:  # Limit to top 3 keywords
                pattern_matches = await self.search_patterns(keyword, limit=3)
                for match in pattern_matches:
                    match['suggestion_reason'] = f"Related to keyword: {keyword}"
                    suggestions.append(match)
            
            # Search by tags derived from keywords
            tag_matches = await self.search_by_tags(keywords[:2], limit=3)
            for match in tag_matches:
                match['suggestion_reason'] = "Related by tags"
                suggestions.append(match)
            
            # Remove duplicates and limit results
            seen_paths = set()
            unique_suggestions = []
            
            for suggestion in suggestions:
                if suggestion['file_path'] not in seen_paths:
                    seen_paths.add(suggestion['file_path'])
                    unique_suggestions.append(suggestion)
            
            return unique_suggestions[:limit]
            
        except Exception as e:
            logger.error(f"Related knowledge suggestion failed: {e}")
            return []
    
    async def _refresh_search_index(self):
        """Refresh search index if needed."""
        
        if (self._index_last_updated is None or 
            (datetime.now() - self._index_last_updated).total_seconds() > 300):  # 5 minutes
            
            self._search_index.clear()
            self._index_last_updated = datetime.now()
    
    def _parse_frontmatter(self, content: str) -> Dict[str, Any]:
        """Parse YAML frontmatter from markdown content."""
        
        frontmatter_match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
        if not frontmatter_match:
            return {}
        
        import yaml
        try:
            return yaml.safe_load(frontmatter_match.group(1)) or {}
        except yaml.YAMLError:
            return {}
    
    def _calculate_relevance_score(
        self,
        query: str,
        title: str,
        description: str,
        content: str
    ) -> float:
        """Calculate relevance score for search results."""
        
        query_lower = query.lower()
        score = 0.0
        
        # Title match (highest weight)
        if query_lower in title.lower():
            score += 3.0
        
        # Description match
        if query_lower in description.lower():
            score += 2.0
        
        # Content match
        if query_lower in content.lower():
            score += 1.0
        
        # Exact word matches
        query_words = query_lower.split()
        content_words = (title + " " + description + " " + content).lower().split()
        
        word_matches = sum(1 for word in query_words if word in content_words)
        score += word_matches * 0.5
        
        return score
    
    def _calculate_similarity_score(
        self,
        reference_pattern: CodePattern,
        candidate: Dict[str, Any]
    ) -> float:
        """Calculate similarity score between patterns."""
        
        score = 0.0
        
        # Pattern type match
        if reference_pattern.pattern_type == candidate.get('pattern_type'):
            score += 0.5
        
        # Description similarity (simplified)
        ref_desc = reference_pattern.description.lower()
        cand_desc = candidate.get('description', '').lower()
        
        common_words = set(ref_desc.split()) & set(cand_desc.split())
        if len(cand_desc.split()) > 0:
            desc_similarity = len(common_words) / len(set(ref_desc.split()) | set(cand_desc.split()))
            score += desc_similarity * 0.5
        
        return min(score, 1.0)  # Cap at 1.0
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text for suggestion purposes."""
        
        # Simple keyword extraction (could be enhanced with NLP)
        words = re.findall(r'\b\w+\b', text.lower())
        
        # Filter common words
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
            'this', 'that', 'these', 'those', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might',
            'it', 'its', 'he', 'she', 'they', 'them', 'their', 'we', 'us', 'our', 'you', 'your'
        }
        
        keywords = [word for word in words if len(word) > 2 and word not in stop_words]
        
        # Return most frequent keywords
        from collections import Counter
        counter = Counter(keywords)
        return [word for word, count in counter.most_common(10)]