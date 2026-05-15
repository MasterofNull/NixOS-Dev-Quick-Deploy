# DEPRECATED (arch-revamp G-2): real_time_learning_engine.py is the canonical
# entry point for all learning-related activities. ContinuousLearningPipeline
# will be merged into a learning/ submodule in a future phase. This top-level
# shim remains for backward compatibility only — do not add new callers.
from extensions.continuous_learning import *
