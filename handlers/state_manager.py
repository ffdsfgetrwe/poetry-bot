class StateManager:
    def __init__(self):
        self.edit_states = {}
        self.admin_states = {}
    
    def set_edit_state(self, user_id: int, state: str):
        self.edit_states[user_id] = state
    
    def get_edit_state(self, user_id: int) -> str:
        return self.edit_states.get(user_id)
    
    def clear_edit_state(self, user_id: int):
        self.edit_states.pop(user_id, None)
    
    def set_admin_state(self, user_id: int, state: str):
        self.admin_states[user_id] = state
    
    def get_admin_state(self, user_id: int) -> str:
        return self.admin_states.get(user_id)
    
    def clear_admin_state(self, user_id: int):
        self.admin_states.pop(user_id, None)
    
    def clear_all_states(self, user_id: int):
        """Очистить все состояния пользователя"""
        self.clear_edit_state(user_id)
        self.clear_admin_state(user_id)

# Глобальный экземпляр
state_manager = StateManager()
