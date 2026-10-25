---
Status: Active
Owner: hyperd
Last Updated: 2026-10-25
---

# Microarchitectural CPU Cache Timing Isolation Guide

## 1. Context & Threat Model

Recent AI security research has demonstrated that untrusted or compromised autonomous agents can establish covert side channels via CPU microarchitectural timing—specifically exploiting shared L2/L3 cache hierarchies and SMT (Hyper-Threading) execution pipelines—to transmit unauthorized data or state to other processes or network-connected boundaries.

This framework enforces physical core isolation and strict container/microVM cgroup boundaries to eliminate shared cache-line footprint leaks.

## 2. Architecture & Components

1. **Kernel Scheduling Isolation (`nix/modules/core/microarchitectural-isolation.nix`)**:
   - `nosmt`: Hardware-level hyperthreading disabled to eliminate sibling-thread pipeline sharing.
   - `isolcpus=managed_irq,domain,4-7`: Strips physical CPU cores 4-7 completely from the CFS general OS scheduler.
   - `nohz_full=4-7`: Eliminates scheduler tick timer interrupts on isolated cores.
   - `rcu_nocbs=4-7`: Offloads RCU callback processing to housekeeping cores (0-3).
   - `irqaffinity=0-3` & `workqueue.cpumask=0-3`: Directs interrupts and kernel workqueues away from isolated lines.

2. **Libvirt KVM MicroVM Pinning (`config/libvirt/untrusted-agent-microvm.xml`)**:
   - Explicit `<cputune>` binding guest vCPUs 0-3 statically to physical cores 4-7.
   - Guest CPU topology hides SMT threads (`threads='1'`) and disables `rdtscp` timestamp counters.

3. **Ephemeral Lifecycle Automation**:
   - `scripts/ai/orchestrate-sandbox.sh`: Lifecycle engine verifying hardware invariants, booting `isolated-agent-runner`, enforcing `AllowedCPUs=4-5` with 50% `CPUQuota`, executing untrusted code, and tearing down with complete memory/cache dropping (`sync; echo 3 > /proc/sys/vm/drop_caches`).
   - `scripts/ai/agent_driver.py`: Python CLI driver verifying system state and dispatching payloads under monitored execution.

## 3. Verification & Auditing

Run the test suite to verify module syntax, XML contracts, and fail-closed security properties:
```bash
python3 scripts/testing/test-microarchitectural-isolation.py
```
