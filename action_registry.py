from dataclasses import dataclass
from typing import Callable, Dict, Any, Optional, List


@dataclass
class ActionDef:
    action_id: str
    name: str
    description: str
    schema: Dict[str, Dict[str, Any]]
    run: Callable[[Dict[str, Any]], tuple]  # returns (ok: bool, msg: str)


class ActionRegistry:
    """
    Registry of actions that can be executed by macro steps.
    Plugins register actions here, and UI queries here to build fields.
    """

    def __init__(self):
        self._actions: Dict[str, ActionDef] = {}

    def register_action(
        self,
        action_id: str,
        name: str,
        description: str = "",
        schema: Optional[Dict[str, Dict[str, Any]]] = None,
        run: Optional[Callable[[Dict[str, Any]], tuple]] = None,
        replace: bool = False,
    ):
        action_id = str(action_id).strip()
        if not action_id:
            raise ValueError("action_id is required")

        if not replace and action_id in self._actions:
            raise ValueError(f"Action already registered: {action_id}")

        if schema is None:
            schema = {}

        if run is None:
            def _noop(_params):
                return False, f"No run() provided for action: {action_id}"
            run = _noop

        self._actions[action_id] = ActionDef(
            action_id=action_id,
            name=str(name).strip() or action_id,
            description=str(description or "").strip(),
            schema=dict(schema),
            run=run,
        )

    def has(self, action_id: str) -> bool:
        return str(action_id) in self._actions

    def get(self, action_id: str) -> Optional[ActionDef]:
        return self._actions.get(str(action_id))

    def list_actions(self) -> List[ActionDef]:
        return [self._actions[k] for k in sorted(self._actions.keys())]

    def list_action_ids(self) -> List[str]:
        return [a.action_id for a in self.list_actions()]

    def get_name(self, action_id: str) -> str:
        a = self.get(action_id)
        return a.name if a else str(action_id)
