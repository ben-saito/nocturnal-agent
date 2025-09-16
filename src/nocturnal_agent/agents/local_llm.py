"""Local LLM agent implementation using LM Studio."""

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

import aiohttp
from pydantic import BaseModel

from nocturnal_agent.core.config import LLMConfig
from nocturnal_agent.core.models import (
    Task, TaskAnalysis, QualityScore, ImprovementPlan, FailureInfo, AgentType
)


logger = logging.getLogger(__name__)


class LLMRequest(BaseModel):
    """Request model for LLM API calls."""
    model: str = "local"
    messages: List[Dict[str, str]]
    temperature: float = 0.7
    max_tokens: int = 4096
    stream: bool = False


class LLMResponse(BaseModel):
    """Response model for LLM API calls."""
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Dict[str, Any]]
    usage: Dict[str, int]


class LocalLLMAgent:
    """Local LLM agent for task orchestration and analysis."""
    
    def __init__(self, config: LLMConfig):
        """Initialize the Local LLM agent."""
        self.config = config
        self.model_name = "local"
        self.session: Optional[aiohttp.ClientSession] = None
        self._connection_verified = False
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()
    
    async def connect(self) -> None:
        """Establish connection to LM Studio."""
        if not self.config.enabled:
            logger.warning("Local LLM is disabled in configuration")
            return
        
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.config.timeout)
        )
        
        # Verify connection
        try:
            await self._verify_connection()
            self._connection_verified = True
            logger.info(f"Connected to LM Studio at {self.config.api_url}")
        except Exception as e:
            logger.error(f"Failed to connect to LM Studio: {e}")
            await self.disconnect()
            raise
    
    async def disconnect(self) -> None:
        """Close connection to LM Studio."""
        if self.session:
            await self.session.close()
            self.session = None
            self._connection_verified = False
    
    async def _verify_connection(self) -> None:
        """Verify connection to LM Studio API."""
        if not self.session:
            raise RuntimeError("No active session")
        
        # Try a simple request to verify the API is responding
        test_request = LLMRequest(
            messages=[{"role": "user", "content": "Hello"}],
            temperature=0.1,
            max_tokens=10
        )
        
        try:
            response = await self._make_request(test_request)
            if not response.choices:
                raise RuntimeError("Empty response from LLM API")
        except Exception as e:
            raise RuntimeError(f"LLM API verification failed: {e}")
    
    async def _make_request(self, request: LLMRequest) -> LLMResponse:
        """Make HTTP request to LM Studio API."""
        if not self.session or not self._connection_verified:
            raise RuntimeError("LLM agent not connected")
        
        url = f"{self.config.api_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        
        try:
            async with self.session.post(
                url, 
                json=request.dict(), 
                headers=headers
            ) as response:
                response.raise_for_status()
                data = await response.json()
                return LLMResponse(**data)
        except aiohttp.ClientError as e:
            logger.error(f"HTTP request failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in LLM request: {e}")
            raise
    
    async def analyze_task(self, task: Task) -> TaskAnalysis:
        """Analyze task and generate execution plan."""
        prompt = self._build_task_analysis_prompt(task)
        
        request = LLMRequest(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,  # Lower temperature for analysis
            max_tokens=2048
        )
        
        try:
            response = await self._make_request(request)
            analysis_text = response.choices[0]["message"]["content"]
            
            # Parse the analysis response
            analysis = self._parse_task_analysis(analysis_text, task.id)
            
            logger.info(f"Task analysis completed for {task.id}: "
                       f"complexity={analysis.complexity_score:.2f}, "
                       f"success_prob={analysis.success_probability:.2f}")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Task analysis failed for {task.id}: {e}")
            # Return a conservative analysis on failure
            return TaskAnalysis(
                task_id=task.id,
                complexity_score=0.8,
                estimated_duration=30.0,
                risk_level="medium",
                success_probability=0.5,
                recommended_agent=AgentType.LOCAL_LLM,
                execution_strategy="Conservative approach due to analysis failure"
            )
    
    async def evaluate_quality(self, code: str, context: str = "") -> QualityScore:
        """Evaluate code quality using LLM."""
        prompt = self._build_quality_evaluation_prompt(code, context)
        
        request = LLMRequest(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,  # Very low temperature for consistent scoring
            max_tokens=1024
        )
        
        try:
            response = await self._make_request(request)
            evaluation_text = response.choices[0]["message"]["content"]
            
            # Parse the quality evaluation
            quality_score = self._parse_quality_evaluation(evaluation_text)
            
            logger.info(f"Quality evaluation completed: overall={quality_score.overall:.2f}")
            
            return quality_score
            
        except Exception as e:
            logger.error(f"Quality evaluation failed: {e}")
            # Return a conservative score on failure
            return QualityScore(
                overall=0.5,
                code_quality=0.5,
                consistency=0.5,
                test_coverage=0.0,
                security=0.5,
                performance=0.5
            )
    
    async def analyze_failure(self, failure: FailureInfo) -> ImprovementPlan:
        """Analyze failure and create improvement plan."""
        prompt = self._build_failure_analysis_prompt(failure)
        
        request = LLMRequest(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,  # Moderate temperature for creative solutions
            max_tokens=2048
        )
        
        try:
            response = await self._make_request(request)
            analysis_text = response.choices[0]["message"]["content"]
            
            # Parse the failure analysis
            improvement_plan = self._parse_failure_analysis(analysis_text, failure.task_id)
            
            logger.info(f"Failure analysis completed for {failure.task_id}: "
                       f"should_retry={improvement_plan.should_retry}")
            
            return improvement_plan
            
        except Exception as e:
            logger.error(f"Failure analysis failed for {failure.task_id}: {e}")
            # Return a basic plan on failure
            return ImprovementPlan(
                task_id=failure.task_id,
                failure_analysis="Analysis failed due to LLM error",
                root_cause=failure.error_type,
                improvement_steps=["Review error manually", "Retry with different approach"],
                estimated_success_probability=0.3,
                should_retry=True,
                alternative_approach="Manual intervention required"
            )
    
    def _build_task_analysis_prompt(self, task: Task) -> str:
        """Build prompt for task analysis."""
        return f"""
Analyze the following development task and provide a detailed assessment:

TASK DESCRIPTION:
{task.description}

REQUIREMENTS:
{chr(10).join(f"- {req}" for req in task.requirements)}

CONSTRAINTS:
{chr(10).join(f"- {constraint}" for constraint in task.constraints)}

PROJECT CONTEXT:
- Working Directory: {task.working_directory or "Not specified"}
- Target Files: {', '.join(task.target_files) if task.target_files else "None specified"}
- Quality Threshold: {task.minimum_quality_threshold}

Please provide analysis in the following JSON format:
{{
    "complexity_score": 0.0-1.0,
    "estimated_duration": minutes,
    "risk_level": "low|medium|high|critical",
    "required_capabilities": ["capability1", "capability2"],
    "dependencies": ["dependency1", "dependency2"],
    "success_probability": 0.0-1.0,
    "recommended_agent": "local_llm|claude_code|github_copilot",
    "execution_strategy": "detailed strategy description"
}}

Focus on:
1. Code complexity and technical difficulty
2. Time estimation based on scope
3. Risk assessment for automated execution
4. Required tools and capabilities
5. Probability of successful completion
6. Best agent for this specific task
"""
    
    def _build_quality_evaluation_prompt(self, code: str, context: str) -> str:
        """Build prompt for quality evaluation."""
        return f"""
Evaluate the quality of the following code and provide detailed scoring:

CONTEXT:
{context}

CODE:
```
{code}
```

Please provide evaluation in the following JSON format:
{{
    "overall": 0.0-1.0,
    "code_quality": 0.0-1.0,
    "consistency": 0.0-1.0,
    "test_coverage": 0.0-1.0,
    "security": 0.0-1.0,
    "performance": 0.0-1.0,
    "strengths": ["strength1", "strength2"],
    "weaknesses": ["weakness1", "weakness2"],
    "improvement_suggestions": ["suggestion1", "suggestion2"]
}}

Evaluation criteria:
1. Code Quality: Readability, maintainability, best practices
2. Consistency: Follows project patterns and conventions
3. Test Coverage: Presence and quality of tests
4. Security: Security best practices and vulnerability assessment
5. Performance: Efficiency and optimization considerations
6. Overall: Weighted average considering all factors
"""
    
    def _build_failure_analysis_prompt(self, failure: FailureInfo) -> str:
        """Build prompt for failure analysis."""
        return f"""
Analyze the following task failure and create an improvement plan:

TASK ID: {failure.task_id}
AGENT USED: {failure.agent_used}
ERROR TYPE: {failure.error_type}
ERROR MESSAGE: {failure.error_message}
RETRY COUNT: {failure.retry_count}

STACK TRACE:
{failure.stack_trace or "Not available"}

CONTEXT:
{json.dumps(failure.context, indent=2)}

Please provide analysis in the following JSON format:
{{
    "failure_analysis": "detailed analysis of what went wrong",
    "root_cause": "primary cause of failure",
    "improvement_steps": ["step1", "step2", "step3"],
    "estimated_success_probability": 0.0-1.0,
    "should_retry": true/false,
    "alternative_approach": "description of alternative approach",
    "recommended_changes": {{
        "prompts": "prompt improvements",
        "parameters": "parameter adjustments",
        "approach": "strategy changes"
    }}
}}

Focus on:
1. Root cause identification
2. Specific actionable improvements
3. Success probability of retry
4. Alternative approaches if retry likely to fail
5. Learning for future similar tasks
"""
    
    def _parse_task_analysis(self, response_text: str, task_id: str) -> TaskAnalysis:
        """Parse LLM response into TaskAnalysis object."""
        try:
            # Extract JSON from response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON found in response")
            
            json_text = response_text[json_start:json_end]
            data = json.loads(json_text)
            
            # Convert agent name to enum
            agent_mapping = {
                "local_llm": AgentType.LOCAL_LLM,
                "claude_code": AgentType.CLAUDE_CODE,
                "github_copilot": AgentType.GITHUB_COPILOT,
                "openai_codex": AgentType.OPENAI_CODEX
            }
            
            recommended_agent = agent_mapping.get(
                data.get("recommended_agent", "local_llm"),
                AgentType.LOCAL_LLM
            )
            
            return TaskAnalysis(
                task_id=task_id,
                complexity_score=float(data.get("complexity_score", 0.5)),
                estimated_duration=float(data.get("estimated_duration", 30.0)),
                risk_level=data.get("risk_level", "medium"),
                required_agent_capabilities=data.get("required_capabilities", []),
                dependencies=data.get("dependencies", []),
                success_probability=float(data.get("success_probability", 0.5)),
                recommended_agent=recommended_agent,
                execution_strategy=data.get("execution_strategy", "")
            )
            
        except Exception as e:
            logger.error(f"Failed to parse task analysis: {e}")
            # Return default analysis
            return TaskAnalysis(
                task_id=task_id,
                complexity_score=0.5,
                estimated_duration=30.0,
                risk_level="medium",
                success_probability=0.5,
                recommended_agent=AgentType.LOCAL_LLM,
                execution_strategy="Default strategy due to parsing error"
            )
    
    def _parse_quality_evaluation(self, response_text: str) -> QualityScore:
        """Parse LLM response into QualityScore object."""
        try:
            # Extract JSON from response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON found in response")
            
            json_text = response_text[json_start:json_end]
            data = json.loads(json_text)
            
            return QualityScore(
                overall=float(data.get("overall", 0.5)),
                code_quality=float(data.get("code_quality", 0.5)),
                consistency=float(data.get("consistency", 0.5)),
                test_coverage=float(data.get("test_coverage", 0.0)),
                security=float(data.get("security", 0.5)),
                performance=float(data.get("performance", 0.5))
            )
            
        except Exception as e:
            logger.error(f"Failed to parse quality evaluation: {e}")
            # Return conservative score
            return QualityScore(
                overall=0.5,
                code_quality=0.5,
                consistency=0.5,
                test_coverage=0.0,
                security=0.5,
                performance=0.5
            )
    
    def _parse_failure_analysis(self, response_text: str, task_id: str) -> ImprovementPlan:
        """Parse LLM response into ImprovementPlan object."""
        try:
            # Extract JSON from response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON found in response")
            
            json_text = response_text[json_start:json_end]
            data = json.loads(json_text)
            
            return ImprovementPlan(
                task_id=task_id,
                failure_analysis=data.get("failure_analysis", "Analysis not available"),
                root_cause=data.get("root_cause", "Unknown"),
                improvement_steps=data.get("improvement_steps", []),
                estimated_success_probability=float(data.get("estimated_success_probability", 0.3)),
                recommended_changes=data.get("recommended_changes", {}),
                should_retry=data.get("should_retry", True),
                alternative_approach=data.get("alternative_approach")
            )
            
        except Exception as e:
            logger.error(f"Failed to parse failure analysis: {e}")
            # Return basic plan
            return ImprovementPlan(
                task_id=task_id,
                failure_analysis="Parsing failed",
                root_cause="Unknown",
                improvement_steps=["Review manually"],
                estimated_success_probability=0.3,
                should_retry=True
            )
    
    def is_available(self) -> bool:
        """Check if the LLM agent is available."""
        return self.config.enabled and self._connection_verified
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the LLM service."""
        if not self.config.enabled:
            return {
                "status": "disabled",
                "available": False,
                "message": "Local LLM is disabled in configuration"
            }
        
        try:
            start_time = time.time()
            await self._verify_connection()
            response_time = time.time() - start_time
            
            return {
                "status": "healthy",
                "available": True,
                "response_time_ms": int(response_time * 1000),
                "api_url": self.config.api_url,
                "model": self.model_name
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "available": False,
                "error": str(e),
                "api_url": self.config.api_url
            }