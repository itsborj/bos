#!/usr/bin/env python3
"""
Test script for NVIDIA NIM API with request/response logging.

This demonstrates how to interact with NVIDIA's NIM endpoints and log
API calls for debugging/auditing purposes.

Requires: pip install openai python-dotenv
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any

# Try to import openai (optional - only needed for direct API calls)
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("Warning: openai package not installed. Install with: pip install openai")


# ---- Logging Setup ----

def setup_logger(
    log_file: Optional[str] = None,
    log_level: int = logging.INFO
) -> logging.Logger:
    """Configure a logger for NVIDIA API calls.
    
    Args:
        log_file: Optional file path to write logs to. If None, uses
                  ~/.logs/nvidia_api_<timestamp>.log
        log_level: Logging level (default: INFO)
    
    Returns:
        Configured logger instance
    """
    if log_file is None:
        os.makedirs(os.path.expanduser("~/.logs"), exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.expanduser(f"~/.logs/nvidia_api_{timestamp}.log")
    
    logger = logging.getLogger("nvidia_api")
    logger.setLevel(log_level)
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # File handler - JSON format for machine parsing
    fh = logging.FileHandler(log_file)
    fh.setLevel(log_level)
    
    # Console handler - human readable
    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)  # Only warnings/errors to console
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    
    logger.addHandler(fh)
    logger.addHandler(ch)
    
    logger.info(f"Logger initialized. Writing to: {log_file}")
    return logger


class NvidiaAPIWrapper:
    """Wrapper around NVIDIA NIM API with built-in logging."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://integrate.api.nvidia.com/v1",
        logger: Optional[logging.Logger] = None
    ):
        """Initialize the NVIDIA API wrapper.
        
        Args:
            api_key: NVIDIA API key. If None, reads from NVIDIA_API_KEY env var.
            base_url: NIM API base URL
            logger: Optional pre-configured logger. If None, creates one.
        """
        if not OPENAI_AVAILABLE:
            raise ImportError(
                "The 'openai' package is required. Install with: pip install openai"
            )
        
        self.api_key = api_key or os.getenv("NVIDIA_API_KEY")
        if not self.api_key:
            raise ValueError(
                "NVIDIA_API_KEY not provided and not found in environment variables."
            )
        
        self.base_url = base_url
        self.client = OpenAI(
            base_url=base_url,
            api_key=self.api_key
        )
        self.logger = logger or setup_logger()
    
    def chat_completions_create(
        self,
        model: str,
        messages: list,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        stream: bool = False,
        log_request: bool = True,
        log_response: bool = True,
        redact_keys: bool = True
    ) -> Dict[str, Any]:
        """Create a chat completion with full request/response logging.
        
        Args:
            model: Model ID (e.g., "meta/llama-3.1-405b-instruct")
            messages: List of message dicts
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            stream: Whether to stream the response
            log_request: Whether to log the request details
            log_response: Whether to log the response details
            redact_keys: Whether to redact the API key from logs
        
        Returns:
            Response from the API as a dict
        """
        # Prepare log-safe request data
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
            "messages_count": len(messages),
            "messages": messages
        }
        
        if redact_keys and self.api_key:
            log_data["api_key"] = f"{self.api_key[:8]}...{self.api_key[-4:]}"
        
        if log_request:
            self.logger.info(
                "NVIDIA API Request",
                extra={
                    "request": {
                        "model": model,
                        "message_count": len(messages),
                        "max_tokens": max_tokens,
                        "temperature": temperature
                    }
                }
            )
            # Also log full JSON to a separate debug file
            self._log_json("nvidia_api_requests.jsonl", log_data)
        
        try:
            # Make the API call
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=stream
            )
            
            # Convert response to dict for logging
            if stream:
                # For streaming, collect all chunks
                chunks = []
                full_content = ""
                for chunk in response:
                    chunks.append(chunk.model_dump())
                    if chunk.choices and chunk.choices[0].delta.content:
                        full_content += chunk.choices[0].delta.content
                
                response_data = {
                    "stream": True,
                    "chunks_count": len(chunks),
                    "content": full_content,
                    "status": "success"
                }
            else:
                response_dict = response.model_dump()
                response_data = {
                    "stream": False,
                    "content": response.choices[0].message.content,
                    "finish_reason": response.choices[0].finish_reason,
                    "usage": response_dict.get("usage"),
                    "model": response.model,
                    "status": "success"
                }
            
            if log_response:
                self.logger.info(
                    "NVIDIA API Response",
                    extra={
                        "response": {
                            "model": response_data.get("model"),
                            "finish_reason": response_data.get("finish_reason"),
                            "usage": response_data.get("usage"),
                            "content_length": len(response_data.get("content", ""))
                        }
                    }
                )
                self._log_json("nvidia_api_responses.jsonl", response_data)
            
            return response_data
        
        except Exception as e:
            error_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e),
                "error_type": type(e).__name__,
                "model": model
            }
            self.logger.error(
                "NVIDIA API Error",
                extra={"error": error_data},
                exc_info=True
            )
            self._log_json("nvidia_api_errors.jsonl", error_data)
            raise
    
    def _log_json(self, filename: str, data: Dict[str, Any]) -> None:
        """Append JSON data to a log file (JSONL format - one line per record).
        
        Args:
            filename: Name of the log file (created in ~/.logs/)
            data: Dictionary to serialize as JSON
        """
        log_dir = os.path.expanduser("~/.logs")
        os.makedirs(log_dir, exist_ok=True)
        filepath = os.path.join(log_dir, filename)
        
        with open(filepath, "a") as f:
            f.write(json.dumps(data, default=str) + "\n")
    
    def list_models(self) -> list:
        """List available models (if the endpoint supports it).
        
        Note: NIM may not support the /models endpoint.
        """
        try:
            response = self.client.models.list()
            return [m.id for m in response.data]
        except Exception as e:
            self.logger.warning(f"Could not list models: {e}")
            return []


def main():
    """Example usage of the NVIDIA API wrapper."""
    
    # Initialize the wrapper
    api = NvidiaAPIWrapper()
    
    # Example messages
    messages = [
        {
            "role": "system",
            "content": "You are a helpful AI assistant for the BOS (Business Operating System) project."
        },
        {
            "role": "user",
            "content": "What is the purpose of the CLAUDE.md file in this project?"
        }
    ]
    
    # Make a request
    print("\n=== Calling NVIDIA NIM API ===")
    print(f"Model: meta/llama3-70b-instruct")
    print(f"Messages: {len(messages)}")
    print()
    
    try:
        result = api.chat_completions_create(
            model="meta/llama3-70b-instruct",
            messages=messages,
            max_tokens=1024,
            temperature=0.7,
            log_request=True,
            log_response=True
        )
        
        print("\n=== Response ===")
        print(result["content"])
        print()
        print("="*50)
        print(f"Finish reason: {result.get('finish_reason')}")
        print(f"Usage: {result.get('usage')}")
        print("\nLogs saved to ~/.logs/nvidia_api_*.log")
        print("JSON request logs: ~/.logs/nvidia_api_requests.jsonl")
        print("JSON response logs: ~/.logs/nvidia_api_responses.jsonl")
        
    except Exception as e:
        print(f"\nError: {e}")
        print("Check ~/.logs/nvidia_api_errors.jsonl for details")


if __name__ == "__main__":
    main()
