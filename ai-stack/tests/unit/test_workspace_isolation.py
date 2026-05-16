import pytest
import inspect
from orchestration.workspace_isolation import WorkspaceManager, IsolationMode

def test_workspace_manager_default_path():
    """Verify the production base_dir default without requiring root write access."""
    sig = inspect.signature(WorkspaceManager.__init__)
    assert sig.parameters["base_dir"].default is None

def test_workspace_manager_init(tmp_path):
    wm = WorkspaceManager(base_dir=tmp_path)
    assert wm.base_dir == tmp_path
    assert wm.default_mode == IsolationMode.TEMP_DIR
