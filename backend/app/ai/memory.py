import time
from typing import Dict, List

class ConversationalMemory:
    """Manages context-aware message history for users with automatic window limits."""
    
    def __init__(self, max_history: int = 15):
        self.max_history = max_history
        self.conversations: Dict[str, List[Dict[str, str]]] = {}
        self.last_activity: Dict[str, float] = {}

    def get_history(self, session_id: str) -> List[Dict[str, str]]:
        """Retrieve message log for the given session."""
        self.last_activity[session_id] = time.time()
        return self.conversations.get(session_id, [])

    def add_message(self, session_id: str, role: str, content: str):
        """Append message to user log, pruning oldest entries if capacity is reached."""
        if session_id not in self.conversations:
            self.conversations[session_id] = []
        
        self.conversations[session_id].append({"role": role, "content": content})
        self.last_activity[session_id] = time.time()

        # Limit window size
        if len(self.conversations[session_id]) > self.max_history * 2:
            # Retain system prompts or just prune oldest pairs
            self.conversations[session_id] = self.conversations[session_id][-self.max_history * 2:]

    def clear(self, session_id: str):
        """Reset conversation state."""
        if session_id in self.conversations:
            del self.conversations[session_id]
        if session_id in self.last_activity:
            del self.last_activity[session_id]

# Global conversational memory cache
memory = ConversationalMemory()
