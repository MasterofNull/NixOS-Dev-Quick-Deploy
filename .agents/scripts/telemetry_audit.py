import json, pathlib, collections
p = pathlib.Path('/home/hyperd/Documents/NixOS-Dev-Quick-Deploy/.agents/telemetry/hybrid-events.jsonl')
if not p.exists():
    print('MISSING')
else:
    lines = p.read_text().splitlines()[-200:]
    types = collections.Counter(json.loads(l).get('event_type','?') for l in lines if l.strip())
    print('event distribution (last 200):', dict(types))
    steps = types.get('agent_step_complete', 0)
    infer = types.get('local_inference', 0)
    total = steps + infer
    ratio = f"{infer}/{total}" if total > 0 else "N/A"
    print(f'training signal ratio: {ratio} local_inference vs agent_step_complete')
